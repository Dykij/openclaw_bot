"""
Brigade: OpenClaw
Role: Pipeline Executor (Chain-of-Agents) — Core

Implements the workflow chains described in SOUL.md.
Delegates state management to _state.py, reflexion to _reflexion.py,
and tool execution to _tools_handler.py.

Submodules (extracted for modularity):
  _role_executor  — single-step execution + vLLM inference
  _chain_selector — static / dynamic chain selection
  _ensemble       — parallel Executor instances with consensus
  _multi_task     — prompt decomposition + parallel sub-task execution
"""

import asyncio
import json
import os
import re
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import aiohttp
import structlog

from src.auto_rollback import AutoRollback
from src.mcp_client import OpenClawMCPClient
from src.ai.inference.metrics import InferenceMetricsCollector
from src.utils.async_utils import taskgroup_gather
from src.ai.inference.budget import AdaptiveTokenBudget
from src.ai.inference.router import SmartModelRouter

from src.pipeline_schemas import (
    GUARDRAIL_MAX_RETRIES,
    ROLE_GUARDRAILS,
    ROLE_SCHEMAS,
    TOOL_ELIGIBLE_ROLES,
    PipelineStepResult,
    PipelineResult,
)
from src.pipeline_utils import (
    build_role_prompt,
    clean_response_for_user,
    compress_for_next_step,
    emergency_compress,
    group_chain,
)
from src.code_validator import CodeValidator
from src.context_bridge import ContextBridge
from src.vllm_inference import (
    execute_stream,
    force_unload,
    vram_protection,
)
from src.openrouter_client import call_openrouter, reset_circuit_breakers
from src.ai.agents.react import ReActReasoner
from src.ai.agents.constitutional import ConstitutionalChecker
from src.tools.dynamic_sandbox import DynamicSandbox

from src.pipeline._state import init_smart_router, init_supermemory, recall_memory_context
from src.pipeline._reflexion import reflexion_fallback
from src.pipeline._tools_handler import handle_planner_handoff

# v11.7 SOTA modules
from src.pipeline._lats_search import LATSEngine, classify_complexity
from src.safety.hallucination import MARCHProtocol

# v13.2: AFlow dynamic chain generation + Ensemble Voting
from src.pipeline._aflow import AFlowEngine

# v14.0: SAGE self-evolution + MAC constitution
from src.pipeline._sage import SAGEEngine
from src.safety.mac_constitution import MACConstitution

# v14.1: Counterfactual Credit + ProRL rollout evaluation
from src.pipeline._counterfactual import CounterfactualCredit
from src.pipeline._prorl import ProRLEngine

# v14.2: Tool Call Text Parser — intercept XML/MD tool leakage from free models
from src.pipeline._tool_call_parser import (
    parse_tool_calls,
    strip_tool_calls,
    execute_parsed_tool_calls,
    format_observations,
)

# --- Extracted submodules ---
from src.pipeline._role_executor import call_vllm_inference, run_single_step
from src.pipeline._chain_selector import (
    get_chain as _get_chain,
    get_chain_dynamic as _get_chain_dynamic,
)
from src.pipeline._ensemble import ensemble_vote
from src.pipeline._multi_task import (
    _decompose_multi_task,
    _route_subtask,
    execute_multi_task,
    # Re-export constants for backward compatibility
    _ACTION_VERBS_RE,
    _SEMANTIC_MIN_LEN,
    _NUMBERED_RE,
    _BRIGADE_KEYWORDS,
)

logger = structlog.get_logger(__name__)


async def _async_save_trajectory(supermemory, prompt, chain, complexity, steps_results, response):
    """v14.0: Complementary RL — сохранение траектории успешной сложной задачи в SuperMemory."""
    try:
        await asyncio.to_thread(
            supermemory.save_success_trajectory,
            task=prompt[:200],
            chain=chain,
            complexity=complexity,
            reward=0.85,
            response_preview=response[:120],
        )
        logger.debug("Complementary RL: trajectory saved", chain=chain, complexity=complexity)
    except Exception as _err:
        logger.debug("Complementary RL: trajectory save non-fatal error", error=str(_err))


