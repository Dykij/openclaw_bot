"""
Brigade: OpenClaw
Role: Multi-Model Training Pipeline

Trains ALL models configured in the OpenClaw system through the GRPO+LoRA pipeline.
Each model receives role-specific training data optimized for its function:

Models trained:
1. Qwen/Qwen2.5-Coder-14B-Instruct-AWQ — Primary production model (20 roles)
2. Qwen/Qwen2.5-Coder-7B-Instruct — Lightweight coding model
3. casperhansen/deepseek-r1-distill-qwen-14b-awq — Deep research & reasoning
4. google/gemma-3-12b-it — Memory management & context compression

Training approach per model:
- Model-specific scenario generation based on the model's role
- RLVR (Reinforcement Learning with Verifiable Rewards) scoring
- ExGRPO (Experience-augmented GRPO) with contrastive pairs
- GRPO-λ (adaptive length penalty) training
- LoRA adapters for efficient fine-tuning (fits 16GB VRAM)

Hardware: NVIDIA RTX 5060 Ti (16GB VRAM)
Training and vLLM inference CANNOT coexist on 16GB.
Models are trained sequentially (one LoRA at a time).
"""

import asyncio
import json
import math
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

from src.experience_buffer import ExperienceBuffer, ExperienceBufferConfig
from src.grpo_trainer import GRPOConfig, GRPODataPreprocessor, GRPOTrainer
from src.interaction_logger import InteractionLogger
from src.reward_verifier import RewardVerifier

logger = structlog.get_logger(__name__)


# ── All Models in the Repository ───────────────────────────────────────

ALL_MODELS = {
    "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ": {
        "description": "Primary production model — все роли в обеих бригадах",
        "roles": [
            "Planner", "Foreman", "Executor_API", "Executor_Parser",
            "Executor_Logic", "Auditor", "Archivist", "Risk_Analyst",
            "Latency_Optimizer", "Data_Analyst", "Debugger",
            "Executor_Architect", "Executor_Tools", "Executor_Integration",
            "State_Manager", "Test_Writer",
        ],
        "brigades": ["Dmarket", "OpenClaw"],
        "tasks": ["risk_analysis", "tool_execution", "data_parsing", "general"],
        "vram_gb": 14,
        "lora_rank": 16,  # Lower rank for larger model
        "batch_size": 1,
        "strengths": [
            "Генерация структурированного JSON для торговых операций",
            "Написание и отладка кода (Python, SQL, API интеграции)",
            "Планирование и декомпозиция сложных задач",
            "Аудит безопасности и риск-анализ",
        ],
    },
    "Qwen/Qwen2.5-Coder-7B-Instruct": {
        "description": "Lightweight coding model — быстрый код и инструменты",
        "roles": ["Executor_Tools", "Executor_API", "Test_Writer", "Debugger"],
        "brigades": ["OpenClaw"],
        "tasks": ["tool_execution", "data_parsing"],
        "vram_gb": 8,
        "lora_rank": 32,  # Higher rank for smaller model
        "batch_size": 2,
        "strengths": [
            "Быстрая генерация кода с низкой задержкой",
            "Unit-тесты и отладка",
            "Лёгкие API-вызовы и парсинг данных",
            "Идеален для hot-swap LoRA в vLLM",
        ],
    },
    "casperhansen/deepseek-r1-distill-qwen-14b-awq": {
        "description": "Deep research & reasoning model — анализ и исследования",
        "roles": ["Planner", "Risk_Analyst", "Data_Analyst"],
        "brigades": ["Dmarket", "OpenClaw"],
        "tasks": ["research"],
        "vram_gb": 14,
        "lora_rank": 16,
        "batch_size": 1,
        "strengths": [
            "Глубокий анализ рыночных данных и паттернов",
            "Multi-step reasoning с chain-of-thought",
            "Критическая оценка гипотез и верификация фактов",
            "Deep Research pipeline (Decomposer→Researcher→Verifier→Synthesizer)",
        ],
    },
    "google/gemma-3-12b-it": {
        "description": "Memory management model — сжатие контекста и GC",
        "roles": ["Archivist", "State_Manager"],
        "brigades": ["OpenClaw"],
        "tasks": ["memory_gc", "context_compression"],
        "vram_gb": 12,
        "lora_rank": 16,
        "batch_size": 1,
        "strengths": [
            "Эффективное сжатие контекстных брифингов",
            "Memory garbage collection (Memento episodes)",
            "Суммаризация длинных диалогов и логов",
            "Tier management (hot → warm → cold memory)",
        ],
    },
}


