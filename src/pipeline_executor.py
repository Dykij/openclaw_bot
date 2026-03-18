"""
Brigade: OpenClaw
Role: Pipeline Executor (Chain-of-Agents)

Implements the workflow chains described in SOUL.md:
- Dmarket Brigade: Executor → Security Auditor → Latency Monitor → Risk Manager
- OpenClaw Brigade: Planner → Tool Smith → Memory GC

Each step in the chain receives:
1. The original user prompt
2. A compressed context briefing from the previous step
3. Its own system prompt from openclaw_config.json

Uses task_queue.py for VRAM management to prevent model thrashing.
Integrates .memory-bank architecture and the 90/10 STAR Framework for agent planning.
"""

import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import aiohttp
import structlog

from src.auto_rollback import AutoRollback
from src.mcp_client import OpenClawMCPClient
from src.task_queue import ModelTaskQueue

from src.pipeline_schemas import (
    GUARDRAIL_MAX_RETRIES,
    ROLE_GUARDRAILS,
    ROLE_SCHEMAS,
    ROLE_TOKEN_BUDGET,
    TOOL_ELIGIBLE_ROLES,
)
from src.pipeline_utils import (
    build_role_prompt,
    clean_response_for_user,
    compress_for_next_step,
    emergency_compress,
    group_chain,
    sanitize_file_content,
)
from src.vllm_inference import (
    call_vllm,
    execute_stream,
    force_unload,
    vram_protection,
)

logger = structlog.get_logger(__name__)