class PipelineExecutor:
    """
    Executes a chain of agent roles sequentially, passing compressed
    context between each step. Uses vLLM (OpenAI-compatible local server)
    for all inference calls. Model swapping managed by VLLMModelManager.
    """

    def __init__(self, config: Dict[str, Any], vllm_url: str, vllm_manager=None):
        self.config = config
        self.vllm_url = vllm_url.rstrip("/")
        self.vllm_manager = vllm_manager
        self.gc_model = config.get("memory", {}).get("model", "google/gemma-3-12b-it")

        # OpenRouter configuration (primary inference)
        self.openrouter_config = config.get("system", {}).get("openrouter", {})
        self.openrouter_enabled = self.openrouter_config.get("enabled", False) and bool(self.openrouter_config.get("api_key", ""))
        self._use_local_models = self.openrouter_config.get("use_local_models", True)
        self.force_cloud = (
            self.openrouter_enabled
            and self.openrouter_config.get("force_cloud", False)
            and not self._use_local_models
        )

        self.default_chains = {
            "Dmarket-Dev": ["Planner", "Coder", "Auditor"],
            "OpenClaw-Core": ["Planner", "Foreman", "Executor_Tools", "Executor_Architect", "Auditor", "State_Manager", "Archivist"],
            "Research-Ops": ["Researcher", "Analyst", "Summarizer"],
        }

        self._ctx_budget = self.config.get("system", {}).get("vllm_max_model_len", 16384)

        # Initialize MCP Clients dynamically
        framework_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self._framework_root = framework_root
        self.openclaw_mcp = OpenClawMCPClient(db_path=None, fs_allowed_dirs=[framework_root])

        dmarket_ws = config.get("brigades", {}).get("Dmarket", {}).get("workspace_dir", framework_root)
        dmarket_ws = os.path.abspath(dmarket_ws) if os.path.isdir(os.path.abspath(dmarket_ws)) else framework_root
        self.dmarket_mcp = OpenClawMCPClient(db_path=None, fs_allowed_dirs=[dmarket_ws])
        self.brigade_mcp_map: Dict[str, OpenClawMCPClient] = {}

        self.last_loaded_model: Optional[str] = None
        self.auto_rollback = AutoRollback(framework_root)
        self.code_validator = CodeValidator(framework_root, config)

        # Reuse shared singletons from llm_gateway
        from src.llm_gateway import get_metrics_collector, get_token_budget
        self.metrics_collector = get_metrics_collector() or InferenceMetricsCollector()
        vram_gb = config.get("system", {}).get("hardware", {}).get("vram_gb", 16.0)
        self.token_budget = get_token_budget() or AdaptiveTokenBudget(
            default_max_tokens=config.get("system", {}).get("vllm_max_model_len", 8192),
            vram_gb=vram_gb,
        )
        logger.info("InferenceMetrics + AdaptiveTokenBudget activated (shared)")

        self._supermemory = None
        self._rag_engine = None

        # SmartModelRouter (delegated to _state.py)
        self._smart_router = init_smart_router(config, self.force_cloud)

        # Context Bridge
        if self.force_cloud:
            self.context_bridge = ContextBridge({"context_bridge": {"enabled": False}})
            logger.info("Context Bridge DISABLED (cloud-only mode, no local model swaps)")
        else:
            self.context_bridge = ContextBridge(config.get("system", {}))

        self._react_reasoner = ReActReasoner(vllm_url=self.vllm_url, model="")
        self._constitutional = ConstitutionalChecker(vllm_url=self.vllm_url, model="")
        self._sandbox = DynamicSandbox()

        # v11.7: LATS tree search + MARCH hallucination control
        lats_model = self.config.get("model_router", {}).get(
            "research", "meta-llama/llama-3.3-70b-instruct:free"
        )
        self._lats_engine = LATSEngine(model=lats_model, vllm_url=self.vllm_url)
        self._march_protocol = MARCHProtocol(vllm_url=self.vllm_url)

        # v13.2: AFlow dynamic chain generator
        aflow_model = self.config.get("system", {}).get("model_router", {}).get(
            "intent", "meta-llama/llama-3.3-70b-instruct:free"
        )
        self._aflow = AFlowEngine(
            vllm_url=self.vllm_url,
            model=aflow_model,
            default_chains=self.default_chains,
        )

        # v14.0: SAGE self-evolution engine
        sage_cfg = self.config.get("system", {}).get("sage", {})
        self._sage = SAGEEngine(
            vllm_url=self.vllm_url,
            model=aflow_model,
            enabled=sage_cfg.get("enabled", True),
        )

        # v14.0: MAC Dynamic Constitution
        mac_cfg = self.config.get("system", {}).get("mac", {})
        self._mac = MACConstitution(
            vllm_url=self.vllm_url,
            model=self.config.get("system", {}).get("model_router", {}).get(
                "expand", "google/gemma-3-12b-it:free"
            ),
            enabled=mac_cfg.get("enabled", True),
        )

        # v14.1: Counterfactual Credit for Ensemble Voting attribution
        cc_cfg = self.config.get("system", {}).get("counterfactual_credit", {})
        self._counterfactual = CounterfactualCredit(
            enabled=cc_cfg.get("enabled", True),
        )

        # v14.1: ProRL lightweight rollout evaluation
        prorl_cfg = self.config.get("system", {}).get("prorl", {})
        self._prorl = ProRLEngine(
            enabled=prorl_cfg.get("enabled", True),
        )

    def _init_supermemory(self) -> None:
        init_supermemory(self)

    async def _recall_memory_context(self, prompt: str) -> str:
        return await recall_memory_context(self, prompt)

    async def _reflexion_fallback(self, prompt: str, error_response: str) -> Optional[str]:
        return await reflexion_fallback(self.vllm_url, self.config, prompt, error_response)

    async def _quick_inference(self, prompt: str) -> str:
        """v16.4: Fast LLM inference for autonomous reflection (Self-Healing)."""
        try:
            if self.force_cloud and self.openrouter_config:
                response = await call_openrouter(
                    openrouter_config=self.openrouter_config,
                    vllm_url=self.vllm_url,
                    model="meta-llama/llama-3.3-70b-instruct:free",
                    fallback_model="meta-llama/llama-3.3-70b-instruct:free",
                    system_prompt="You are a debugging assistant. Be concise. Answer in Russian.",
                    user_prompt=prompt,
                    role_name="Reflection",
                    role_config={"temperature": 0.3, "max_tokens": 512},
                    mcp_client=None,
                    config=self.config,
                )
            else:
                async with aiohttp.ClientSession() as sess:
                    payload = {
                        "model": "meta-llama/llama-3.3-70b-instruct",
                        "messages": [
                            {"role": "system", "content": "You are a debugging assistant. Be concise. Answer in Russian."},
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                        "max_tokens": 512,
                        "temperature": 0.3,
                    }
                    async with sess.post(
                        f"{self.vllm_url}/chat/completions",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            response = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        else:
                            response = ""
            return (response or "").strip()
        except Exception as e:
            logger.warning("v16.4 quick inference failed", error=str(e))
            return ""

    async def initialize(self):
        """Initializes internal components like MCP.
        MCP failures are non-fatal — pipeline proceeds with reduced capabilities."""
        try:
            await self.openclaw_mcp.initialize()
        except Exception as e:
            logger.warning("OpenClaw MCP init failed (non-fatal)", error=str(e))
        try:
            await self.dmarket_mcp.initialize()
        except Exception as e:
            logger.warning("Dmarket MCP init failed (non-fatal)", error=str(e))
        logger.info("Pipeline MCP clients initialized (openclaw + dmarket contexts)")

        self._init_supermemory()

        if not self.force_cloud:
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
        return _get_chain(self.config, self.default_chains, brigade)

    async def get_chain_dynamic(
        self,
        prompt: str,
        brigade: str,
        max_steps: int = 7,
    ) -> tuple[List[str], str]:
        return await _get_chain_dynamic(
            prompt=prompt, brigade=brigade, config=self.config,
            default_chains=self.default_chains, aflow_engine=self._aflow,
            prorl_engine=self._prorl, get_chain_fn=self.get_chain,
            max_steps=max_steps,
        )

    async def execute(
        self,
        prompt: str,
        brigade: str = "Dmarket",
        max_steps: int = 5,
        status_callback=None,
        task_type: Optional[str] = None,
        shared_observations: dict = None
    ) -> Dict[str, Any]:
        """Execute the full pipeline for a brigade."""

        # --- v14.4: Multi-Task Decomposer (P1-1 / P1-3 hotfix) ---
        # If the prompt contains a numbered list (1. ... 2. ...) and is long enough,
        # decompose into sub-tasks and route each to the best-matching brigade.
        if not task_type and len(prompt) > 200:
            sub_tasks = _decompose_multi_task(prompt)
            if len(sub_tasks) >= 2:
                logger.info(
                    "Multi-task decomposer activated",
                    n_subtasks=len(sub_tasks),
                    brigades=[s[1] for s in sub_tasks],
                )
                if status_callback:
                    await status_callback(
                        "Decomposer", "system",
                        f"🧩 Обнаружено {len(sub_tasks)} подзадач — запускаю параллельно...",
                    )
                return await self._execute_multi_task(
                    sub_tasks, prompt, max_steps, status_callback,
                )

        # П7-fix: инициализируем _traj_context безусловно, чтобы избежать
        # UnboundLocalError на строке ниже при task_type != None
        _traj_context = ""
        if task_type:
            chain = [task_type]
            chain_source = "task_type"
        else:
            # v14.0: Complementary RL — few-shot trajectories для AFlow
            if self._supermemory and classify_complexity(prompt) in ("complex", "extreme"):
                try:
                    _traj_context = self._supermemory.recall_similar_trajectories(prompt, top_k=3)
                    if _traj_context:
                        logger.info("Complementary RL: trajectories injected for AFlow")
                except Exception as _traj_err:
                    logger.debug("Trajectory recall failed (non-fatal)", error=str(_traj_err))

            # v13.2: AFlow — dynamic chain generation
            chain, chain_source = await self.get_chain_dynamic(prompt, brigade, max_steps)

        if not chain:
            return {
                "final_response": "⚠️ No roles available in the pipeline.",
                "brigade": brigade,
                "chain_executed": [],
                "steps": [],
                "status": "completed"
            }

        logger.info(f"Pipeline START: brigade={brigade}, chain={' → '.join(chain)}, source={chain_source}")

        # Reset per-model circuit breakers at the start of each pipeline run
        # so stale failures from previous runs don't poison fresh queries.
        reset_circuit_breakers()

        # --- v13.1: LATS tree search for complex tasks (TaskGroup + early exit) ---
        # v15.4: Skip LATS entirely when prompt contains a URL — force tool-execution chain
        complexity = classify_complexity(prompt)
        _has_url = bool(re.search(r"https?://", prompt))
        if (
            complexity in ("complex", "extreme")
            and not task_type
            and brigade in ("Dmarket", "Dmarket-Dev")
            and not _has_url
        ):
            logger.info("LATS activated", complexity=complexity)
            if status_callback:
                await status_callback("LATS", "tree-search", "🌳 LATS: задача сложная — запускаю дерево поиска решений...")
            try:
                lats_model = self.config.get("brigades", {}).get(brigade, {}).get(
                    "roles", {}
                ).get("Planner", {}).get("model", "meta-llama/llama-3.3-70b-instruct:free")
                lats_result = await self._lats_engine.search(
                    prompt=prompt, model=lats_model, config=self.config,
                )
                if lats_result.best_answer:
                    logger.info("LATS completed", depth=lats_result.depth_reached,
                                score=lats_result.best_score, early_exit=lats_result.early_exit)
                    # v15.3: Wrap LATS reasoning trace in <think> so it's hidden from user
                    _lats_answer = lats_result.best_answer
                    # v15.4: Leakage containment — if the best answer itself
                    # contains planning preamble, wrap the entire preamble in
                    # <think> so prompt_handler strips it before the user sees it.
                    _PLANNING_RE = re.compile(
                        r"^((?:.*?(?:Approach\s*#\d|Plan\s*:|Подход\s*#?\d|План\s*:).*?\n)+)",
                        re.IGNORECASE | re.DOTALL,
                    )
                    _plan_m = _PLANNING_RE.match(_lats_answer)
                    if _plan_m:
                        _lats_answer = (
                            f"<think>\n{_plan_m.group(1).strip()}\n</think>\n\n"
                            + _lats_answer[_plan_m.end():]
                        )
                    _lats_trace = "\n".join(
                        f"[D{n.depth}] {n.thought[:120]}"
                        for n in lats_result.tree_trace
                        if n.thought != "[ROOT]" and n.thought != _lats_answer
                    )
                    if _lats_trace:
                        _lats_answer = f"<think>\n{_lats_trace}\n</think>\n\n{_lats_answer}"
                    return {
                        "final_response": _lats_answer,
                        "brigade": brigade,
                        "chain_executed": ["LATS_TreeSearch"],
                        "steps": [{"role": "LATS_TreeSearch", "model": lats_model, "response": lats_result.best_answer}],
                        "status": "completed",
                        "meta": {"lats_depth": lats_result.depth_reached, "lats_score": lats_result.best_score,
                                 "lats_early_exit": lats_result.early_exit},
                    }
            except Exception as e:
                logger.warning("LATS failed, falling back to linear pipeline", error=str(e))

        budget = self.token_budget.estimate_budget(prompt, task_type or "general")
        logger.info("Token budget estimated", max_tokens=budget.max_tokens, reason=budget.budget_reason)

        memory_context = await self._recall_memory_context(prompt)

        # v14.2: YouTube — если в промпте есть YouTube URL, извлекаем транскрипт
        _yt_metadata_only = False  # флаг: субтитры недоступны, но есть метаданные
        _yt_transcript_injected = False  # флаг: полный транскрипт успешно инжектирован
        try:
            from src.tools.youtube_parser import is_youtube_url, analyze_youtube_video
            if is_youtube_url(prompt):
                logger.info("YouTube URL detected in prompt, fetching transcript")
                if status_callback:
                    await status_callback("System", "youtube", "🎥 YouTube: извлекаю транскрипт видео...")
                yt_result = await analyze_youtube_video(prompt)
                if yt_result.success:
                    _yt_ctx = yt_result.to_context()
                    memory_context = (_yt_ctx + "\n\n" + memory_context) if memory_context else _yt_ctx
                    _yt_transcript_injected = True
                    logger.info("YouTube transcript injected", video_id=yt_result.video_id, chars=len(yt_result.transcript))
                    # П6-fix: пересчитать budget с учётом реального контекста после YouTube inject
                    effective_prompt = prompt + "\n" + _yt_ctx
                    budget = self.token_budget.estimate_budget(effective_prompt, "research")
                    logger.info("Token budget re-estimated after YouTube inject",
                                max_tokens=budget.max_tokens, chars=len(_yt_ctx))
                elif yt_result.title:
                    # П1/П2-fix: субтитры недоступны, но видео существует — сообщаем явно
                    _yt_metadata_only = True
                    _meta_ctx = yt_result.to_context()  # содержит "(Субтитры недоступны)"
                    
                    if status_callback:
                        await status_callback("System", "youtube", "Поиск текстового описания видео в сети...")
                    
                    from src.research._searcher import web_search
                    try:
                        web_result = await web_search(self.openclaw_mcp or self.dmarket_mcp, yt_result.title + " transcript text")
                        _meta_ctx += f"\n\n[Web Search Fallback for '{yt_result.title}']:\n{web_result}"
                    except Exception as e:
                        logger.warning("web_search fallback failed", error=str(e))
                        
                    memory_context = (_meta_ctx + "\n\n" + memory_context) if memory_context else _meta_ctx
                    logger.warning("YouTube subtitles unavailable, metadata only",
                                   video_id=yt_result.video_id, title=yt_result.title)
                    if status_callback:
                        await status_callback("System", "youtube",
                            f"⚠️ Субтитры недоступны для видео «{yt_result.title}». "
                            "Анализ по метаданным и Web Search.")
                else:
                    logger.warning("YouTube fetch failed", error=yt_result.error)
        except Exception as _yt_err:
            logger.debug("YouTube detection failed (non-fatal)", error=str(_yt_err))

        # v14.0: Complementary RL — инжекция few-shot траекторий в начальный контекст
        if _traj_context and memory_context:
            memory_context = _traj_context + "\n\n" + memory_context
        elif _traj_context:
            memory_context = _traj_context

        # v16.1: Deep Source Injection (NotebookLM simulation)
        if complexity == "extreme":
            try:
                from src.memory_mcp import export_vault_content
                _mega_source = export_vault_content()
                if _mega_source and "No markdown files" not in _mega_source:
                    memory_context = (_mega_source + "\n\n" + memory_context) if memory_context else _mega_source
                    logger.info("NotebookLM Deep Source Injection applied (Complexity: extreme)")
            except Exception as _deep_err:
                logger.debug("Deep Source Injection failed", error=str(_deep_err))

        # v16.1: Semantic Cross-Linking (GraphRAG approximation)
        try:
            from src.pipeline._logic_provider import get_neural_connection
            _neural_cx = get_neural_connection(prompt)
            if _neural_cx:
                memory_context = (_neural_cx + "\n\n" + memory_context) if memory_context else _neural_cx
        except Exception as _ns_err:
            logger.debug("Neural Synthesis failed", error=str(_ns_err))

        # v16.3: Persistent Knowledge Hook — fresh entries get top priority
        try:
            from src.pipeline._logic_provider import get_recent_knowledge
            _fresh = get_recent_knowledge(max_age_seconds=3600)
            if _fresh:
                memory_context = (_fresh + "\n\n" + memory_context) if memory_context else _fresh
                logger.info("v16.3 fresh knowledge injected", chars=len(_fresh))
        except Exception as _fk_err:
            logger.debug("Fresh knowledge hook failed", error=str(_fk_err))

        chain_groups = group_chain(chain)
        steps_results = []
        context_briefing = memory_context
        step_index = 0

        for group in chain_groups:
            is_parallel = len(group) > 1

            if is_parallel:
                logger.info(f"Parallel executor batch: {group}")
                tasks = []
                for role_name in group:
                    tasks.append(self._run_single_step(
                        role_name=role_name, step_index=step_index, chain_len=len(chain),
                        brigade=brigade, prompt=prompt, context_briefing=context_briefing,
                        status_callback=status_callback, task_type=task_type,
                    ))
                    step_index += 1
                parallel_results = await taskgroup_gather(*tasks, return_exceptions=True)
                for role_name, res in zip(group, parallel_results):
                    if isinstance(res, Exception):
                        logger.error(f"Parallel step {role_name} failed: {res}")
                        response = f"⚠️ {role_name} failed: {res}"
                    else:
                        response = res
                    steps_results.append({"role": role_name, "model": "parallel", "response": response})
                merged = "\n\n".join(
                    f"[{r['role']}]: {compress_for_next_step(r['role'], r['response'])}"
                    for r in steps_results if r['role'] in group
                )
                context_briefing = merged
                continue

            role_name = group[0]
            if task_type:
                model = self.config.get("system", {}).get("model_router", {}).get(task_type, "meta-llama/llama-3.3-70b-instruct:free")
                role_config = {"model": model}
                system_prompt = build_role_prompt(role_name, role_config, self._framework_root, task_type=task_type)
            else:
                role_config = (
                    self.config.get("brigades", {}).get(brigade, {}).get("roles", {}).get(role_name, {})
                )
                if not role_config:
                    logger.warning(f"Role '{role_name}' not found in config, skipping")
                    continue
                model = role_config.get("model", "meta-llama/llama-3.3-70b-instruct:free")
                system_prompt = build_role_prompt(role_name, role_config, self._framework_root)

            is_final_step = (step_index == len(chain) - 1)

            # v14.0: MAC — дополняем system_prompt динамическими правилами проекта
            try:
                system_prompt = self._mac.enrich_system_prompt(system_prompt)
            except Exception as _mac_err:
                logger.debug("MAC enrichment failed (non-fatal)", error=str(_mac_err))

            # v16.0: Obsidian Brigade Logic override
            try:
                from src.pipeline._logic_provider import get_brigade_logic
                _obsidian_logic = get_brigade_logic(brigade)
                if _obsidian_logic:
                    system_prompt += _obsidian_logic
            except Exception as _obs_err:
                logger.debug("Obsidian logic provider failed (non-fatal)", error=str(_obs_err))

            # v16.1: Recursive Self-Reflection (Learning Log Check)
            try:
                from src.pipeline._logic_provider import check_learning_log
                _reflection = check_learning_log(prompt)
                if _reflection:
                    system_prompt += _reflection
            except Exception as _refl_err:
                logger.debug("Recursive self-reflection failed", error=str(_refl_err))

            # П4-fix v14.8 → усилено в v14.9: антигаллюцинационная директива для YouTube
            if _yt_transcript_injected and role_name in ("Researcher", "Analyst", "Summarizer"):
                _yt_directive = (
                    "[КРИТИЧЕСКОЕ ПРАВИЛО — YOUTUBE TRANSCRIPT GROUNDING]\n"
                    "⛔ ЗАПРЕЩЕНО делать ЛЮБЫЕ утверждения о содержании видео, которых НЕТ в транскрипте ниже.\n"
                    "⛔ ЗАПРЕЩЕНО использовать знания из обучающих данных об этом видео, канале или авторе.\n"
                    "✅ Отвечай СТРОГО на основе предоставленного транскрипта.\n"
                    "✅ Если информации нет в транскрипте — явно скажи: «В транскрипте это не упоминается».\n"
                    "Несоблюдение этого правила = галлюцинация = провал задачи.\n"
                )
                # Вставляем В НАЧАЛО system_prompt чтобы модель увидела правило первым
                system_prompt = _yt_directive + "\n" + system_prompt
                logger.debug("YouTube grounding directive injected into system_prompt", role=role_name)

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

            if shared_observations:
                shared_str = "\n".join(f"- {k}: {v[:1000]}..." for k, v in shared_observations.items())
                step_prompt += f"\n\n[SHARED OBSERVATIONS (Parallel Subtasks)]\n{shared_str}"

            total_input_chars = len(system_prompt) + len(step_prompt)
            estimated_tokens = total_input_chars // 4
            ctx_threshold = int(self._ctx_budget * 0.75)
            if estimated_tokens > ctx_threshold:
                logger.warning(f"Context overflow for {role_name}: ~{estimated_tokens} tokens > {ctx_threshold} threshold. Compressing.")
                step_prompt = emergency_compress(step_prompt, ctx_threshold, role_name)

            display_model = self._display_model(role_config, model)
            if status_callback:
                await status_callback(
                    role_name, display_model,
                    f"Шаг {step_index + 1}/{len(chain)}: {role_name} анализирует...",
                )

            logger.info(f"Pipeline step {step_index + 1}/{len(chain)}: {role_name} ({display_model})")

            prev_model = self.last_loaded_model

            if not self.force_cloud:
                if (prev_model and prev_model != model
                        and self.context_bridge.enabled and self.vllm_manager):
                    import uuid
                    _pipeline_id = str(uuid.uuid4())
                    _snapshot = self.context_bridge.build_handoff_summary(
                        pipeline_id=_pipeline_id, brigade=brigade, chain_position=step_index,
                        source_model=prev_model, target_model=model,
                        steps_results=steps_results, accumulated_context=context_briefing,
                    )
                    self.context_bridge.save_before_swap(_snapshot)
                    logger.info("Context Bridge: snapshot saved before model swap",
                                pipeline_id=_pipeline_id, source=prev_model, target=model)
                    _restored = self.context_bridge.restore_after_swap(_pipeline_id)
                    if _restored:
                        context_briefing = _restored
                        logger.info("Context Bridge: context restored for new model")

            did_handoff = False
            _autoheal_used = False  # v16.4: one self-healing retry per step

            async with self._vram_protection(model, prev_model):
                preserve_think = any(role in role_name for role in ["Planner", "Foreman", "Orchestrator", "Auditor"])
                active_mcp = self.openclaw_mcp if brigade == "OpenClaw" else self.dmarket_mcp
                role_schema = ROLE_SCHEMAS.get(role_name) if not task_type else None

                # v13.2: Ensemble Voting для Executor ролей (только сложные задачи)
                _ensemble_cfg = self.config.get("system", {}).get("ensemble_voting", {})
                _ensemble_enabled = _ensemble_cfg.get("enabled", True)
                _is_executor = role_name.startswith("Executor_") or role_name in ("Coder",)
                _is_complex = classify_complexity(prompt) in ("complex", "extreme")
                _use_ensemble = _ensemble_enabled and _is_executor and _is_complex and not task_type

                if _use_ensemble:
                    _auditor_cfg = (
                        self.config.get("brigades", {}).get(brigade, {}).get("roles", {}).get("Auditor", {})
                    )
                    logger.info("Ensemble Voting activated", role=role_name, instances=2)
                    if status_callback:
                        await status_callback(role_name, display_model,
                                              "🗳️ Ensemble: запускаю N экземпляров с разной температурой...")
                    response = await self._ensemble_vote(
                        role_name=role_name,
                        model=model,
                        system_prompt=system_prompt,
                        step_prompt=step_prompt,
                        role_config=role_config,
                        active_mcp=active_mcp,
                        n_instances=_ensemble_cfg.get("n_instances", 2),
                        auditor_role_config=_auditor_cfg,
                    )
                else:
                    response = await self._call_vllm(
                        model, system_prompt, step_prompt, role_name, role_config, active_mcp,
                        preserve_think=preserve_think, json_schema=role_schema
                    )

                # --- v14.2: TOOL CALL TEXT INTERCEPTION ---
                # Free models may emit raw XML/MD tool calls instead of native JSON.
                # Parse them, execute, inject Observation, strip raw tags from response.
                try:
                    _parsed_calls = parse_tool_calls(response)
                    if _parsed_calls:
                        if role_name in TOOL_ELIGIBLE_ROLES:
                            # П5-fix: исполняем инструменты только у eligible ролей.
                            # Summarizer/Analyst/Researcher не должны вызывать инструменты.
                            logger.info(
                                "Tool leakage intercepted",
                                role=role_name, n_calls=len(_parsed_calls),
                                tools=[c.name for c in _parsed_calls],
                            )
                            if status_callback:
                                await status_callback(
                                    role_name, display_model,
                                    f"🔧 Перехвачен вызов инструмента: {_parsed_calls[0].name}. Выполняю...",
                                )
                            _tc_results = await execute_parsed_tool_calls(
                                _parsed_calls, active_mcp, self._sandbox,
                            )
                            if shared_observations is not None:
                                for call, tc_res in zip(_parsed_calls, _tc_results):
                                    shared_observations[call.name] = (tc_res.output or tc_res.error or "")[:2000]
                            _observation = format_observations(_tc_results)

                            # --- v16.4: Autonomous Error Catcher + Self-Healing ---
                            try:
                                from src.pipeline._logic_provider import is_tool_error, autonomous_reflection
                                _tool_errors = [
                                    (c.name, r.output or r.error or "")
                                    for c, r in zip(_parsed_calls, _tc_results)
                                    if is_tool_error(r.output or r.error or "")
                                ]
                                if _tool_errors and not _autoheal_used:
                                    _autoheal_used = True
                                    _err_summary = "; ".join(f"{n}: {e[:200]}" for n, e in _tool_errors)
                                    logger.warning(
                                        "v16.4 Self-Healing: tool errors detected",
                                        errors=len(_tool_errors),
                                        summary=_err_summary[:200],
                                    )
                                    _fix_rule = await autonomous_reflection(
                                        task=prompt,
                                        code=response[:500],
                                        stderr=_err_summary,
                                        inference_fn=self._quick_inference,
                                    )
                                    if _fix_rule:
                                        _observation += (
                                            f"\n\n[SELF-HEALING — ОБНАРУЖЕНА ОШИБКА]\n"
                                            f"Ошибка: {_err_summary[:300]}\n"
                                            f"Правило фикса: {_fix_rule}"
                                        )
                                        if status_callback:
                                            await status_callback(
                                                role_name, display_model,
                                                f"🔄 Self-Healing: {_fix_rule[:80]}...",
                                            )
                            except Exception as _heal_err:
                                logger.debug("v16.4 tool error detection failed (non-fatal)", error=str(_heal_err))

                            # Strip raw tool-call XML from response so user never sees it
                            response = strip_tool_calls(response, _parsed_calls)
                            # Re-query the model with Observation context for a clean answer
                            _tc_followup = (
                                f"{step_prompt}\n\n"
                                f"[TOOL RESULTS]\n{_observation}\n\n"
                                "Используй результаты инструментов выше для финального ответа. "
                                "Не выводи XML-теги tool_call."
                            )
                            response = await self._call_vllm(
                                model, system_prompt, _tc_followup, role_name,
                                role_config, active_mcp,
                                preserve_think=preserve_think, json_schema=role_schema,
                            )
                        else:
                            # Роль не должна вызывать инструменты — просто стрипаем теги
                            logger.warning(
                                "Tool leakage stripped (non-eligible role)",
                                role=role_name, n_calls=len(_parsed_calls),
                                tools=[c.name for c in _parsed_calls],
                            )
                            response = strip_tool_calls(response, _parsed_calls)
                except Exception as _tc_err:
                    logger.debug("Tool call interception failed (non-fatal)", error=str(_tc_err))

                # --- GUARDRAIL VALIDATION WITH RETRY ---
                guardrail_fn = ROLE_GUARDRAILS.get(role_name)
                if guardrail_fn and not task_type:
                    # B3-fix: передаём task_hint для context-aware валидации (Analyst)
                    _guardrail_kwargs: Dict[str, Any] = {}
                    if role_name == "Analyst" and _yt_transcript_injected:
                        _guardrail_kwargs["task_hint"] = "youtube video"
                    for retry_i in range(GUARDRAIL_MAX_RETRIES):
                        is_valid, feedback = guardrail_fn(response, **_guardrail_kwargs)
                        if is_valid:
                            break
                        logger.warning(f"Guardrail failed for {role_name} (attempt {retry_i + 1}/{GUARDRAIL_MAX_RETRIES}): {feedback}")
                        if status_callback:
                            await status_callback(role_name, display_model, f"🔄 Гарантия качества: повтор {retry_i + 1} — {feedback[:60]}")
                        retry_prompt = f"{step_prompt}\n\n[GUARDRAIL FEEDBACK — исправь ответ]:\n{feedback}"
                        response = await self._call_vllm(
                            model, system_prompt, retry_prompt, role_name, role_config, active_mcp,
                            preserve_think=preserve_think, json_schema=role_schema
                        )

                # --- CODE STATIC ANALYSIS (Executor roles only) ---
                _validator_cfg = self.config.get("code_validator", {})
                if _validator_cfg.get("enabled", True) and role_name.startswith("Executor_") and not task_type:
                    try:
                        _cv_reports = await self.code_validator.validate_response(response)
                        _cv_fix_prompt = self.code_validator.build_fix_prompt(_cv_reports) if _cv_reports else ""
                        if _cv_fix_prompt:
                            _issues_count = sum(len(r.issues) for r in _cv_reports)
                            logger.warning(f"Code validation found {_issues_count} issues in {role_name} — auto-fix pass")
                            if status_callback:
                                await status_callback(role_name, display_model, f"🔍 Статический анализ: {_issues_count} проблем — исправляю...")
                            _cv_retry_prompt = f"{step_prompt}\n\n{_cv_fix_prompt}"
                            response = await self._call_vllm(
                                model, system_prompt, _cv_retry_prompt, role_name, role_config,
                                active_mcp, preserve_think=preserve_think, json_schema=role_schema,
                            )
                    except Exception as _cv_err:
                        logger.warning(f"CodeValidator error (skipping): {_cv_err}")

                # --- v16.4: General step error detection + self-healing retry ---
                if not _autoheal_used and response:
                    _resp_lower = (response or "").lower()
                    _has_error_markers = (
                        response.startswith("⚠️")
                        or "traceback" in _resp_lower
                        or "exception:" in _resp_lower
                        or "error:" in _resp_lower
                        or "failed to execute" in _resp_lower
                    )
                    if _has_error_markers:
                        _autoheal_used = True
                        _step_err = response[:500]
                        logger.warning(
                            "v16.4 Self-Healing: step error detected",
                            role=role_name,
                            error_preview=_step_err[:100],
                        )
                        try:
                            from src.pipeline._logic_provider import autonomous_reflection, get_recent_knowledge
                            _fix_rule = await autonomous_reflection(
                                task=prompt,
                                code=response[:500],
                                stderr=_step_err,
                                inference_fn=self._quick_inference,
                            )
                            if _fix_rule:
                                _fresh = get_recent_knowledge(max_age_seconds=60)
                                _heal_prompt = (
                                    f"{step_prompt}\n\n"
                                    f"[SELF-HEALING CONTEXT]\n{_fresh}\n\n"
                                    f"[FIX RULE]: {_fix_rule}\n\n"
                                    "Предыдущий ответ содержал ошибку. Используй правило фикса и исправь."
                                )
                                response = await self._call_vllm(
                                    model, system_prompt, _heal_prompt, role_name, role_config,
                                    active_mcp, preserve_think=preserve_think, json_schema=role_schema,
                                )
                                if status_callback:
                                    await status_callback(
                                        role_name, display_model,
                                        f"🔄 Self-Healing retry: {_fix_rule[:60]}...",
                                    )
                        except Exception as _heal_step_err:
                            logger.debug("v16.4 step self-healing failed (non-fatal)", error=str(_heal_step_err))

                self.last_loaded_model = model

            # --- HANDOFF AND ASK_USER INTERCEPTION ---
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            extracted_json_str = None
            if json_match:
                extracted_json_str = json_match.group(1)
            else:
                try:
                    _resp_stripped = (response or "").strip()
                    if _resp_stripped.startswith('{') or _resp_stripped.startswith('['):
                        json.loads(_resp_stripped)
                        extracted_json_str = _resp_stripped
                except (json.JSONDecodeError, AttributeError):
                    pass

            # AGGRESSIVE PARSER RETRY
            if not extracted_json_str and ("Planner" in role_name or "Foreman" in role_name):
                lower_resp = response.lower()
                if any(kw in lower_resp for kw in ["создай", "запиши", "выполни", "create", "write", "execute"]):
                    logger.warning(f"No JSON found from {role_name} but action keywords present. Forcing re-generation.")
                    if status_callback:
                        await status_callback(role_name, display_model, "Оркестратор забыл JSON. Требую по протоколу...")

                    retry_prompt = "Ошибка формата. Выдай только JSON-инструкцию для Исполнителя согласно протоколу."
                    retry_messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": step_prompt},
                        {"role": "assistant", "content": response},
                        {"role": "user", "content": retry_prompt}
                    ]
                    try:
                        if self.force_cloud:
                            new_response = await call_openrouter(
                                openrouter_config=self.openrouter_config,
                                vllm_url=self.vllm_url,
                                model=model,
                                fallback_model=role_config.get("fallback_model", model),
                                system_prompt=system_prompt,
                                user_prompt=step_prompt + "\n\n" + retry_prompt,
                                role_name=role_name,
                                role_config=role_config,
                                mcp_client=active_mcp,
                                config=self.config,
                            )
                        else:
                            _payload = {
                                "model": model,
                                "messages": retry_messages,
                                "stream": False,
                                "max_tokens": 2048,
                            }
                            async with aiohttp.ClientSession() as _sess:
                                async with _sess.post(f"{self.vllm_url}/chat/completions", json=_payload, timeout=aiohttp.ClientTimeout(total=60)) as retry_resp:
                                    if retry_resp.status == 200:
                                        r_data = await retry_resp.json()
                                        _raw = r_data.get("choices", [{}])[0].get("message", {}).get("content") or ""
                                        new_response = _raw.strip()
                                    else:
                                        new_response = ""
                        new_response = re.sub(r"<think>.*?</think>", "", (new_response or ""), flags=re.DOTALL)
                        new_response = re.sub(r"<think>.*$", "", new_response, flags=re.DOTALL).strip()
                        if new_response:
                            response += "\n\n[Correction]:\n" + new_response
                            json_match = re.search(r'```json\s*(.*?)\s*```', new_response, re.DOTALL)
                            if json_match:
                                extracted_json_str = json_match.group(1)
                            else:
                                try:
                                    if new_response.strip().startswith('{') or new_response.strip().startswith('['):
                                        json.loads(new_response.strip())
                                        extracted_json_str = new_response.strip()
                                except json.JSONDecodeError:
                                    pass
                    except Exception as e:
                        logger.error(f"Retry request failed: {e}")

            if extracted_json_str:
                try:
                    parsed_json = json.loads(extracted_json_str)
                    if isinstance(parsed_json, dict) and parsed_json.get("action") == "ask_user":
                        logger.info("Pipeline suspended for ask_user")
                        steps_results.append({"role": role_name, "model": model, "response": response})
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
                        steps_results.append({"role": role_name, "model": model, "response": response})
                        return {
                            "status": "create_offer",
                            "brigade": brigade,
                            "chain_executed": [s["role"] for s in steps_results],
                            "steps": steps_results,
                            "final_response": response + "\n\n[System]: Inventory verified. Proceeding to create_offer."
                        }

                    if "Planner" in role_name or "Foreman" in role_name:
                        did_handoff = await handle_planner_handoff(
                            self, extracted_json_str, role_name, model, brigade,
                            active_mcp, status_callback, steps_results, response,
                        )
                        if did_handoff:
                            break

                    # B1-fix: всегда сохраняем шаг в steps_results, даже если
                    # ответ содержит валидный JSON, не совпавший с action-паттерном.
                    # Без этого Analyst/Researcher/Summarizer молча терялись.
                    if not did_handoff:
                        steps_results.append({"role": role_name, "model": model, "response": response})

                except json.JSONDecodeError:
                    steps_results.append({"role": role_name, "model": model, "response": response})
            else:
                steps_results.append({"role": role_name, "model": model, "response": response})

            if did_handoff:
                break

            if status_callback and not is_final_step:
                step_preview = response[:120].replace('\n', ' ').strip()
                await status_callback(
                    role_name, display_model,
                    f"✅ Шаг {step_index + 1}/{len(chain)} ({role_name}) завершён. Передаю контекст дальше..."
                )

            try:
                import subprocess
                commit_msg = f"Auto-commit [PoW]: Pipeline step {role_name} ({model}) completed"
                subprocess.run(["git", "commit", "-am", commit_msg], cwd=os.path.dirname(__file__), capture_output=True)
            except Exception as e:
                logger.debug(f"Git auto-commit failed: {e}")

            context_briefing = compress_for_next_step(role_name, response)

            # v14.1: SLEA-RL — сохраняем step-level experience
            if self._supermemory and response and not response.startswith("⚠️"):
                try:
                    _step_reward = 0.7  # default for non-error steps
                    if "error" in response.lower() or "fail" in response.lower():
                        _step_reward = 0.3
                    self._supermemory.save_step_experience(
                        episode_id=f"run:{int(time.time())}",
                        step_index=step_index,
                        role=role_name,
                        action=prompt[:200],
                        observation=response[:300],
                        reward=_step_reward,
                    )
                except Exception as _slea_err:
                    logger.debug("SLEA-RL step save failed (non-fatal)", error=str(_slea_err))
            step_index += 1

        raw_response = steps_results[-1]["response"] if steps_results else ""
        final_response = clean_response_for_user(raw_response)

        if not final_response or final_response.startswith("⚠️"):
            logger.warning("Pipeline produced empty/error response, attempting Reflexion fallback")
            reflexion_answer = await self._reflexion_fallback(prompt, raw_response)
            if reflexion_answer:
                final_response = reflexion_answer
                steps_results.append({"role": "Reflexion_Fallback", "model": "reflexion", "response": reflexion_answer})

        if final_response and not final_response.startswith("⚠️"):
            try:
                const_result = await self._constitutional.check(prompt, final_response)
                if not const_result.safe and const_result.revised_response:
                    logger.warning("Constitutional check triggered revision", violations=const_result.violations)
                    final_response = const_result.revised_response
                    steps_results.append({"role": "Constitutional_Guard", "model": "constitutional", "response": final_response})
            except Exception as e:
                logger.warning("Constitutional check failed (non-fatal)", error=str(e))

            # --- v11.7: MARCH hallucination cross-verification ---
            if self._supermemory and len(steps_results) >= 2:
                try:
                    executor_resp = steps_results[-2]["response"] if len(steps_results) >= 2 else ""
                    archivist_resp = final_response
                    march_result = await self._march_protocol.cross_verify_agents(
                        executor_response=executor_resp,
                        archivist_response=archivist_resp,
                        memory=self._supermemory,
                        config=self.config,
                    )
                    total_claims = len(march_result.verified_claims) + len(march_result.discrepancies)
                    disc_rate = len(march_result.discrepancies) / max(total_claims, 1)
                    if not march_result.is_consistent:
                        logger.warning(
                            "MARCH cross-verification failed",
                            discrepancy_rate=disc_rate,
                            unverified=len(march_result.discrepancies),
                        )
                        if march_result.corrected_response:
                            final_response = march_result.corrected_response
                            steps_results.append({
                                "role": "MARCH_Verification",
                                "model": "march",
                                "response": final_response,
                            })
                    else:
                        logger.info("MARCH cross-verification passed", rate=disc_rate)
                except Exception as e:
                    logger.warning("MARCH verification failed (non-fatal)", error=str(e))

        # v14.0: SAGE — анализ низкокачественных шагов
        if steps_results:
            try:
                sage_result = self._sage.analyze_steps(steps_results, chain)
                if sage_result.needs_rebuild:
                    logger.warning(
                        "SAGE: low-quality step detected — correction saved",
                        step=sage_result.low_score_step,
                        score=sage_result.detected_score,
                        suggested_chain=sage_result.suggested_chain,
                    )
                    if self._supermemory:
                        self._sage.save_to_memory(self._supermemory, sage_result)
            except Exception as _sage_err:
                logger.debug("SAGE analysis failed (non-fatal)", error=str(_sage_err))

        # v14.0: Complementary RL — сохраняем траекторию успешных сложных задач
        _complexity = classify_complexity(prompt)
        _is_success = final_response and not final_response.startswith("⚠️")
        if _is_success and _complexity in ("complex", "extreme") and self._supermemory:
            try:
                asyncio.ensure_future(
                    _async_save_trajectory(
                        self._supermemory, prompt, chain, _complexity,
                        steps_results, final_response,
                    )
                )
            except Exception as _trl_err:
                logger.debug("Trajectory save failed (non-fatal)", error=str(_trl_err))

        # v14.1: Counterfactual Credit — persist stats to SuperMemory
        if self._supermemory:
            try:
                self._counterfactual.save_to_memory(self._supermemory)
            except Exception as _cc_err:
                logger.debug("Counterfactual credit save failed (non-fatal)", error=str(_cc_err))

        # v16.0 & v16.1: Learning Log and Dynamic Auto-Tagging
        try:
            from src.pipeline._logic_provider import record_learning, auto_tag_snippet
            if final_response and not final_response.startswith("⚠️"):
                record_learning(prompt, "", final_response)
                auto_tag_snippet(prompt, final_response)
            else:
                record_learning(prompt, final_response, "Execution failed or produced warnings")
        except Exception as _ll_err:
            logger.debug("Obsidian LearningLog / AutoTag write failed", error=str(_ll_err))

        logger.info(f"Pipeline COMPLETE: brigade={brigade}, steps={len(steps_results)}")

        try:
            validated = PipelineResult(
                final_response=final_response,
                brigade=brigade,
                chain_executed=[s["role"] for s in steps_results],
                steps=[PipelineStepResult(**s) for s in steps_results],
                status="completed",
            )
            return validated.model_dump()
        except Exception as val_err:
            logger.warning("Pipeline result validation failed (returning raw)", error=str(val_err))
            return {
                "final_response": final_response,
                "brigade": brigade,
                "chain_executed": [s["role"] for s in steps_results],
                "steps": steps_results,
                "status": "completed",
            }

    async def _run_single_step(self, role_name, step_index, chain_len, brigade, prompt, context_briefing, status_callback=None, task_type=None) -> str:
        """Run a single pipeline step (used for parallel Executor dispatch)."""
        return await run_single_step(
            role_name=role_name, step_index=step_index, chain_len=chain_len,
            brigade=brigade, prompt=prompt, context_briefing=context_briefing,
            config=self.config, framework_root=self._framework_root,
            openclaw_mcp=self.openclaw_mcp, dmarket_mcp=self.dmarket_mcp,
            display_model_fn=self._display_model, call_vllm_fn=self._call_vllm,
            status_callback=status_callback, task_type=task_type,
        )

    def _display_model(self, role_config: Dict[str, Any], fallback_model: str = "") -> str:
        if self.openrouter_enabled:
            or_model = role_config.get("openrouter_model")
            if or_model:
                return or_model
        return fallback_model or role_config.get("model", "unknown")

    # ------------------------------------------------------------------
    # v13.2: Ensemble Voting — parallel Executor instances with consensus
    # ------------------------------------------------------------------

    async def _ensemble_vote(
        self,
        role_name: str,
        model: str,
        system_prompt: str,
        step_prompt: str,
        role_config: Dict[str, Any],
        active_mcp,
        n_instances: int = 2,
        auditor_role_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        return await ensemble_vote(
            role_name=role_name, model=model, system_prompt=system_prompt,
            step_prompt=step_prompt, role_config=role_config, active_mcp=active_mcp,
            call_vllm_fn=self._call_vllm, counterfactual=self._counterfactual,
            n_instances=n_instances, auditor_role_config=auditor_role_config,
        )

    async def _call_vllm(self, model, system_prompt, user_prompt, role_name, role_config, mcp_client, preserve_think=False, json_schema=None) -> str:
        return await call_vllm_inference(
            model=model, system_prompt=system_prompt, user_prompt=user_prompt,
            role_name=role_name, role_config=role_config, mcp_client=mcp_client,
            vllm_url=self.vllm_url, openrouter_enabled=self.openrouter_enabled,
            openrouter_config=self.openrouter_config, smart_router=self._smart_router,
            config=self.config, vllm_manager=self.vllm_manager,
            metrics_collector=self.metrics_collector,
            preserve_think=preserve_think, json_schema=json_schema,
        )

    # ------------------------------------------------------------------
    # v14.4: Multi-Task parallel execution
    # ------------------------------------------------------------------

    async def _execute_multi_task(
        self,
        sub_tasks: list[tuple[str, str]],
        original_prompt: str,
        max_steps: int,
        status_callback,
    ) -> Dict[str, Any]:
        """Run decomposed sub-tasks concurrently, each routed to its brigade."""
        return await execute_multi_task(
            sub_tasks=sub_tasks, original_prompt=original_prompt,
            max_steps=max_steps, status_callback=status_callback,
            execute_fn=self.execute,
        )

    async def _force_unload(self, model: str):
        await force_unload(model)

    async def execute_stream(self, prompt, brigade="Dmarket", max_steps=5, status_callback=None, task_type=None):
        return await execute_stream(self, prompt, brigade, max_steps, status_callback, task_type)

    @asynccontextmanager
    async def _vram_protection(self, target_model: str, prev_model: Optional[str]):
        if self.force_cloud:
            yield
        else:
            async with vram_protection(target_model, prev_model):
                yield
