"""
Pipeline Ensemble Voting — parallel Executor instances with consensus.
Extracted from _core.py for modularity.
"""

import asyncio
import re
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


async def ensemble_vote(
    *,
    role_name: str,
    model: str,
    system_prompt: str,
    step_prompt: str,
    role_config: Dict[str, Any],
    active_mcp,
    call_vllm_fn: Callable,
    counterfactual,
    n_instances: int = 2,
    auditor_role_config: Optional[Dict[str, Any]] = None,
) -> str:
    """Run N Executor instances in parallel with temperature diversity,
    then select the best response via Auditor consensus scoring.

    v13.2: uses asyncio.TaskGroup for parallel inference.
    - Instance 0: temperature=0.7 (balanced)
    - Instance 1: temperature=1.0 (creative / alternative view)
    - Auditor (if available): scores all candidates and picks winner
      or synthesises a final composite answer.

    Falls back to single-instance call on any errors.
    """
    temperatures = [0.7, 1.0, 0.5][:n_instances]

    async def _run_at_temp(temp: float) -> str:
        # Patch role_config temperature inline — non-destructive copy
        patched_config = dict(role_config)
        patched_config["temperature"] = temp
        try:
            return await call_vllm_fn(
                model, system_prompt, step_prompt,
                role_name, patched_config, active_mcp,
                preserve_think=False,
            )
        except Exception as e:
            logger.warning("Ensemble instance failed", temp=temp, error=str(e))
            return ""

    # Launch all instances concurrently
    tasks = [_run_at_temp(t) for t in temperatures]
    candidates: List[str] = []
    try:
        async with asyncio.TaskGroup() as tg:
            futures = [tg.create_task(_run_at_temp(t)) for t in temperatures]
        candidates = [f.result() for f in futures if f.result()]
    except* Exception as eg:
        logger.warning("Ensemble TaskGroup error", errors=str(eg))
        # Graceful fallback via gather
        raw = await asyncio.gather(*tasks, return_exceptions=True)
        candidates = [r for r in raw if isinstance(r, str) and r]

    if not candidates:
        logger.warning("Ensemble: all instances failed, single fallback")
        return await call_vllm_fn(
            model, system_prompt, step_prompt, role_name, role_config, active_mcp,
        )

    if len(candidates) == 1:
        return candidates[0]

    # --- Auditor consensus scoring ---
    auditor_cfg = auditor_role_config or {}
    auditor_model = auditor_cfg.get("model") or auditor_cfg.get("openrouter_model") or model

    candidates_block = "\n\n".join(
        f"[CANDIDATE {i + 1}]:\n{c[:1500]}"
        for i, c in enumerate(candidates)
    )
    vote_prompt = (
        f"You are an expert judge. The following are {len(candidates)} candidate responses "
        f"to the same task. Analyse each, then either:\n"
        f"a) Select the best candidate verbatim (output: 'WINNER: <N>'), or\n"
        f"b) Synthesise a superior composite answer using the best parts.\n\n"
        f"TASK:\n{step_prompt[:600]}\n\n"
        f"{candidates_block}\n\n"
        f"Your verdict (winner or composite):"
    )
    vote_system = (
        "You are a senior technical reviewer. Evaluate response quality, correctness, "
        "completeness and absence of hallucinations. Output the best answer directly."
    )

    try:
        verdict = await call_vllm_fn(
            auditor_model,
            vote_system,
            vote_prompt,
            "Ensemble_Auditor",
            auditor_cfg or role_config,
            active_mcp,
        )
        # If verdict references a specific winner, return that candidate
        m = re.search(r'WINNER:\s*(\d+)', verdict or "")
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(candidates):
                logger.info("Ensemble: Auditor selected winner", idx=idx + 1)
                # v14.1: Counterfactual Credit — record vote outcome
                try:
                    counterfactual.record_vote(
                        role=role_name, temperatures=temperatures,
                        candidates=candidates, winner_index=idx,
                    )
                except Exception:
                    pass
                return candidates[idx]
        # Otherwise return the synthesised composite
        if verdict and len(verdict.strip()) > 30:
            logger.info("Ensemble: Auditor synthesised composite answer")
            # v14.1: Counterfactual Credit — composite = first candidate wins by default
            try:
                counterfactual.record_vote(
                    role=role_name, temperatures=temperatures,
                    candidates=candidates, winner_index=0,
                )
            except Exception:
                pass
            return verdict
    except Exception as e:
        logger.warning("Ensemble Auditor failed, using longest candidate", error=str(e))

    # Last resort: return longest (most complete) candidate
    return max(candidates, key=len)
