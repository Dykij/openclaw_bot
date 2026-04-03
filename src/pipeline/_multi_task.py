"""
Pipeline Multi-Task Decomposer — prompt decomposition and parallel execution.
Extracted from _core.py for modularity.
"""

import asyncio
import re
from typing import Any, Callable, Dict

import structlog

logger = structlog.get_logger(__name__)


# v14.4: Multi-Task Decomposer regex
# Atomic-style match: capture number + body up to next numbered item or end.
# Avoids backtracking on long whitespace runs.
_NUMBERED_RE = re.compile(
    r"(?:^|\n)\s{0,10}(\d+)\.\s+(.+?)(?=\n\s{0,10}\d+\.\s|\Z)",
    re.DOTALL,
)

# v15.3: Action verbs that signal a new sub-task in unnumbered paragraphs
_ACTION_VERBS_RE = re.compile(
    r"^(?:Сделай|Проанализируй|Напиши|Найди|Создай|Проверь|Check|Create|Write|Find|Analyze|Build|Implement|Audit|Auditor:)",
    re.IGNORECASE,
)
# Minimum prompt length to attempt semantic paragraph splitting
_SEMANTIC_MIN_LEN = 300

# Keyword → brigade mapping (reused from intent_classifier)
_BRIGADE_KEYWORDS: dict[str, list[str]] = {
    "Dmarket-Dev": [
        "dmarket", "buy", "sell", "trade", "price", "skin", "inventory",
        "купить", "продать", "торговля", "скин", "инвентарь", "арбитраж",
        "pyo3", "подпис", "hft", "latency",
    ],
    "Research-Ops": [
        "research", "найди", "поищи", "youtube", "видео", "video",
        "url", "http", "ссылк", "статью", "интернет", "анализ",
        "vision", "проанализируй",
    ],
    "OpenClaw-Core": [
        "config", "pipeline", "model", "bot", "openclaw", "gateway",
        "конфиг", "бригад", "бот", "память", "memory", "mcp",
        "code", "python", "rust", "напиши", "функци",
    ],
}


def _route_subtask(text: str) -> str:
    """Route a single sub-task to the most relevant brigade by keywords."""
    lower = text.lower()
    scores: dict[str, int] = {}
    for brigade, keywords in _BRIGADE_KEYWORDS.items():
        scores[brigade] = sum(1 for kw in keywords if kw in lower)
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    return best if scores[best] > 0 else "OpenClaw-Core"


def _decompose_multi_task(prompt: str) -> list[tuple[str, str]]:
    """Split a prompt into (sub_task_text, brigade) pairs.

    v15.3: Two-pass strategy:
    1. Try numbered-list regex ("1. ... 2. ...").
    2. Fallback: semantic paragraph splitting — split on \\n\\n or \\n,
       keeping paragraphs that start with an action verb as separate tasks.

    Returns an empty list if the prompt doesn't look like a multi-task.
    """
    # --- Pass 1: numbered-list regex ---
    matches = _NUMBERED_RE.findall(prompt)
    if len(matches) >= 2:
        sub_tasks: list[tuple[str, str]] = []
        for _num, body in matches:
            body = body.strip()
            if body:
                brigade = _route_subtask(body)
                sub_tasks.append((body, brigade))
        return sub_tasks

    # --- Pass 2: semantic paragraph splitting (v15.3) ---
    # Strip any [CHAT HISTORY] prefix before analysing paragraphs
    analysis_text = prompt
    if "[CURRENT TASK]:" in prompt:
        analysis_text = prompt.split("[CURRENT TASK]:", 1)[1].strip()

    if len(analysis_text) < _SEMANTIC_MIN_LEN:
        return []

    # Split on double-newline first; fallback to single-newline
    paragraphs = [p.strip() for p in re.split(r"\n\n+", analysis_text) if p.strip()]
    if len(paragraphs) < 2:
        paragraphs = [p.strip() for p in analysis_text.split("\n") if p.strip()]

    # Keep only paragraphs that look like actionable tasks (action verb at start)
    action_paragraphs: list[str] = []
    # First paragraph is always the context/intro — include it as a task too
    # if it contains a URL or is long enough
    for para in paragraphs:
        if _ACTION_VERBS_RE.search(para):
            action_paragraphs.append(para)
        elif re.search(r"https?://", para) and len(para) > 40:
            # URL-bearing paragraphs are implicit research tasks
            action_paragraphs.append(para)

    if len(action_paragraphs) < 2:
        return []

    sub_tasks = []
    for para in action_paragraphs:
        brigade = _route_subtask(para)
        sub_tasks.append((para, brigade))
    logger.info("Semantic decomposer activated (v15.3)",
                n_paragraphs=len(paragraphs), n_tasks=len(sub_tasks))
    return sub_tasks


async def execute_multi_task(
    *,
    sub_tasks: list[tuple[str, str]],
    original_prompt: str,
    max_steps: int,
    status_callback,
    execute_fn: Callable,
) -> Dict[str, Any]:
    """Run decomposed sub-tasks concurrently, each routed to its brigade."""

    # v15.2: Extract [CHAT HISTORY] from original prompt so each sub-task
    # retains multi-turn context (prevents amnesia during decomposition).
    _history_block = ""
    if "[CURRENT TASK]:" in original_prompt:
        _history_block = original_prompt.split("[CURRENT TASK]:")[0] + "[CURRENT TASK]:\n"

    shared_observations: dict = {}

    async def _run_one(idx: int, text: str, brigade: str) -> Dict[str, Any]:
        if status_callback:
            await status_callback(
                "Decomposer", "system",
                f"🔀 Подзадача {idx + 1}/{len(sub_tasks)} → {brigade}",
            )
        # Prepend chat history to each sub-task
        enriched_text = _history_block + text if _history_block else text
        return await execute_fn(
            prompt=enriched_text,
            brigade=brigade,
            max_steps=max_steps,
            status_callback=status_callback,
            shared_observations=shared_observations,
        )

    tasks = [
        _run_one(i, text, brigade)
        for i, (text, brigade) in enumerate(sub_tasks)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge results into one response
    merged_parts: list[str] = []
    all_steps: list[dict] = []
    all_chains: list[str] = []
    for i, (text, brigade) in enumerate(sub_tasks):
        res = results[i]
        if isinstance(res, Exception):
            merged_parts.append(f"**Задача {i + 1}** ({brigade}): ⚠️ Ошибка: {res}")
        else:
            resp = res.get("final_response", "")
            merged_parts.append(f"**Задача {i + 1}** ({brigade}):\n{resp}")
            all_steps.extend(res.get("steps", []))
            all_chains.extend(res.get("chain_executed", []))

    final = "\n\n---\n\n".join(merged_parts)
    logger.info(
        "Multi-task decomposer complete",
        n_subtasks=len(sub_tasks),
        n_steps=len(all_steps),
    )
    return {
        "final_response": final,
        "brigade": "Multi-Task",
        "chain_executed": all_chains,
        "steps": all_steps,
        "status": "completed",
        "meta": {"decomposed": True, "n_subtasks": len(sub_tasks)},
    }
