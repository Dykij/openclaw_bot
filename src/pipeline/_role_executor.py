"""
Pipeline Role Executor — single-step and vLLM inference logic.
Extracted from _core.py for modularity.
"""

import time
from typing import Any, Dict, Optional

import structlog

from src.ai.inference._shared import RoutingTask
from src.ai.inference.metrics import InferenceMetricsCollector
from src.openrouter_client import call_openrouter
from src.pipeline_schemas import ROLE_TOKEN_BUDGET
from src.pipeline_utils import build_role_prompt
from src.vllm_inference import call_vllm

logger = structlog.get_logger(__name__)


async def run_single_step(
    *,
    role_name: str,
    step_index: int,
    chain_len: int,
    brigade: str,
    prompt: str,
    context_briefing: str,
    config: Dict[str, Any],
    framework_root: str,
    openclaw_mcp,
    dmarket_mcp,
    display_model_fn,
    call_vllm_fn,
    status_callback=None,
    task_type: Optional[str] = None,
) -> str:
    """Run a single pipeline step (used for parallel Executor dispatch)."""
    role_config = config.get("brigades", {}).get(brigade, {}).get("roles", {}).get(role_name, {})
    if not role_config:
        return f"⚠️ Role '{role_name}' not found in config."
    model = role_config.get("model", "meta-llama/llama-3.3-70b-instruct:free")
    display_model = display_model_fn(role_config, model)
    system_prompt = build_role_prompt(role_name, role_config, framework_root)
    step_prompt = (
        f"[PIPELINE CONTEXT from previous step]\n{context_briefing}\n\n"
        f"[ORIGINAL USER TASK]\n{prompt}\n\n"
        f"Based on the above context, perform your role as {role_name}."
    )
    if status_callback:
        await status_callback(role_name, display_model, f"⚡ Параллельно: {role_name} работает...")
    active_mcp = openclaw_mcp if brigade == "OpenClaw" else dmarket_mcp
    return await call_vllm_fn(model, system_prompt, step_prompt, role_name, role_config, active_mcp)


async def call_vllm_inference(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    role_name: str,
    role_config: Dict[str, Any],
    mcp_client,
    vllm_url: str,
    openrouter_enabled: bool,
    openrouter_config: Dict[str, Any],
    smart_router,
    config: Dict[str, Any],
    vllm_manager,
    metrics_collector: InferenceMetricsCollector,
    preserve_think: bool = False,
    json_schema=None,
) -> str:
    """Perform inference via OpenRouter or local vLLM."""
    or_model = role_config.get("openrouter_model")
    if not or_model and smart_router:
        task_type = "general"
        lower_prompt = user_prompt[:500].lower()
        if any(kw in lower_prompt for kw in ["код", "code", "функци", "class", "def ", "import "]):
            task_type = "code"
        elif any(kw in lower_prompt for kw in ["math", "матем", "вычисл", "формул"]):
            task_type = "math"
        elif any(kw in lower_prompt for kw in ["напиши", "сочини", "creativ", "story", "стих"]):
            task_type = "creative"
        routed_model = smart_router.route(RoutingTask(prompt=user_prompt[:300], task_type=task_type))
        if routed_model:
            or_model = routed_model
            logger.info("SmartRouter selected model", model=or_model, task_type=task_type, role=role_name)

    fallback = role_config.get("fallback_model", model)

    # --- AUDITOR ISOLATION: truncate context + fallback model ---
    is_auditor = "Auditor" in role_name
    if is_auditor:
        auditor_budget = ROLE_TOKEN_BUDGET.get("Auditor", 1536)
        max_prompt_chars = auditor_budget * 4  # ~4 chars per token
        if len(user_prompt) > max_prompt_chars:
            logger.warning(
                "Auditor context truncated",
                original_chars=len(user_prompt),
                budget_chars=max_prompt_chars,
            )
            user_prompt = user_prompt[:max_prompt_chars] + "\n\n[... контекст сокращён для Auditor ...]"

    t0 = time.monotonic()
    if openrouter_enabled and or_model:
        result = await call_openrouter(
            openrouter_config=openrouter_config,
            vllm_url=vllm_url,
            model=or_model,
            fallback_model=fallback,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            role_name=role_name,
            role_config=role_config,
            mcp_client=mcp_client,
            config=config,
            vllm_manager=vllm_manager,
            preserve_think=preserve_think,
            json_schema=json_schema,
        )
    else:
        result = await call_vllm(
            vllm_url=vllm_url,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            role_name=role_name,
            role_config=role_config,
            mcp_client=mcp_client,
            config=config,
            vllm_manager=vllm_manager,
            preserve_think=preserve_think,
            json_schema=json_schema,
        )
    elapsed_ms = (time.monotonic() - t0) * 1000

    used_model = or_model or model
    from src.utils.token_counter import estimate_tokens as _est_tokens
    prompt_tokens_est = _est_tokens(system_prompt) + _est_tokens(user_prompt)
    completion_tokens_est = _est_tokens(result)
    metrics_collector.record_inference(
        model=used_model,
        prompt_tokens=prompt_tokens_est,
        completion_tokens=completion_tokens_est,
        total_latency_ms=elapsed_ms,
        first_token_ms=elapsed_ms * 0.15,
    )
    logger.debug("Inference metrics recorded", model=used_model, latency_ms=round(elapsed_ms), role=role_name)
    return result
