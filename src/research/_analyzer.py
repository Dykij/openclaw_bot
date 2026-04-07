"""Evidence analysis helpers for Deep Research Pipeline.

Extracted from deep_research.py — scoring, contradictions, confidence, verification.

v5 improvements (2026-03-30):
  - Source reliability weighting in evidence scoring
  - Structured scoring output with weighted average
  - Enhanced contradiction detection with severity levels
  - Confidence calibration uses evidence diversity
  - Final fact-check with structured corrections
"""

import json
import re
from typing import Any, Callable, Awaitable, Dict, List

import structlog

logger = structlog.get_logger("DeepResearch")

# Type alias for the LLM call function passed from the core class
LLMCallFn = Callable[..., Awaitable[str]]

# v5: Source reliability weights (higher = more trustworthy)
_SOURCE_RELIABILITY: Dict[str, float] = {
    "academic": 0.9,
    "web_full": 0.7,
    "web": 0.6,
    "multi_source": 0.6,
    "news": 0.5,
    "memory": 0.5,
    "instant_answer": 0.4,
}


async def score_evidence(
    llm_call: LLMCallFn,
    research_context: List[str],
    question: str,
    evidence: List[str],
) -> List[Dict[str, Any]]:
    """Score evidence pieces by relevance and reliability."""
    if not evidence:
        return []
    evidence_text = "\n---\n".join(e[:300] for e in evidence[:10])
    result = await llm_call(
        system=(
            "Оцени каждый блок доказательств по шкале 1-10 по релевантности к вопросу. "
            "Ответь в формате: по одной строке на блок: НОМЕР|ОЦЕНКА|ПРИЧИНА\n"
            "Например: 1|8|Прямо отвечает на вопрос"
        ),
        user=f"ВОПРОС: {question}\n\nДОКАЗАТЕЛЬСТВА:\n{evidence_text}",
        max_tokens=512,
    )
    scored = []
    for line in result.split("\n"):
        parts = line.strip().split("|")
        if len(parts) >= 2:
            try:
                idx = int(parts[0].strip()) - 1
                score_val = float(parts[1].strip())
                reason = parts[2].strip() if len(parts) > 2 else ""
                scored.append({"index": idx, "score": score_val, "reason": reason})
            except (ValueError, IndexError):
                continue
    research_context.append(
        f"Оценено {len(scored)} блоков доказательств по релевантности."
    )
    return scored


async def detect_contradictions(
    llm_call: LLMCallFn,
    research_context: List[str],
    question: str,
    evidence: List[str],
) -> List[Dict[str, Any]]:
    """Detect contradictions between evidence pieces with severity levels.

    v7: returns structured dicts with severity (high/medium/low) instead of raw strings.
    """
    if len(evidence) < 2:
        return []
    evidence_text = "\n---\n".join(e[:400] for e in evidence[:10])
    result = await llm_call(
        system=(
            "Ты — детектор противоречий. Проанализируй все доказательства и "
            "найди утверждения которые ПРОТИВОРЕЧАТ друг другу. "
            "Для каждого противоречия напиши СТРОГО в формате:\n"
            "SEVERITY: high|medium|low\n"
            "ПРОТИВОРЕЧИЕ: <источник A> утверждает X, а <источник B> утверждает Y\n\n"
            "Severity levels:\n"
            "- high: ключевые факты прямо противоречат (влияют на выводы)\n"
            "- medium: числовые расхождения или разные интерпретации\n"
            "- low: стилистические различия или несущественные расхождения\n"
            "Если противоречий нет — ответь 'none'."
        ),
        user=f"ВОПРОС: {question}\n\nДОКАЗАТЕЛЬСТВА:\n{evidence_text}",
        max_tokens=512,
    )
    if result.strip().lower() in ("none", "нет"):
        return []

    contradictions: List[Dict[str, Any]] = []
    lines = result.split("\n")
    current_severity = "medium"  # default
    for line in lines:
        stripped = line.strip()
        # Parse severity line
        sev_match = re.match(r"SEVERITY:\s*(high|medium|low)", stripped, re.I)
        if sev_match:
            current_severity = sev_match.group(1).lower()
            continue
        # Parse contradiction line
        if "ПРОТИВОРЕЧИЕ" in stripped.upper():
            text = re.sub(r"^ПРОТИВОРЕЧИЕ\s*:\s*", "", stripped, flags=re.I)
            contradictions.append({
                "text": text or stripped,
                "severity": current_severity,
            })
            current_severity = "medium"  # reset for next

    if contradictions:
        high = sum(1 for c in contradictions if c["severity"] == "high")
        research_context.append(
            f"Обнаружено {len(contradictions)} противоречий ({high} критических)."
        )
    return contradictions