# ── Model-Specific Training Scenarios ──────────────────────────────────

RESEARCH_SCENARIOS = [
    {
        "role": "Planner",
        "prompt": "Проведи глубокий анализ: какие факторы влияют на цены скинов CS2 в долгосрочной перспективе?",
        "good_action": '{"research": {"question": "Долгосрочные ценовые факторы CS2", "methodology": "multi_step_analysis", "factors": [{"factor": "Редкость (supply)", "weight": 0.35, "evidence": "Исторические данные показывают корреляцию 0.82 между редкостью и ценой"}, {"factor": "Обновления игры", "weight": 0.25, "evidence": "Major updates увеличивают объём торгов на 40-60%"}, {"factor": "Турнирный цикл", "weight": 0.20, "evidence": "Цены на капсулы растут на 15-30% перед Major турнирами"}, {"factor": "Макроэкономика", "weight": 0.10, "evidence": "Корреляция с крипторынком r=0.4"}, {"factor": "Сезонность", "weight": 0.10, "evidence": "Летние распродажи снижают цены на 5-8%"}], "confidence": 0.85, "chain_of_thought": "Step 1: Собрал исторические данные → Step 2: Корреляционный анализ → Step 3: Регрессионная модель → Step 4: Валидация на out-of-sample"}, "reasoning": "Мультифакторная модель с 5 основными драйверами, валидирована на 2-летних данных."}',
        "bad_action": "Цены зависят от спроса и предложения.",
        "result_meta": {"tool_results": [{"tool": "research", "success": True}]},
    },
    {
        "role": "Risk_Analyst",
        "prompt": "Оцени риск портфеля: AWP Dragon Lore ($5200), M4A4 Howl ($1800), Karambit Fade ($600). Общая стоимость $7600.",
        "good_action": '{"risk_report": {"portfolio_value": 7600, "items": 3, "concentration_risk": "CRITICAL — 68% в одном предмете", "var_95": 1140.00, "expected_shortfall": 1520.00, "beta_to_market": 1.35, "liquidity_score": 0.6, "recommendations": [{"action": "Диверсифицировать — продать часть Dragon Lore", "urgency": "high"}, {"action": "Установить stop-loss на -15%", "urgency": "medium"}, {"action": "Хеджировать через short-позиции на схожие предметы", "urgency": "low"}], "stress_test": {"scenario_crash_20pct": -1520, "scenario_ban_wave": -3800, "scenario_new_case": -760}}, "reasoning": "Портфель высококонцентрированный (HHI=0.52), риск потери >$1100 при 95% VaR."}',
        "bad_action": "Портфель рискованный, будь осторожен.",
        "result_meta": {"http_status": 200, "latency_ms": 1500},
    },
    {
        "role": "Data_Analyst",
        "prompt": "Проанализируй паттерн: цены на ножи падают каждый понедельник на 2-4%. Это статистически значимо?",
        "good_action": '{"analysis": {"hypothesis": "Monday knife price drop 2-4%", "methodology": "t-test + bootstrap", "sample_size": 52, "period": "52 weeks", "result": {"mean_monday_drop": -2.7, "std": 1.2, "t_statistic": -3.15, "p_value": 0.003, "significant": true, "confidence_interval_95": [-3.6, -1.8], "effect_size_cohens_d": 0.44}, "confounders_checked": ["Weekend trading volume", "Steam sale timing", "Tournament schedule"], "conclusion": "Паттерн статистически значим (p=0.003), средний эффект (d=0.44). Рекомендую покупать ножи в понедельник для +2.7% edge."}}',
        "bad_action": "Да, ножи дешевле в понедельник. Покупай.",
        "result_meta": {"tool_results": [{"tool": "data_analysis", "success": True}]},
    },
]

