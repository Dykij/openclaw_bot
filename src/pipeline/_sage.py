"""SAGE — Self-Evolution for LLM Reasoning in OpenClaw v14.0.

Reference:
- Peng et al., "SAGE: Multi-Agent Self-Evolution for LLM Reasoning",
  arXiv:2603.15255 (2026)

Механика:
- Анализирует успешные и провальные ветки LATS/AFlow.
- Если Auditor выдаёт низкий балл → генерирует «рекомендацию по исправлению
  логики» → сохраняет в метаданные сессии → предлагает перестроение цепочки.
- Всё через SuperMemory; никаких live LLM вызовов без явного флага.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

from src.llm.gateway import route_llm

logger = structlog.get_logger("SAGE")

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# Auditor-score слова/маркеры низкого качества (парсим из текстового ответа)
_LOW_QUALITY_MARKERS: tuple[re.Pattern, ...] = (
    re.compile(r"\b(неверно|ошибка|некорректно|плохо|провал|неправильно|wrong|incorrect|failed|poor|bad)\b", re.I),
    re.compile(r"\b(оценка|score|балл)\s*[:=]?\s*([0-2])\b", re.I),   # score: 0/1/2 из 10
    re.compile(r"\b(оценка|score|балл)\s*[:=]?\s*0\.[0-2]\d*\b", re.I),  # score: 0.0–0.29
)

# Минимальный балл, при котором считаем ответ Auditor'а низким
_MIN_ACCEPTABLE_SCORE = 0.35


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SAGECorrectionResult:
    """Результат SAGE-анализа одного шага пайплайна."""
    needs_rebuild: bool
    low_score_step: str               # role name с низким баллом (или "")
    detected_score: float             # 0.0–1.0; -1 если не удалось распарсить
    correction_hint: str              # текстовая рекомендация
    suggested_chain: List[str]        # предложенная новая цепочка (может быть пустой)
    session_key: str                  # ключ в SuperMemory
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# SAGE Engine
# ---------------------------------------------------------------------------

class SAGEEngine:
    """Self-evolution engine: анализирует результаты, генерирует исправления.

    Используется двумя способами:
    1. Пассивный: ``analyze_steps()`` — проверяет шаги на низкий балл.
    2. Активный (с LLM): ``generate_correction()`` — просит LLM объяснить
       причину провала и предлагает новую цепочку.
    """

    def __init__(
        self,
        model: str = "",
        enabled: bool = True,
    ):
        self.model = model or "qwen/qwen3.6-plus:free"
        self.enabled = enabled
        self._correction_count = 0

    # ------------------------------------------------------------------
    # Low-score detection (heuristic, no LLM)
    # ------------------------------------------------------------------

    def _parse_score(self, response: str) -> float:
        """Пытается извлечь числовой балл из текстового ответа Auditor'а."""
        # Паттерн 1: явная шкала /10 (score: 1/10, балл: 7/10) — ВСЕГДА делим на 10
        out_of_10 = re.compile(
            r"(?:score|балл|оценка)\s*[:=]\s*([\d]+\.?[\d]*)\s*/\s*10", re.I
        )
        m = out_of_10.search(response)
        if m:
            return min(1.0, float(m.group(1)) / 10.0)

        # Паттерн 2: десятичное значение ≤ 1 (score: 0.25)
        decimal_pat = re.compile(
            r"(?:score|балл|оценка)\s*[:=]\s*(0\.\d+|1\.0)\b", re.I
        )
        m = decimal_pat.search(response)
        if m:
            return float(m.group(1))

        # Паттерн 3: целое число без знаменателя (оценка: 7) — если > 1, делим
        int_pat = re.compile(
            r"(?:score|балл|оценка)\s*[:=]\s*([0-9]+)\b", re.I
        )
        m = int_pat.search(response)
        if m:
            val = float(m.group(1))
            return min(1.0, val / 10.0) if val > 1.0 else val

        return -1.0  # не удалось определить

    def _has_low_quality_markers(self, response: str) -> bool:
        """Проверяет наличие маркеров низкого качества без числового балла."""
        return any(pat.search(response) for pat in _LOW_QUALITY_MARKERS)

    def _step_is_low_quality(self, step: Dict[str, Any]) -> tuple[bool, float]:
        """Возвращает (is_low, detected_score) для одного шага."""
        role = step.get("role", "")
        response = step.get("response", "")

        # Анализируем только Auditor-шаги
        if "auditor" not in role.lower() and "audit" not in role.lower():
            return False, -1.0

        score = self._parse_score(response)
        if score != -1.0:
            return score < _MIN_ACCEPTABLE_SCORE, score

        # Fallback на текстовые маркеры
        if self._has_low_quality_markers(response):
            return True, 0.2  # условный плохой балл

        return False, score

    # ------------------------------------------------------------------
    # Main analysis
    # ------------------------------------------------------------------

    def analyze_steps(
        self,
        steps: List[Dict[str, Any]],
        original_chain: List[str],
    ) -> SAGECorrectionResult:
        """Анализирует шаги пайплайна. Если Auditor дал низкий балл →
        возвращает SAGECorrectionResult с needs_rebuild=True и подсказкой.

        Не делает LLM-вызовов — только эвристический анализ.
        """
        if not self.enabled:
            return SAGECorrectionResult(
                needs_rebuild=False, low_score_step="", detected_score=-1.0,
                correction_hint="", suggested_chain=[], session_key="",
            )

        for step in steps:
            is_low, score = self._step_is_low_quality(step)
            if is_low:
                role = step["role"]
                logger.warning(
                    "SAGE: low-quality auditor step detected",
                    role=role, score=round(score, 2) if score != -1 else "n/a",
                )
                # Эвристически предлагаем цепочку с дополнительным шагом исправления
                suggested = self._suggest_rebuild(original_chain, role)
                key = f"sage:correction:{int(time.time())}"
                self._correction_count += 1
                return SAGECorrectionResult(
                    needs_rebuild=True,
                    low_score_step=role,
                    detected_score=score,
                    correction_hint=(
                        f"Шаг '{role}' получил низкий балл ({score:.2f}). "
                        f"Рекомендую перестроить цепочку: {' → '.join(suggested)}."
                    ),
                    suggested_chain=suggested,
                    session_key=key,
                )

        return SAGECorrectionResult(
            needs_rebuild=False, low_score_step="", detected_score=-1.0,
            correction_hint="", suggested_chain=[], session_key="",
        )

    def _suggest_rebuild(
        self,
        original_chain: List[str],
        failing_role: str,
    ) -> List[str]:
        """Эвристически перестраивает цепочку после провального шага."""
        chain = list(original_chain)
        # Вставляем «SAGE_Corrector» перед провальным Auditor'ом
        idx = next((i for i, r in enumerate(chain) if r == failing_role), len(chain))
        if "Coder" not in chain and idx > 0:
            chain.insert(idx, "Coder")
        # Дополнительный Auditor в конец, если его ещё нет в конце
        if chain[-1] != "Auditor":
            chain.append("Auditor")
        return chain

    # ------------------------------------------------------------------
    # Active correction (requires LLM)
    # ------------------------------------------------------------------

    async def generate_correction(
        self,
        prompt: str,
        failing_step: str,
        failing_response: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Вызывает LLM чтобы объяснить причину провала и предложить исправление.

        Возвращает строку-рекомендацию. При любой ошибке возвращает fallback-текст.
        """
        system = (
            "Ты — старший аналитик качества в мультиагентной системе. "
            "Твоя задача — определить причину провала агента и кратко предложить "
            "конкретное исправление логики. Никаких лишних слов."
        )
        user = (
            f"Задача пользователя: {prompt[:400]}\n\n"
            f"Провальный агент: {failing_step}\n"
            f"Его ответ (фрагмент):\n{failing_response[:800]}\n\n"
            "Объясни причину провала в 2-3 предложениях и предложи конкретный "
            "исправленный подход для следующего запуска."
        )
        try:
            raw = await route_llm(
                user,
                system=system,
                model=self.model,
                max_tokens=512,
                temperature=0.3,
            )
            return (raw or "").strip()
        except Exception as e:
            logger.warning("SAGE LLM correction failed (non-fatal)", error=str(e))
            return f"SAGE: не удалось сгенерировать LLM-коррекцию ({e})"

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def save_to_memory(
        self,
        supermemory: Any,
        result: SAGECorrectionResult,
        llm_correction: str = "",
    ) -> None:
        """Сохраняет SAGE-коррекцию в SuperMemory для последующего анализа."""
        if not result.session_key or supermemory is None:
            return
        content = (
            f"[SAGE CORRECTION]\n"
            f"Failing step: {result.low_score_step}\n"
            f"Score: {result.detected_score:.2f}\n"
            f"Hint: {result.correction_hint}\n"
            f"Suggested chain: {' → '.join(result.suggested_chain)}\n"
        )
        if llm_correction:
            content += f"LLM analysis: {llm_correction}\n"
        try:
            supermemory.store(
                key=result.session_key,
                content=content,
                importance=0.7,
                source="sage_correction",
                tier="hot",
            )
            logger.info("SAGE correction saved to SuperMemory", key=result.session_key)
        except Exception as e:
            logger.warning("SAGE memory save failed (non-fatal)", error=str(e))

    # ------------------------------------------------------------------
    # v7: Integration with Cognitive Evolution and Obsidian Vault
    # ------------------------------------------------------------------

    def record_to_evolution(
        self,
        evolution_engine: Any,
        result: SAGECorrectionResult,
        task_id: str = "",
        task_description: str = "",
        model_used: str = "",
    ) -> None:
        """Feed SAGE correction results into the cognitive evolution engine.

        This closes the self-learning loop: SAGE detects low quality →
        cognitive evolution tracks it → prompts evolve → quality improves.
        """
        if evolution_engine is None:
            return
        try:
            from src.cognitive_evolution import ExecutionOutcome

            outcome = ExecutionOutcome(
                task_id=task_id or result.session_key,
                task_description=task_description or f"SAGE correction for {result.low_score_step}",
                role=result.low_score_step,
                intended_action="High-quality pipeline step",
                observed_result=result.correction_hint,
                success=not result.needs_rebuild,
                quality_score=max(0.0, result.detected_score) if result.detected_score >= 0 else 0.2,
                duration_sec=0.0,
                model_used=model_used,
                error="" if not result.needs_rebuild else f"Low score: {result.detected_score:.2f}",
                suggestions=[result.correction_hint] if result.correction_hint else [],
            )
            evolution_engine.record_outcome(outcome)
            logger.info("SAGE correction fed to CognitiveEvolution", role=result.low_score_step)
        except Exception as e:
            logger.warning("SAGE→CognitiveEvolution bridge failed", error=str(e))

    def save_to_vault(
        self,
        vault_bridge: Any,
        result: SAGECorrectionResult,
        llm_correction: str = "",
    ) -> None:
        """Save SAGE correction to Obsidian vault for persistent learning.

        Creates a learning log entry that the cognitive evolution engine
        and proactive task scanner can use later.
        """
        if vault_bridge is None or not result.needs_rebuild:
            return
        try:
            lessons = [result.correction_hint]
            if llm_correction:
                lessons.append(f"LLM Analysis: {llm_correction[:300]}")

            vault_bridge.save_learning_log(
                task=f"SAGE: {result.low_score_step} quality check",
                outcome="failure",
                lessons=lessons,
                context=(
                    f"Score: {result.detected_score:.2f}\n"
                    f"Original chain: requested\n"
                    f"Suggested chain: {' → '.join(result.suggested_chain)}"
                ),
                improvements=[
                    f"Rebuild chain: {' → '.join(result.suggested_chain)}",
                    f"Focus on improving {result.low_score_step} role prompt",
                ],
            )
            logger.info("SAGE correction saved to Obsidian vault", step=result.low_score_step)
        except Exception as e:
            logger.warning("SAGE vault save failed (non-fatal)", error=str(e))

    @property
    def correction_count(self) -> int:
        """Количество задетектированных коррекций за время жизни движка."""
        return self._correction_count
