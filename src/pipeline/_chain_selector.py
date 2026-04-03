"""
Pipeline Chain Selector — static and dynamic chain selection.
Extracted from _core.py for modularity.
"""

from typing import Any, Callable, Dict, List, Tuple

import structlog

from src.pipeline._lats_search import classify_complexity

logger = structlog.get_logger(__name__)


def get_chain(
    config: Dict[str, Any],
    default_chains: Dict[str, List[str]],
    brigade: str,
) -> List[str]:
    """Return the pipeline chain for a brigade (static config)."""
    brigade_config = config.get("brigades", {}).get(brigade, {})
    if "pipeline" in brigade_config:
        return brigade_config["pipeline"]
    available_roles = set(brigade_config.get("roles", {}).keys())
    default_chain = default_chains.get(brigade, ["Planner"])
    return [role for role in default_chain if role in available_roles]


async def get_chain_dynamic(
    *,
    prompt: str,
    brigade: str,
    config: Dict[str, Any],
    default_chains: Dict[str, List[str]],
    aflow_engine,
    prorl_engine,
    get_chain_fn: Callable[[str], List[str]],
    max_steps: int = 7,
) -> Tuple[List[str], str]:
    """v13.2 AFlow: generate optimal chain for this prompt.

    Returns (chain, source) where source is "heuristic"|"llm"|"lats"|"fallback".
    Falls back to static get_chain() on any error.
    """
    # Если в конфиге явно задан pipeline — уважаем его (не override)
    brigade_config = config.get("brigades", {}).get(brigade, {})
    if "pipeline" in brigade_config:
        return brigade_config["pipeline"][:max_steps], "config"

    available_roles = list(brigade_config.get("roles", {}).keys())
    if not available_roles:
        return get_chain_fn(brigade)[:max_steps], "fallback"

    try:
        aflow_result = await aflow_engine.generate_chain(
            prompt=prompt,
            brigade=brigade,
            available_roles=available_roles,
            config=config,
            max_chain_len=max_steps,
        )
        chain = aflow_result.chain or get_chain_fn(brigade)

        # v14.1: ProRL — evaluate AFlow chain vs static fallback
        static_chain = get_chain_fn(brigade)[:max_steps]
        _complexity = classify_complexity(prompt)
        try:
            prorl_result = prorl_engine.evaluate_candidates(
                candidates=[
                    (chain[:max_steps], aflow_result.source),
                    (static_chain, "static"),
                ],
                complexity=_complexity,
            )
            chain = prorl_result.selected_chain
            source = prorl_result.selected_source
            logger.info(
                "ProRL: chain selected",
                chain=chain, source=source,
                score=prorl_result.best_score,
            )
            return chain, source
        except Exception as _prorl_err:
            logger.debug("ProRL evaluation failed (non-fatal)", error=str(_prorl_err))

        logger.info(
            "AFlow chain generated",
            chain=chain,
            source=aflow_result.source,
            confidence=round(aflow_result.confidence, 2),
        )
        return chain[:max_steps], aflow_result.source
    except Exception as e:
        logger.warning("AFlow chain generation failed, using static chain", error=str(e))
        return get_chain_fn(brigade)[:max_steps], "fallback"