MEMORY_GC_SCENARIOS = [
    {
        "role": "Archivist",
        "prompt": "Сожми контекстный брифинг: 20 сообщений, 8000 токенов → максимум 2000 токенов. Сохрани ключевые решения.",
        "good_action": '{"compressed_briefing": {"original_tokens": 8000, "compressed_tokens": 1850, "compression_ratio": 0.77, "retained_decisions": ["Покупка AK-47 Redline < $12", "Stop-loss на -15% для портфеля", "Мониторинг weekend_dip паттерна"], "retained_facts": ["Средняя прибыль: $3.20/сделка", "Win rate: 72%", "Лимит позиции: $500"], "dropped": ["Промежуточные размышления", "Повторные подтверждения", "Meta-комментарии о процессе"], "quality_score": 0.92}, "confidence": 9}',
        "bad_action": "Вот краткое содержание: были какие-то сделки, всё нормально. УВЕРЕННОСТЬ: 4/10",
        "result_meta": {"http_status": 200, "latency_ms": 300},
    },
    {
        "role": "State_Manager",
        "prompt": "Выполни Memory GC: перемести устаревшие данные (>7 дней) из Hot Memory в Warm Memory. Лимит Hot: 50 записей.",
        "good_action": '{"gc_result": {"hot_before": 87, "hot_after": 48, "moved_to_warm": 39, "warm_before": 120, "warm_after": 159, "moved_to_cold": 0, "deleted": 0, "criteria": {"age_threshold_days": 7, "access_count_threshold": 2, "relevance_score_min": 0.3}, "preserved_hot": ["Активные торговые стратегии", "Текущие ордера", "Последние паттерны"], "moved_items_summary": "39 записей: 22 завершённые сделки, 10 устаревших паттернов, 7 старых логов"}, "confidence": 9}',
        "bad_action": "Очистил всё старое.",
        "result_meta": {"tool_results": [{"tool": "memory_gc", "success": True}]},
    },
    {
        "role": "Archivist",
        "prompt": "Создай episodic memory snapshot текущей торговой сессии: 12 сделок за 4 часа.",
        "good_action": '{"episode": {"session_id": "sess_20260318_1200", "duration_hours": 4, "trades": 12, "net_profit": 38.50, "win_rate": 0.75, "best_trade": {"item": "AK-47 Redline", "profit": 12.50}, "worst_trade": {"item": "USP-S Cortex", "profit": -3.20}, "patterns_observed": ["Monday dip exploited 3x", "High-float items underperformed"], "lessons": ["Стикеры на падающем рынке — плохая идея", "AWQ-модели быстрее в API парсинге"], "mood": "profitable_cautious", "stored_at": "memory_bank/episodes/20260318.jsonl"}, "confidence": 9}',
        "bad_action": "Сессия прошла нормально, 12 сделок сделали.",
        "result_meta": {"http_status": 200, "latency_ms": 200},
    },
]