class PipelineExecutor:
    """
    Executes a chain of agent roles sequentially, passing compressed
    context between each step. Uses vLLM (OpenAI-compatible local server)
    for all inference calls. Model swapping managed by VLLMModelManager.
    """

    def __init__(self, config: Dict[str, Any], vllm_url: str, vllm_manager=None):
        self.config = config
        self.vllm_url = vllm_url.rstrip("/")
        self.vllm_manager = vllm_manager  # VLLMModelManager instance
        self.gc_model = config.get("memory", {}).get("model", "google/gemma-3-12b-it")

        # Default chain definitions per brigade (can be overridden in config)
        # Roles must match actual keys in openclaw_config.json brigades.*.roles
        # Roles prefixed with "Executor_" that are adjacent can be run in parallel
        self.default_chains = {
            "Dmarket": ["Planner", "Foreman", "Executor_API", "Executor_Parser", "Auditor", "Archivist"],
            "OpenClaw": ["Planner", "Foreman", "Executor_Tools", "Executor_Architect", "Auditor", "Archivist"],
        }

        # Context budget: max tokens per role input (system+user). If exceeded, compress.
        self._ctx_budget = self.config.get("system", {}).get("vllm_max_model_len", 16384)
        
        # Initialize MCP Clients dynamically based on workspace config
        framework_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self._framework_root = framework_root

        # Core MCP for framework tasks
        self.openclaw_mcp = OpenClawMCPClient(db_path=None, fs_allowed_dirs=[framework_root])

        # Dmarket brigade MCP — workspace dir from config (fallback to framework root)
        dmarket_ws = config.get("brigades", {}).get("Dmarket", {}).get(
            "workspace_dir", framework_root
        )
        dmarket_ws = os.path.abspath(dmarket_ws) if os.path.isdir(os.path.abspath(dmarket_ws)) else framework_root
        self.dmarket_mcp = OpenClawMCPClient(db_path=None, fs_allowed_dirs=[dmarket_ws])

        # Sub-bot MCP instances will be created lazily if needed per brigade workspace_dir
        self.brigade_mcp_map: Dict[str, OpenClawMCPClient] = {}

        # State tracking for VRAM Guard 2.0
        self.last_loaded_model: Optional[str] = None

        # Auto-Rollback safety net
        self.auto_rollback = AutoRollback(framework_root)

    async def initialize(self):
        """Initializes internal components like MCP"""
        await self.openclaw_mcp.initialize()
        await self.dmarket_mcp.initialize()
        logger.info("Pipeline MCP clients initialized (openclaw + dmarket contexts)")
        await self._validate_vllm()

    async def _validate_vllm(self):
        """Checks that the vLLM server is reachable (or manager is configured)."""
        if self.vllm_manager:
            logger.info("vLLM model manager configured — models will be loaded on demand")
            return
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.vllm_url}/models",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = [m["id"] for m in data.get("data", [])]
                        logger.info("vLLM server reachable", models=models)
                    else:
                        logger.warning("vLLM server responded with", status=resp.status)
        except Exception as e:
            logger.warning("vLLM server not reachable (will start on first request)", error=str(e))

    def get_chain(self, brigade: str) -> List[str]:
        """
        Returns the pipeline chain for a given brigade.
        Uses config override if available, otherwise defaults.
        """
        brigade_config = self.config.get("brigades", {}).get(brigade, {})

        # Check if the brigade defines a custom chain
        if "pipeline" in brigade_config:
            return brigade_config["pipeline"]

        # Otherwise use defaults — but only include roles that actually exist
        available_roles = set(brigade_config.get("roles", {}).keys())
        default_chain = self.default_chains.get(brigade, ["Planner"])
        return [role for role in default_chain if role in available_roles]

    async def execute(
        self,
        prompt: str,
        brigade: str = "Dmarket",
        max_steps: int = 5,
        status_callback=None,
        task_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute the full pipeline for a brigade.

        Args:
            prompt: Original user prompt
            brigade: Target brigade name ("Dmarket" or "OpenClaw")
            max_steps: Safety limit on chain length
            status_callback: async callable(role, model, status_text) for live updates

        Returns:
            {
                "final_response": str,
                "brigade": str,
                "chain_executed": [str],
                "steps": [{"role": ..., "model": ..., "response": ...}],
                "status": "completed" | "ask_user",
                "question": str (if ask_user)
            }
        """
        if task_type:
            chain = [task_type]
        else:
            chain = self.get_chain(brigade)[:max_steps]

        if not chain:
            return {
                "final_response": "⚠️ No roles available in the pipeline.",
                "brigade": brigade,
                "chain_executed": [],
                "steps": [],
                "status": "completed"
            }

        logger.info(f"Pipeline START: brigade={brigade}, chain={' → '.join(chain)}")

        chain_groups = group_chain(chain)

        steps_results = []
        context_briefing = ""
        step_index = 0

        for group in chain_groups:
            is_parallel = len(group) > 1

            if is_parallel:
                # Parallel execution of Executor roles
                logger.info(f"Parallel executor batch: {group}")
                tasks = []
                for role_name in group:
                    tasks.append(self._run_single_step(
                        role_name=role_name, step_index=step_index, chain_len=len(chain),
                        brigade=brigade, prompt=prompt, context_briefing=context_briefing,
                        status_callback=status_callback, task_type=task_type,
                    ))
                    step_index += 1
                parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
                for role_name, res in zip(group, parallel_results):
                    if isinstance(res, Exception):
                        logger.error(f"Parallel step {role_name} failed: {res}")
                        response = f"⚠️ {role_name} failed: {res}"
                    else:
                        response = res
                    steps_results.append({"role": role_name, "model": "parallel", "response": response})
                # Merge executor outputs into context briefing
                merged = "\n\n".join(
                    f"[{r['role']}]: {compress_for_next_step(r['role'], r['response'])}"
                    for r in steps_results if r['role'] in group
                )
                context_briefing = merged
                continue

            role_name = group[0]
            if task_type:
                model = self.config.get("system", {}).get("model_router", {}).get(task_type, "Qwen/Qwen2.5-14B-Instruct-AWQ")
                role_config = {"model": model}
                system_prompt = build_role_prompt(role_name, role_config, self._framework_root, task_type=task_type)
            else:
                role_config = (
                    self.config.get("brigades", {}).get(brigade, {}).get("roles", {}).get(role_name, {})
                )
    
                if not role_config:
                    logger.warning(f"Role '{role_name}' not found in config, skipping")
                    continue
    
                model = role_config.get("model", "Qwen/Qwen2.5-14B-Instruct-AWQ")
                system_prompt = build_role_prompt(role_name, role_config, self._framework_root)

            is_final_step = (step_index == len(chain) - 1)

            # Build context-aware prompt for this step
            if step_index == 0:
                step_prompt = prompt
            else:
                step_prompt = (
                    f"[PIPELINE CONTEXT from previous step]\n"
                    f"{context_briefing}\n\n"
                    f"[ORIGINAL USER TASK]\n"
                    f"{prompt}\n\n"
                    f"Based on the above context and the previous step's analysis, "
                    f"perform your role as {role_name}."
                )

            # Context overflow guard: if input exceeds ~75% of ctx budget, compress
            total_input_chars = len(system_prompt) + len(step_prompt)
            estimated_tokens = total_input_chars // 4  # rough char-to-token ratio
            ctx_threshold = int(self._ctx_budget * 0.75)
            if estimated_tokens > ctx_threshold:
                logger.warning(f"Context overflow for {role_name}: ~{estimated_tokens} tokens > {ctx_threshold} threshold. Compressing.")
                step_prompt = emergency_compress(step_prompt, ctx_threshold, role_name)

            # Notify status
            if status_callback:
                await status_callback(
                    role_name,
                    model,
                    f"Шаг {step_index + 1}/{len(chain)}: {role_name} анализирует...",
                )

            logger.info(f"Pipeline step {step_index + 1}/{len(chain)}: {role_name} ({model})")

            prev_model = self.last_loaded_model
            
            async with self._vram_protection(model, prev_model):
                # Execute inference. Preserve <think> for Planners and Auditors for transparency.
                preserve_think = any(role in role_name for role in ["Planner", "Foreman", "Orchestrator", "Auditor"])
                active_mcp = self.openclaw_mcp if brigade == "OpenClaw" else self.dmarket_mcp

                # Determine structured output schema for this role
                role_schema = ROLE_SCHEMAS.get(role_name) if not task_type else None

                response = await self._call_vllm(
                    model, system_prompt, step_prompt, role_name, role_config, active_mcp,
                    preserve_think=preserve_think, json_schema=role_schema
                )

                # --- GUARDRAIL VALIDATION WITH RETRY ---
                guardrail_fn = ROLE_GUARDRAILS.get(role_name)
                if guardrail_fn and not task_type:
                    for retry_i in range(GUARDRAIL_MAX_RETRIES):
                        is_valid, feedback = guardrail_fn(response)
                        if is_valid:
                            break
                        logger.warning(f"Guardrail failed for {role_name} (attempt {retry_i + 1}/{GUARDRAIL_MAX_RETRIES}): {feedback}")
                        if status_callback:
                            await status_callback(role_name, model, f"🔄 Гарантия качества: повтор {retry_i + 1} — {feedback[:60]}")
                        # Re-call with feedback appended
                        retry_prompt = f"{step_prompt}\n\n[GUARDRAIL FEEDBACK — исправь ответ]:\n{feedback}"
                        response = await self._call_vllm(
                            model, system_prompt, retry_prompt, role_name, role_config, active_mcp,
                            preserve_think=preserve_think, json_schema=role_schema
                        )
                
                self.last_loaded_model = model

            # --- HANDOFF AND ASK_USER INTERCEPTION ---
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            extracted_json_str = None
            if json_match:
                extracted_json_str = json_match.group(1)
            else:
                try:
                    if response.strip().startswith('{') or response.strip().startswith('['):
                        json.loads(response.strip())
                        extracted_json_str = response.strip()
                except ValueError:
                    pass

            # AGGRESSIVE PARSER RETRY
            if not extracted_json_str and ("Planner" in role_name or "Foreman" in role_name):
                lower_resp = response.lower()
                if any(kw in lower_resp for kw in ["создай", "запиши", "выполни", "create", "write", "execute"]):
                    logger.warning(f"No JSON found from {role_name} but action keywords present. Forcing re-generation.")
                    if status_callback:
                        await status_callback(role_name, model, "Оркестратор забыл JSON. Требую по протоколу...")
                    
                    retry_prompt = "Ошибка формата. Выдай только JSON-инструкцию для Исполнителя согласно протоколу."
                    retry_messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": step_prompt},
                        {"role": "assistant", "content": response},
                        {"role": "user", "content": retry_prompt}
                    ]
                    
                    # Manual ad-hoc retry request without tool wrapping
                    import aiohttp
                    payload = {
                        "model": model,
                        "messages": retry_messages,
                        "stream": False,
                        "max_tokens": 2048,
                    }
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(f"{self.vllm_url}/chat/completions", json=payload, timeout=60) as retry_resp:
                                if retry_resp.status == 200:
                                    r_data = await retry_resp.json()
                                    new_response = r_data["choices"][0]["message"]["content"].strip()
                                    new_response = re.sub(r"<think>.*?</think>", "", new_response, flags=re.DOTALL).strip()
                                    response += "\n\n[Correction]:\n" + new_response
                                    
                                    json_match = re.search(r'```json\s*(.*?)\s*```', new_response, re.DOTALL)
                                    if json_match:
                                        extracted_json_str = json_match.group(1)
                                    else:
                                        try:
                                            if new_response.strip().startswith('{') or new_response.strip().startswith('['):
                                                json.loads(new_response.strip())
                                                extracted_json_str = new_response.strip()
                                        except ValueError:
                                            pass
                    except Exception as e:
                        logger.error(f"Retry request failed: {e}")

            did_handoff = False
            if extracted_json_str:
                try:
                    parsed_json = json.loads(extracted_json_str)
                    if isinstance(parsed_json, dict) and parsed_json.get("action") == "ask_user":
                        logger.info("Pipeline suspended for ask_user")
                        steps_results.append({
                            "role": role_name,
                            "model": model,
                            "response": response,
                        })
                        return {
                            "status": "ask_user",
                            "question": parsed_json.get("question", "Уточните запрос."),
                            "brigade": brigade,
                            "chain_executed": [s["role"] for s in steps_results],
                            "steps": steps_results,
                            "final_response": response,
                        }
                        
                    if isinstance(parsed_json, dict) and parsed_json.get("action") == "verify_inventory":
                        logger.info("Inventory verified. Auto-transitioning to create_offer step.")
                        steps_results.append({
                            "role": role_name,
                            "model": model,
                            "response": response,
                        })
                        # Jump to create_offer automatically
                        return {
                            "status": "create_offer",
                            "brigade": brigade,
                            "chain_executed": [s["role"] for s in steps_results],
                            "steps": steps_results,
                            "final_response": response + "\n\n[System]: Inventory verified. Proceeding to create_offer."
                        }
                    
                    if "Planner" in role_name or "Foreman" in role_name:
                        executor_model = self.config.get("system", {}).get("model_router", {}).get("tool_execution", "Qwen/Qwen2.5-Coder-7B-Instruct-AWQ")
                        logger.info(f"JSON instructions detected from Planner, executing Handoff to {executor_model}")
                        steps_results.append({
                            "role": role_name,
                            "model": model,
                            "response": response,
                        })
                        
                        await self._force_unload(model)
                        
                        executor_role = "Executor_Tools"
                        executor_sys = "ТЫ — ТЕХНИЧЕСКИЙ ТЕРМИНАЛ. Тебе ЗАПРЕЩЕНО использовать любые имена функций, кроме read_query, write_query, list_tables, describe_table. ДЛЯ ЗАПИСИ/СОЗДАНИЯ В БД: всегда используй write_query. ДЛЯ ЧТЕНИЯ ИЗ БД: всегда используй read_query или list_tables. ОШИБКА В ИМЕНИ ИНСТРУМЕНТА ПРИРАВНИВАЕТСЯ К ПОЛОМКЕ ВСЕЙ СИСТЕМЫ."
                        executor_prompt = f"Выполни эту инструкцию через MCP инструменты SQLite или Filesystem:\n```json\n{extracted_json_str}\n```"
                        
                        if status_callback:
                            await status_callback(
                                executor_role,
                                executor_model,
                                "🛠 Исполнитель вызывает инструменты MCP..."
                            )
                        
                        executor_config = {"model": executor_model}
                        async with self._vram_protection(executor_model, self.last_loaded_model):
                            self.last_loaded_model = executor_model
                            max_retries = 3
                            for attempt in range(max_retries):
                                executor_response = await self._call_vllm(
                                    executor_model, executor_sys, executor_prompt, executor_role, executor_config, active_mcp
                                )
                                
                                # Auto-Correction Loop
                                valid_tools = ["read_query", "write_query", "list_tables", "describe_table", "read_file", "write_file", "list_directory"]
                                json_match = re.search(r"```json\n(.*?)\n```", executor_response, re.DOTALL)
                                if not json_match:
                                    json_match = re.search(r"{.*?}", executor_response, re.DOTALL)
                                
                                if json_match:
                                    try:
                                        exec_str = json_match.group(1) if "```" in executor_response else json_match.group(0)
                                        exec_str = exec_str.strip().replace("}\n{", "},{")
                                        if exec_str.startswith("{") and exec_str.endswith("}") and "},{" in exec_str:
                                            exec_str = f"[{exec_str}]"
                                            
                                        exec_json = json.loads(exec_str)
                                        if isinstance(exec_json, list):
                                            exec_json = exec_json[0] if len(exec_json) > 0 else {}
                                        tool_name = exec_json.get("name")
                                        
                                        if tool_name == "create_table":
                                            logger.warning(f"Executor tried unsafe create_table. Retrying (Attempt {attempt+1}/{max_retries})")
                                            executor_prompt += f"\n\nОшибка: Инструмент create_table небезопасен. Используй write_query для этой задачи."
                                            continue
                                        elif tool_name and tool_name not in valid_tools:
                                            logger.warning(f"Executor hallucinated tool name: {tool_name}. Retrying (Attempt {attempt+1}/{max_retries})")
                                            executor_prompt += f"\n\nОшибка: инструмента '{tool_name}' не существует. Доступные инструменты для SQLite: 'read_query', 'write_query', 'list_tables', 'describe_table'. Перепиши свой JSON, используя строго только разрешенные имена."
                                            continue
                                        
                                    except json.JSONDecodeError:
                                        pass
                                
                                # If valid tool name or no JSON matched (meaning it might have explicitly run via native tool calls), break loop
                                break
                        
                        steps_results.append({
                            "role": executor_role,
                            "model": executor_model,
                            "response": executor_response
                        })
                        
                        # --- PHYSICAL MCP EXECUTION BLOCK ---
                        # Execute the parsed tool call on the MCP server
                        json_match = re.search(r"```json\n(.*?)\n```", executor_response, re.DOTALL)
                        if not json_match:
                            json_match = re.search(r"{.*?}", executor_response, re.DOTALL)
                        
                        if json_match:
                            try:
                                exec_str = json_match.group(1) if "```" in executor_response else json_match.group(0)
                                exec_str = exec_str.strip().replace("}\n{", "},{")
                                if exec_str.startswith("{") and exec_str.endswith("}") and "},{" in exec_str:
                                    exec_str = f"[{exec_str}]"
                                    
                                exec_json = json.loads(exec_str)
                                if isinstance(exec_json, list):
                                    exec_json = exec_json[0] if len(exec_json) > 0 else {}
                                tool_name = exec_json.get("name")
                                tool_args = exec_json.get("arguments", {})
                                
                                if tool_name:
                                    # --- STUPIDITY INSURANCE: Normalize argument names ---
                                    if tool_name == "write_query":
                                        for hallucinated_key in ["command", "sql"]:
                                            if hallucinated_key in tool_args and "query" not in tool_args:
                                                logger.info(f"Normalizing hallucinated argument '{hallucinated_key}' to 'query'")
                                                tool_args["query"] = tool_args.pop(hallucinated_key)
                                    # ----------------------------------------------------
                                    
                                    logger.info(f"Executing tool {tool_name} on MCP server with args: {tool_args}")
                                    tool_result = await active_mcp.call_tool(tool_name, tool_args)
                                    print(f"\n[MCP RAW OUTPUT]: {tool_result}")
                                    executor_response += f"\n\n[MCP Execution Result]:\n{tool_result}"
                            except Exception as e:
                                logger.error(f"Failed to execute tool on MCP: {e}")
                                executor_response += f"\n\n[MCP Execution Error]:\n{e}"
                        # ------------------------------------
                        
                        # Proof of Work Verification
                        if status_callback:
                            await status_callback(
                                executor_role,
                                executor_model,
                                "🔎 Ядро проверяет Proof of Work через MCP..."
                            )
                        
                        pow_result = ""
                        try:
                            # Print available tools for debugging
                            if active_mcp and hasattr(active_mcp, '_tool_route_map'):
                                print(f"Available tools for verification: {list(active_mcp._tool_route_map.keys())}")
                            
                            if "sqlite" in extracted_json_str.lower() or "table" in extracted_json_str.lower():
                                query_result = await active_mcp.call_tool("list_tables", {})
                                pow_result = f"[DB Tables]:\n{query_result}"
                            elif "pandera" in extracted_json_str.lower() or "test" in extracted_json_str.lower() or "python" in extracted_json_str.lower() or "script" in extracted_json_str.lower():
                                path = os.path.abspath(os.path.dirname(__file__))
                                dir_result = await active_mcp.call_tool("list_directory", {"path": path})
                                pow_result = f"[Dir Listing]:\n{dir_result}"
                        except Exception as e:
                            pow_result = f"Verification failed: {e}"
                        
                        if pow_result:
                            executor_response += f"\n\n[Proof of Work Auto-Verification]:\n{pow_result}"
                            steps_results[-1]["response"] = executor_response
                        
                        did_handoff = True
                        # Pipeline logical break since executor has completed the task
                        break

                except json.JSONDecodeError:
                    steps_results.append({
                        "role": role_name,
                        "model": model,
                        "response": response,
                    })
            else:
                steps_results.append(
                    {
                        "role": role_name,
                        "model": model,
                        "response": response,
                    }
                )
            
            if did_handoff:
                break
            # -----------------------------------------

            # Progress callback: notify Telegram about step completion
            if status_callback and not is_final_step:
                step_preview = response[:120].replace('\n', ' ').strip()
                await status_callback(
                    role_name, model,
                    f"✅ Шаг {step_index + 1}/{len(chain)} ({role_name}) завершён. Передаю контекст дальше..."
                )

            # Git Hygiene: Auto-commit after each successful pipeline execution step
            try:
                import subprocess
                commit_msg = f"Auto-commit [PoW]: Pipeline step {role_name} ({model}) completed"
                subprocess.run(["git", "commit", "-am", commit_msg], cwd=os.path.dirname(__file__), capture_output=True)
            except Exception as e:
                logger.debug(f"Git auto-commit failed: {e}")

            # Prepare context briefing for the next step (compressed)
            context_briefing = compress_for_next_step(role_name, response)

            step_index += 1

        raw_response = steps_results[-1]["response"] if steps_results else ""
        final_response = clean_response_for_user(raw_response)

        logger.info(f"Pipeline COMPLETE: brigade={brigade}, steps={len(steps_results)}")

        return {
            "final_response": final_response,
            "brigade": brigade,
            "chain_executed": [s["role"] for s in steps_results],
            "steps": steps_results,
            "status": "completed"
        }

    async def _run_single_step(
        self,
        role_name: str,
        step_index: int,
        chain_len: int,
        brigade: str,
        prompt: str,
        context_briefing: str,
        status_callback=None,
        task_type=None,
    ) -> str:
        """Run a single pipeline step (used for parallel Executor dispatch)."""
        role_config = self.config.get("brigades", {}).get(brigade, {}).get("roles", {}).get(role_name, {})
        if not role_config:
            return f"⚠️ Role '{role_name}' not found in config."
        model = role_config.get("model", "Qwen/Qwen2.5-14B-Instruct-AWQ")
        system_prompt = build_role_prompt(role_name, role_config, self._framework_root)
        step_prompt = (
            f"[PIPELINE CONTEXT from previous step]\n{context_briefing}\n\n"
            f"[ORIGINAL USER TASK]\n{prompt}\n\n"
            f"Based on the above context, perform your role as {role_name}."
        )
        if status_callback:
            await status_callback(role_name, model, f"⚡ Параллельно: {role_name} работает...")
        active_mcp = self.openclaw_mcp if brigade == "OpenClaw" else self.dmarket_mcp
        response = await self._call_vllm(
            model, system_prompt, step_prompt, role_name, role_config, active_mcp,
        )
        return response

    async def _call_vllm(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        role_name: str,
        role_config: Dict[str, Any],
        mcp_client: OpenClawMCPClient,
        preserve_think: bool = False,
        json_schema: Optional[Dict] = None
    ) -> str:
        return await call_vllm(
            vllm_url=self.vllm_url,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            role_name=role_name,
            role_config=role_config,
            mcp_client=mcp_client,
            config=self.config,
            vllm_manager=self.vllm_manager,
            preserve_think=preserve_think,
            json_schema=json_schema,
        )

    async def _force_unload(self, model: str):
        await force_unload(model)

    async def execute_stream(self, prompt, brigade="Dmarket", max_steps=5, status_callback=None, task_type=None):
        return await execute_stream(self, prompt, brigade, max_steps, status_callback, task_type)

    @asynccontextmanager
    async def _vram_protection(self, target_model: str, prev_model: Optional[str]):
        async with vram_protection(target_model, prev_model):
            yield