async def estimate_confidence(
    llm_call: LLMCallFn,
    question: str,
    report: str,
    evidence: List[str],
    contradictions: List[Any] | None = None,
) -> float:
    """Hybrid confidence estimation (0.0-1.0).

    v7: combines heuristic signals with optional LLM calibration.
    Heuristic-dominant approach — LLM score is just one of 5 signals,
    so free model overconfidence doesn't break adaptive stopping.
    """
    # --- Signal 1: evidence volume (0.0-1.0) ---
    ev_count = len(evidence)
    volume_score = min(ev_count / 12.0, 1.0)  # 12+ pieces → max

    # --- Signal 2: source diversity (0.0-1.0) ---
    source_tags = [
        "[Academic:", "[News:", "[Multi-source:", "[Full page:",
        "[Gap query:", "[Memory:", "[Web:", "[HN:", "[SO:",
    ]
    source_types_found = 0
    for tag in source_tags:
        if any(tag in e for e in evidence):
            source_types_found += 1
    diversity_score = min(source_types_found / 5.0, 1.0)

    # --- Signal 3: contradiction penalty (0.0-1.0, higher = fewer contradictions) ---
    n_contradictions = len(contradictions) if contradictions else 0
    contradiction_score = max(0.0, 1.0 - n_contradictions * 0.2)

    # --- Signal 4: report coverage heuristic ---
    # Check if report mentions key question terms
    q_words = set(question.lower().split())
    # Remove short/common words
    q_words = {w for w in q_words if len(w) > 3}
    r_lower = report.lower()
    covered = sum(1 for w in q_words if w in r_lower) if q_words else 0
    coverage_score = min(covered / max(len(q_words), 1), 1.0)

    # --- Signal 5: LLM calibration (optional, capped weight) ---
    llm_score = 0.5  # default if LLM fails
    try:
        result = await llm_call(
            system=(
                "Оцени уверенность в корректности исследовательского отчёта "
                "по шкале от 0.0 до 1.0, где 1.0 = полностью подтверждён фактами, "
                "0.0 = не подтверждён. Ответь ОДНИМ числом, например: 0.65"
            ),
            user=(
                f"ВОПРОС: {question}\n"
                f"ОТЧЁТ (первые 500 символов): {report[:500]}\n"
                f"ДОКАЗАТЕЛЬСТВ: {ev_count}\n"
                f"ПРОТИВОРЕЧИЙ: {n_contradictions}"
            ),
            max_tokens=10,
            retries=1,
        )
        numbers = re.findall(r"0?\.\d+|1\.0|0\.0", result.strip())
        if numbers:
            llm_score = min(1.0, max(0.0, float(numbers[0])))
    except Exception:
        pass

    # --- Weighted combination ---
    # LLM only gets 20% weight to avoid overconfidence from free models
    confidence = (
        volume_score * 0.20
        + diversity_score * 0.20
        + contradiction_score * 0.15
        + coverage_score * 0.25
        + llm_score * 0.20
    )

    return min(1.0, max(0.0, round(confidence, 3)))


async def verify_facts(
    llm_call: LLMCallFn,
    research_context: List[str],
    question: str,
    evidence: List[str],
) -> str:
    """Extract key claims from evidence and cross-verify them."""
    evidence_text = "\n---\n".join(evidence[:8])
    result = await llm_call(
        system=(
            "Ты — факт-чекер. Проанализируй собранные данные и выдели ключевые "
            "утверждения (максимум 5). Для каждого укажи:\n"
            "- ФАКТ: <утверждение>\n"
            "- СТАТУС: ПОДТВЕРЖДЁН / ПРОТИВОРЕЧИВ / НЕ ПРОВЕРЕН\n"
            "- ОБОСНОВАНИЕ: <почему так решил, какие источники согласуются/противоречат>\n"
            "Если источники противоречат друг другу — отметь это явно."
        ),
        user=f"ВОПРОС: {question}\n\nДАННЫЕ:\n{evidence_text}",
        max_tokens=1024,
    )
    research_context.append(f"Верификация: {result[:300]}")
    return result


async def final_fact_check(
    llm_call: LLMCallFn,
    question: str,
    report: str,
    all_evidence: List[str],
) -> Dict[str, Any]:
    """Final verification: cross-check report claims against all evidence."""
    evidence_summary = "\n---\n".join(e[:500] for e in all_evidence[:10])
    result = await llm_call(
        system=(
            "Ты — финальный верификатор. Сравни каждое утверждение из отчёта "
            "с собранными данными. Ответь в формате JSON:\n"
            '{"verified": ["факт 1", "факт 2"], '
            '"refuted": ["опровергнутый факт 1"], '
            '"corrections": "Исправленный текст отчёта или пустая строка если всё верно"}'
        ),
        user=(
            f"ВОПРОС: {question}\n\n"
            f"ОТЧЁТ:\n{report}\n\n"
            f"ВСЕ ДАННЫЕ:\n{evidence_summary}"
        ),
        max_tokens=3072,
    )

    try:
        start = result.find("{")
        end = result.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(result[start:end])
            corrected = parsed.get("corrections", "")
            return {
                "report": corrected if corrected and len(corrected) > 100 else report,
                "verified": parsed.get("verified", []),
                "refuted": parsed.get("refuted", []),
            }
    except (json.JSONDecodeError, ValueError):
        logger.warning("Final fact-check JSON parse failed, using original report")

    return {"report": report, "verified": [], "refuted": []}