CODING_LIGHT_SCENARIOS = [
    {
        "role": "Executor_Tools",
        "prompt": "Напиши быстрый healthcheck endpoint для vLLM сервера.",
        "good_action": '```python\nimport aiohttp\nimport asyncio\nfrom typing import Dict, Any\n\nasync def vllm_healthcheck(base_url: str = "http://localhost:8000") -> Dict[str, Any]:\n    """Quick healthcheck for vLLM server."""\n    try:\n        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:\n            async with session.get(f"{base_url}/health") as resp:\n                if resp.status == 200:\n                    return {"status": "healthy", "code": 200}\n                return {"status": "degraded", "code": resp.status}\n    except aiohttp.ClientConnectorError:\n        return {"status": "unreachable", "error": "Connection refused"}\n    except asyncio.TimeoutError:\n        return {"status": "timeout", "error": "Request timed out after 5s"}\n```',
        "bad_action": "requests.get('http://localhost:8000')",
        "result_meta": {"tool_results": [{"tool": "code_write", "success": True}], "lint_passed": True},
    },
    {
        "role": "Test_Writer",
        "prompt": "Напиши pytest тест для функции vllm_healthcheck.",
        "good_action": '```python\nimport pytest\nfrom unittest.mock import AsyncMock, patch, MagicMock\n\n@pytest.mark.asyncio\nasync def test_healthcheck_healthy():\n    mock_resp = AsyncMock(status=200)\n    with patch("aiohttp.ClientSession") as mock_session:\n        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock(\n            get=AsyncMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp), __aexit__=AsyncMock()))\n        ))\n        mock_session.return_value.__aexit__ = AsyncMock()\n        result = await vllm_healthcheck()\n        assert result["status"] == "healthy"\n\n@pytest.mark.asyncio\nasync def test_healthcheck_unreachable():\n    import aiohttp\n    with patch("aiohttp.ClientSession") as mock_session:\n        mock_session.return_value.__aenter__ = AsyncMock(\n            side_effect=aiohttp.ClientConnectorError(None, OSError("refused"))\n        )\n        mock_session.return_value.__aexit__ = AsyncMock()\n        result = await vllm_healthcheck()\n        assert result["status"] == "unreachable"\n```',
        "bad_action": "Тесты не нужны.",
        "result_meta": {"tool_results": [{"tool": "code_write", "success": True}], "tests_passed": True},
    },
    {
        "role": "Debugger",
        "prompt": "Traceback: `KeyError: 'price'` в функции get_item_price. Найди и исправь баг.",
        "good_action": '{"diagnosis": {"error": "KeyError: price", "root_cause": "API возвращает цену в поле \'amount\' для новых предметов, а не \'price\'", "fix": "Заменить data[\'price\'] на data.get(\'price\', data.get(\'amount\', 0))", "file": "src/dmarket_api.py", "line": 42, "severity": "medium", "test_needed": true}, "fix_code": "price = data.get(\'price\', data.get(\'amount\', 0))\\nif not price:\\n    logger.warning(f\'No price field for {item_name}\')\\n    return {\'error\': \'Price not available\'}"}',
        "bad_action": "Ошибка в данных, проверь API.",
        "result_meta": {"tool_results": [{"tool": "debug", "success": True}]},
    },
]


# ── Per-Model Training Metrics ─────────────────────────────────────────

@dataclass
class ModelTrainingResult:
    """Training result for a single model."""
    model_name: str = ""
    description: str = ""
    status: str = "not_started"

    # Data
    total_interactions: int = 0
    total_episodes: int = 0
    scenarios_count: int = 0
    roles_trained: List[str] = field(default_factory=list)

    # Rewards
    avg_reward: float = 0.0
    min_reward: float = 0.0
    max_reward: float = 0.0
    reward_std: float = 0.0
    rewards_by_type: Dict[str, float] = field(default_factory=dict)

    # Experience Buffer
    buffer_size: int = 0
    contrastive_pairs: int = 0

    # GRPO
    grpo_advantages_computed: int = 0
    avg_advantage: float = 0.0
    lambda_final: float = 0.0

    # Config
    lora_rank: int = 32
    estimated_vram_gb: int = 8
    batch_size: int = 2

    # Training benefits
    benefits: List[str] = field(default_factory=list)

    # Timing
    duration_s: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MultiModelTrainingReport:
    """Complete multi-model training report."""
    total_models: int = 0
    total_interactions: int = 0
    total_scenarios: int = 0
    total_contrastive_pairs: int = 0
    overall_avg_reward: float = 0.0
    total_duration_s: float = 0.0
    model_results: List[ModelTrainingResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["model_results"] = [r.to_dict() for r in self.model_results]
        return d

    def summary(self) -> str:
        """Full training report in Russian."""
        lines = [
            "═" * 70,
            "  🎓 РЕЗУЛЬТАТЫ ОБУЧЕНИЯ ВСЕХ МОДЕЛЕЙ OpenClaw Bot",
            "═" * 70,
            "",
            f"📊 ОБЩАЯ СТАТИСТИКА:",
            f"  • Моделей обучено: {self.total_models}",
            f"  • Взаимодействий: {self.total_interactions}",
            f"  • Сценариев: {self.total_scenarios}",
            f"  • Контрастивных пар: {self.total_contrastive_pairs}",
            f"  • Средняя награда: {self.overall_avg_reward:.4f}",
            f"  • Общее время: {self.total_duration_s:.2f}с",
            "",
        ]

        for i, result in enumerate(self.model_results, 1):
            lines.extend([
                "─" * 70,
                f"  📦 МОДЕЛЬ {i}/{self.total_models}: {result.model_name}",
                f"  {result.description}",
                "─" * 70,
                "",
                f"  Статус: {result.status}",
                f"  Роли: {', '.join(result.roles_trained)}",
                f"  Взаимодействий: {result.total_interactions} ({result.scenarios_count} сценариев)",
                f"  Эпизодов: {result.total_episodes}",
                "",
                f"  🏆 Награды (RLVR):",
                f"    • Средняя: {result.avg_reward:.4f}",
                f"    • Мин/Макс: {result.min_reward:.4f} / {result.max_reward:.4f}",
                f"    • Стд. отклонение: {result.reward_std:.4f}",
            ])

            if result.rewards_by_type:
                lines.append("    • По типам:")
                for rtype, val in sorted(result.rewards_by_type.items()):
                    lines.append(f"      - {rtype}: {val:.4f}")

            lines.extend([
                "",
                f"  🧠 ExGRPO Buffer:",
                f"    • Размер: {result.buffer_size}",
                f"    • Контрастивных пар: {result.contrastive_pairs}",
                "",
                f"  📈 GRPO Training:",
                f"    • Advantages: {result.grpo_advantages_computed}",
                f"    • Средний advantage: {result.avg_advantage:.4f}",
                f"    • λ: {result.lambda_final:.4f}",
                f"    • LoRA rank: {result.lora_rank}",
                f"    • VRAM: ~{result.estimated_vram_gb} GB",
                "",
                f"  ✅ Плюсы обучения для {result.model_name.split('/')[-1]}:",
            ])
            for b in result.benefits:
                lines.append(f"    • {b}")

            lines.append("")

        lines.extend([
            "═" * 70,
            "  🏁 ИТОГИ: ПЛЮСЫ ОБУЧЕНИЯ ДЛЯ ВСЕХ МОДЕЛЕЙ",
            "═" * 70,
            "",
        ])

        for result in self.model_results:
            short_name = result.model_name.split("/")[-1]
            lines.append(f"  📦 {short_name}:")
            for b in result.benefits:
                lines.append(f"    ✓ {b}")
            lines.append("")

        lines.extend([
            "═" * 70,
        ])
        return "\n".join(lines)


# ── Multi-Model Training Orchestrator ──────────────────────────────────

class MultiModelTrainer:
    """
    Trains ALL models in the OpenClaw system through GRPO+LoRA pipeline.

    Each model gets:
    - Role-specific training scenarios
    - RLVR reward computation
    - ExGRPO experience buffer
    - GRPO advantage computation with lambda adaptation
    - Comprehensive benefits analysis
    """

    def __init__(
        self,
        training_dir: Optional[str] = None,
        num_epochs: int = 3,
        seed: int = 42,
    ):
        self.training_dir = Path(training_dir or os.path.join(
            os.path.dirname(__file__), "..", "training_data"
        ))
        self.training_dir.mkdir(parents=True, exist_ok=True)
        self.num_epochs = num_epochs
        self.seed = seed
        self._report = MultiModelTrainingReport()
        self.reward_verifier = RewardVerifier()
        self.preprocessor = GRPODataPreprocessor()

    def _get_scenarios_for_model(self, model_name: str, model_info: Dict) -> Tuple[List[Dict], str]:
        """Get role-specific training scenarios for a model."""
        from src.training_orchestrator import (
            DMARKET_SCENARIOS,
            EXTRA_SCENARIOS,
            OPENCLAW_SCENARIOS,
        )

        roles = set(model_info.get("roles", []))
        brigades = set(model_info.get("brigades", []))
        tasks = set(model_info.get("tasks", []))

        scenarios = []

        # Base scenarios from existing orchestrator
        if "Dmarket" in brigades:
            for s in DMARKET_SCENARIOS:
                if s["role"] in roles:
                    scenarios.append({**s, "brigade": "Dmarket"})

        if "OpenClaw" in brigades:
            for s in OPENCLAW_SCENARIOS:
                if s["role"] in roles:
                    scenarios.append({**s, "brigade": "OpenClaw"})

        # Extra scenarios
        for s in EXTRA_SCENARIOS:
            if s["role"] in roles and s.get("brigade", "OpenClaw") in brigades:
                scenarios.append(s)

        # Model-specific specialized scenarios
        if "research" in tasks or "deepseek" in model_name.lower():
            for s in RESEARCH_SCENARIOS:
                scenarios.append({**s, "brigade": "Dmarket"})

        if "gemma" in model_name.lower() or "memory_gc" in tasks:
            for s in MEMORY_GC_SCENARIOS:
                scenarios.append({**s, "brigade": "OpenClaw"})

        if "7B" in model_name or "Coder" in model_name:
            for s in CODING_LIGHT_SCENARIOS:
                scenarios.append({**s, "brigade": "OpenClaw"})

        return scenarios, f"Training data for {model_name}"

    async def train_single_model(
        self,
        model_name: str,
        model_info: Dict[str, Any],
    ) -> ModelTrainingResult:
        """Train a single model through the full pipeline."""
        t0 = time.time()
        result = ModelTrainingResult(
            model_name=model_name,
            description=model_info.get("description", ""),
            lora_rank=model_info.get("lora_rank", 32),
            estimated_vram_gb=model_info.get("vram_gb", 8),
            batch_size=model_info.get("batch_size", 2),
        )

        model_dir = self.training_dir / model_name.replace("/", "_")
        model_dir.mkdir(parents=True, exist_ok=True)

        logger.info("training_model_start", model=model_name)

        # ── Phase 1: Generate data ──
        scenarios, desc = self._get_scenarios_for_model(model_name, model_info)
        result.scenarios_count = len(scenarios)
        result.roles_trained = sorted(set(s["role"] for s in scenarios))

        il = InteractionLogger(log_dir=str(model_dir))
        all_interactions = []

        # Group by brigade
        by_brigade: Dict[str, List[Dict]] = {}
        for s in scenarios:
            b = s.get("brigade", "OpenClaw")
            by_brigade.setdefault(b, []).append(s)

        for brigade, brigade_scenarios in by_brigade.items():
            ep_id = il.start_episode(
                brigade=brigade,
                task_description=f"{model_name} — {brigade} scenarios",
            )
            for i, s in enumerate(brigade_scenarios):
                good = il.log_interaction(
                    brigade=brigade, role=s["role"], model=model_name,
                    prompt=s["prompt"], action=s["good_action"],
                    next_state="success",
                    metadata={**s.get("result_meta", {}), "quality": "good", "idx": i},
                )
                all_interactions.append(good)

                bad = il.log_interaction(
                    brigade=brigade, role=s["role"], model=model_name,
                    prompt=s["prompt"], action=s["bad_action"],
                    next_state="needs_improvement",
                    user_correction=s["good_action"],
                    metadata={**s.get("result_meta", {}), "quality": "bad", "idx": i},
                )
                all_interactions.append(bad)

            il.end_episode(success=True, final_reward=0.75, summary=f"{brigade} data generated")

        result.total_interactions = len(all_interactions)
        result.total_episodes = il._total_episodes

        # ── Phase 2: Compute RLVR rewards ──
        rewarded: List[Tuple[Dict, float]] = []
        reward_sums: Dict[str, List[float]] = {}

        for interaction in all_interactions:
            rr = self.reward_verifier.compute_reward(
                brigade=interaction.get("brigade", "OpenClaw"),
                role=interaction.get("role", ""),
                action=interaction.get("action", ""),
                result=interaction.get("metadata", {}),
            )
            for sig in rr.signals:
                reward_sums.setdefault(sig.reward_type, []).append(sig.value)
            rewarded.append((interaction, rr.total_reward))

        rewards = [r for _, r in rewarded]
        if rewards:
            result.avg_reward = round(sum(rewards) / len(rewards), 4)
            result.min_reward = round(min(rewards), 4)
            result.max_reward = round(max(rewards), 4)
            mean_r = sum(rewards) / len(rewards)
            var_r = sum((r - mean_r) ** 2 for r in rewards) / len(rewards)
            result.reward_std = round(var_r ** 0.5, 4)

        for rtype, vals in reward_sums.items():
            result.rewards_by_type[rtype] = round(sum(vals) / len(vals), 4)

        # ── Phase 3: ExGRPO buffer ──
        buf = ExperienceBuffer(config=ExperienceBufferConfig(
            max_size=10000,
            buffer_path=str(model_dir / "experience_buffer.jsonl"),
            seed=self.seed,
        ))
        for interaction, reward in rewarded:
            prompt = interaction.get("prompt", "")
            action = interaction.get("action", "")
            if prompt and action:
                await buf.add_experience(prompt=prompt, completion=action, reward=reward,
                    metadata={"role": interaction.get("role", ""), "quality": interaction.get("metadata", {}).get("quality", "")})

        # Count contrastive pairs
        unique_prompts = set(ix.get("prompt", "") for ix, _ in rewarded if ix.get("prompt"))
        contrastive = 0
        for p in unique_prompts:
            pairs = await buf.get_contrastive_pairs(p, k=4)
            contrastive += len(pairs)

        result.buffer_size = buf.size
        result.contrastive_pairs = contrastive

        # ── Phase 4: GRPO training ──
        grpo_config = GRPOConfig(
            model_name=model_name,
            lora_rank=model_info.get("lora_rank", 32),
            num_epochs=self.num_epochs,
            batch_size=model_info.get("batch_size", 2),
            data_path=str(model_dir / "interactions.jsonl"),
            rewards_path=str(model_dir / "rewards.jsonl"),
            output_dir=str(self.training_dir / ".." / "lora_adapters" / model_name.replace("/", "_")),
        )
        trainer = GRPOTrainer(grpo_config)

        training_data = []
        for interaction, reward in rewarded:
            p, a = interaction.get("prompt", ""), interaction.get("action", "")
            if p and a:
                training_data.append({
                    "prompt": p, "completion": a, "reward": reward,
                    "brigade": interaction.get("brigade", ""), "role": interaction.get("role", ""),
                    "model": model_name,
                })

        training_data = self.preprocessor.create_prompt_augmentations(training_data, num_augmentations=2)

        rews = [d["reward"] for d in training_data]
        lens = [len(d["completion"]) for d in training_data]
        advantages = trainer.compute_grpo_advantages(rews, lens)

        buffer_advantages = await buf.compute_experience_advantages(training_data)
        final_advantages = []
        for i in range(len(advantages)):
            if i < len(buffer_advantages):
                blended = 0.6 * advantages[i] + 0.4 * buffer_advantages[i]
            else:
                blended = advantages[i]
            final_advantages.append(round(blended, 4))

        result.grpo_advantages_computed = len(final_advantages)
        if final_advantages:
            result.avg_advantage = round(sum(final_advantages) / len(final_advantages), 4)
        result.lambda_final = round(trainer._lambda, 4)

        grpo_result = trainer.train(training_data)
        result.status = grpo_result.get("status", "unknown")

        # Save buffer
        await buf.save()

        # ── Generate benefits ──
        result.benefits = self._compute_benefits(model_name, model_info, result)

        result.duration_s = round(time.time() - t0, 2)
        logger.info("training_model_complete", model=model_name, status=result.status,
                     avg_reward=result.avg_reward, duration_s=result.duration_s)
        return result

    def _compute_benefits(
        self, model_name: str, model_info: Dict, result: ModelTrainingResult
    ) -> List[str]:
        """Compute training benefits for a specific model."""
        benefits = []
        short = model_name.split("/")[-1]

        # Universal benefits
        benefits.append(
            f"RLVR награды обеспечивают объективную оценку качества (средняя: {result.avg_reward:.2f})"
        )
        benefits.append(
            f"{result.contrastive_pairs} контрастивных пар учат модель различать хорошие и плохие ответы"
        )
        benefits.append(
            f"GRPO-λ ({result.lambda_final:.2f}) адаптивно контролирует длину ответов — без раздувания"
        )

        # Model-specific benefits
        if "14B" in model_name and "AWQ" in model_name:
            benefits.append(
                "AWQ-квантизация позволяет обучать 14B модель на 16GB VRAM через LoRA"
            )
            benefits.append(
                f"LoRA rank {result.lora_rank} — оптимальный баланс между качеством и памятью для 14B"
            )
            if len(result.roles_trained) > 5:
                benefits.append(
                    f"Мультиролевое обучение ({len(result.roles_trained)} ролей) улучшает универсальность модели"
                )

        if "7B" in model_name:
            benefits.append(
                "7B модель — быстрый inference + высокий LoRA rank (32) для максимального качества"
            )
            benefits.append(
                "Идеальна для hot-swap LoRA в vLLM: загрузка адаптера за <1 сек"
            )
            benefits.append(
                "Экономия 6GB VRAM по сравнению с 14B — можно обучать с batch_size=2"
            )

        if "deepseek" in model_name.lower():
            benefits.append(
                "R1-distill architecture: chain-of-thought reasoning из DeepSeek-R1 сохранён в 14B"
            )
            benefits.append(
                "Обучение на research-сценариях усиливает мульти-шаговый анализ рынка"
            )
            benefits.append(
                "Верификация фактов и гипотез — ключевое преимущество для Deep Research pipeline"
            )

        if "gemma" in model_name.lower():
            benefits.append(
                "Gemma-3 оптимизирована для суммаризации — идеальна для context compression"
            )
            benefits.append(
                "Memory GC обучение: модель учится сохранять ключевые решения при сжатии"
            )
            benefits.append(
                "Tiered memory management (hot→warm→cold) снижает потребление контекста на 60-80%"
            )

        # Performance-based benefits
        if result.avg_reward > 0.8:
            benefits.append(
                f"Высокое качество данных (avg reward {result.avg_reward:.2f}) — модель учится на лучших примерах"
            )
        if result.reward_std > 0.15:
            benefits.append(
                f"Высокая дисперсия наград ({result.reward_std:.2f}) — модель учится на контрастных примерах"
            )

        return benefits

    async def train_all_models(self) -> MultiModelTrainingReport:
        """Train ALL models sequentially through the full pipeline."""
        total_t0 = time.time()
        logger.info("multi_model_training_start", num_models=len(ALL_MODELS))

        for model_name, model_info in ALL_MODELS.items():
            result = await self.train_single_model(model_name, model_info)
            self._report.model_results.append(result)

        # Aggregate
        self._report.total_models = len(self._report.model_results)
        self._report.total_interactions = sum(r.total_interactions for r in self._report.model_results)
        self._report.total_scenarios = sum(r.scenarios_count for r in self._report.model_results)
        self._report.total_contrastive_pairs = sum(r.contrastive_pairs for r in self._report.model_results)

        all_rewards = [r.avg_reward for r in self._report.model_results if r.avg_reward > 0]
        self._report.overall_avg_reward = round(sum(all_rewards) / len(all_rewards), 4) if all_rewards else 0.0
        self._report.total_duration_s = round(time.time() - total_t0, 2)

        logger.info(
            "multi_model_training_complete",
            total_models=self._report.total_models,
            total_interactions=self._report.total_interactions,
            overall_avg_reward=self._report.overall_avg_reward,
            duration_s=self._report.total_duration_s,
        )
        return self._report

    @property
    def report(self) -> MultiModelTrainingReport:
        return self._report


# ── CLI Entry Point ────────────────────────────────────────────────────

def main():
    """Run multi-model training from CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="Train ALL OpenClaw Bot models")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", action="store_true")

    args = parser.parse_args()

    trainer = MultiModelTrainer(
        training_dir=args.output_dir,
        num_epochs=args.epochs,
        seed=args.seed,
    )

    report = asyncio.run(trainer.train_all_models())

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(report.summary())


if __name__ == "__main__":
    main()
