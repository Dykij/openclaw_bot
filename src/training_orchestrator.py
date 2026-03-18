"""
Brigade: OpenClaw
Role: Training Orchestrator — End-to-End Model Training Pipeline

Orchestrates the complete training cycle:
1. Generate/load synthetic training data
2. Compute RLVR rewards for all interactions
3. Fill experience buffer with prioritized replay data
4. Execute GRPO training with LoRA + GRPO-λ + ExGRPO
5. Evaluate results and produce metrics report

This module ties together all training subsystems:
- interaction_logger.py (data collection)
- reward_verifier.py (RLVR rewards)
- experience_buffer.py (ExGRPO prioritized replay)
- grpo_trainer.py (GRPO + LoRA training)
- safety_guardrails.py (output safety checks)

Hardware: NVIDIA RTX 5060 Ti (16GB VRAM)
Training and vLLM inference CANNOT coexist on 16GB.
"""

import asyncio
import json
import os
import random
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


# ── Synthetic Training Data Scenarios ───────────────────────────────────

DMARKET_SCENARIOS = [
    {
        "role": "Planner",
        "prompt": "Проанализируй текущие цены на AK-47 | Redline на Dmarket. Определи оптимальную стратегию покупки.",
        "good_action": '{"analysis": {"item": "AK-47 | Redline", "current_price": 12.50, "avg_7d": 13.20, "trend": "falling", "recommendation": "buy", "target_price": 11.80, "confidence": 0.82}, "reasoning": "Цена ниже 7-дневного среднего на 5.3%, тренд нисходящий. Рекомендую покупку при достижении $11.80."}',
        "bad_action": "Наверное стоит купить, цены вроде нормальные.",
        "result_meta": {"http_status": 200, "latency_ms": 450},
    },
    {
        "role": "Executor_API",
        "prompt": "Выполни покупку предмета AK-47 | Redline по цене не выше $12.00. Используй Dmarket API.",
        "good_action": '{"action": "buy", "item": "AK-47 | Redline", "max_price": 12.00, "api_endpoint": "/marketplace/buy", "status": "executed", "actual_price": 11.95, "order_id": "DM-2026-001"}',
        "bad_action": "Я не могу выполнить покупку, попробуйте позже.",
        "result_meta": {"http_status": 200, "latency_ms": 320, "profit": 0.55},
    },
    {
        "role": "Archivist",
        "prompt": "Запиши результат сделки: купили AK-47 | Redline за $11.95, ожидаемая прибыль $0.55.",
        "good_action": '{"archived": true, "trade_id": "DM-2026-001", "item": "AK-47 | Redline", "buy_price": 11.95, "expected_profit": 0.55, "stored_at": "memory_bank/trades/2026-03-18.jsonl", "confidence": 9}',
        "bad_action": "Записал. УВЕРЕННОСТЬ: 3/10",
        "result_meta": {"http_status": 200, "latency_ms": 150},
    },
    {
        "role": "Planner",
        "prompt": "Оцени риски портфеля: 5 предметов CS2, общая стоимость $150. Волатильность рынка повышена.",
        "good_action": '{"risk_assessment": {"portfolio_value": 150.00, "num_items": 5, "volatility": "high", "var_95": 22.50, "max_drawdown_estimate": 35.00, "recommendation": "hedge", "diversification_score": 0.65}, "reasoning": "VaR 95% = $22.50. Рекомендую хеджирование через продажу 1-2 высоковолатильных позиций."}',
        "bad_action": "Портфель нормальный, не переживай",
        "result_meta": {"http_status": 200, "latency_ms": 800},
    },
    {
        "role": "Executor_API",
        "prompt": "Получи текущий список предложений (offers) для M4A4 | Howl через Dmarket API.",
        "good_action": '{"offers": [{"price": 1850.00, "seller": "user_x", "float": 0.15}, {"price": 1920.00, "seller": "user_y", "float": 0.08}], "total_offers": 2, "api_status": "success", "lowest_price": 1850.00}',
        "bad_action": "Ошибка API: Connection timeout",
        "result_meta": {"http_status": 200, "latency_ms": 1200},
    },
    {
        "role": "Planner",
        "prompt": "Какую стратегию использовать для торговли стикерами Katowice 2014? Бюджет $500.",
        "good_action": '{"strategy": {"type": "long_term_hold", "budget": 500, "target_items": ["iBUYPOWER Holo", "Titan Holo", "Reason Gaming"], "expected_roi": "15-25% годовых", "risk_level": "medium-high", "entry_criteria": "покупка на просадках -10% от среднего"}, "reasoning": "Стикеры Katowice 2014 — дефицитный актив с стабильным ростом. Рекомендую DCA стратегию."}',
        "bad_action": "Стикеры — это рискованно. Лучше не торговать.",
        "result_meta": {"http_status": 200, "latency_ms": 600},
    },
    {
        "role": "Archivist",
        "prompt": "Обнови базу знаний: добавь паттерн 'weekend_dip' — цены на оружие падают на 3-5% в выходные.",
        "good_action": '{"pattern_stored": true, "pattern_name": "weekend_dip", "description": "Цены CS2 предметов падают на 3-5% в субботу-воскресенье", "data_points": 142, "confidence": 0.78, "category": "temporal_patterns", "stored_path": "memory_bank/patterns/temporal.jsonl", "confidence": 8}',
        "bad_action": "Ок, запомнил. УВЕРЕННОСТЬ: 4/10",
        "result_meta": {"http_status": 200, "latency_ms": 100},
    },
]

OPENCLAW_SCENARIOS = [
    {
        "role": "Planner",
        "prompt": "Пользователь просит: 'Создай скрипт мониторинга цен на Dmarket'. Разбей задачу на подзадачи.",
        "good_action": '{"plan": {"task": "price_monitor_script", "subtasks": [{"id": 1, "action": "Определить API endpoints для получения цен", "tool": "web_search"}, {"id": 2, "action": "Написать Python скрипт с aiohttp для polling", "tool": "code_write"}, {"id": 3, "action": "Добавить фильтрацию по предметам и алерты", "tool": "code_write"}, {"id": 4, "action": "Протестировать на реальных данных", "tool": "code_run"}], "estimated_time": "15 минут"}, "reasoning": "Декомпозиция по принципу 90/10 STAR: 90% планирование, 10% исполнение."}',
        "bad_action": "Нужно написать скрипт. Начнём.",
        "result_meta": {"tool_results": [{"tool": "planner", "success": True}]},
    },
    {
        "role": "Executor_Tools",
        "prompt": "Напиши Python-функцию для получения текущей цены предмета через Dmarket API.",
        "good_action": '```python\nimport aiohttp\nimport asyncio\n\nasync def get_item_price(item_name: str) -> dict:\n    """Get current price for a Dmarket item."""\n    url = "https://api.dmarket.com/exchange/v1/market/items"\n    params = {"title": item_name, "limit": 1, "orderBy": "price", "orderDir": "asc"}\n    async with aiohttp.ClientSession() as session:\n        async with session.get(url, params=params) as resp:\n            data = await resp.json()\n            if data.get("objects"):\n                item = data["objects"][0]\n                return {"price": item["price"]["USD"], "title": item["title"]}\n            return {"error": "Item not found"}\n```',
        "bad_action": "import requests\nresult = requests.get('url')\nprint(result)",
        "result_meta": {
            "tool_results": [{"tool": "code_write", "success": True}],
            "lint_passed": True,
            "typecheck_passed": True,
        },
    },
    {
        "role": "Archivist",
        "prompt": "Сохрани паттерн: async функция get_item_price для Dmarket API, использует aiohttp.",
        "good_action": '{"stored": true, "pattern": "dmarket_price_api", "description": "Асинхронная функция для получения цен через Dmarket REST API с aiohttp", "tags": ["dmarket", "api", "async", "aiohttp"], "confidence": 9, "location": "memory_bank/code_patterns/dmarket_api.md"}',
        "bad_action": "Сохранено. УВЕРЕННОСТЬ: 5/10",
        "result_meta": {"tool_results": [{"tool": "memory_write", "success": True}]},
    },
    {
        "role": "Planner",
        "prompt": "Пользователь: 'Как оптимизировать мою стратегию торговли?' Нужен Deep Research.",
        "good_action": '{"plan": {"type": "deep_research", "question": "Оптимизация стратегии торговли скинами CS2", "complexity": "complex", "sub_queries": ["Лучшие алгоритмы ценообразования для виртуальных предметов", "Машинное обучение для предсказания цен CS2", "Анализ сезонности рынка Dmarket"], "max_iterations": 5}, "reasoning": "Вопрос сложный, требует многоэтапного исследования с верификацией фактов."}',
        "bad_action": "Торгуй по интуиции.",
        "result_meta": {"tool_results": [{"tool": "research", "success": True}]},
    },
    {
        "role": "Executor_Tools",
        "prompt": "Создай unit-тест для функции get_item_price.",
        "good_action": '```python\nimport pytest\nfrom unittest.mock import AsyncMock, patch\n\n@pytest.mark.asyncio\nasync def test_get_item_price_success():\n    mock_response = {"objects": [{"price": {"USD": "12.50"}, "title": "AK-47 | Redline"}]}\n    with patch("aiohttp.ClientSession.get") as mock_get:\n        mock_get.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(json=AsyncMock(return_value=mock_response)))\n        result = await get_item_price("AK-47 | Redline")\n        assert result["price"] == "12.50"\n        assert result["title"] == "AK-47 | Redline"\n\n@pytest.mark.asyncio\nasync def test_get_item_price_not_found():\n    mock_response = {"objects": []}\n    with patch("aiohttp.ClientSession.get") as mock_get:\n        mock_get.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(json=AsyncMock(return_value=mock_response)))\n        result = await get_item_price("NonExistentItem")\n        assert "error" in result\n```',
        "bad_action": "Тесты не нужны, код и так работает.",
        "result_meta": {
            "tool_results": [{"tool": "code_write", "success": True}],
            "lint_passed": True,
            "tests_passed": True,
        },
    },
    {
        "role": "Planner",
        "prompt": "Пользователь хочет настроить автоматические уведомления о падении цен более 10%.",
        "good_action": '{"plan": {"task": "price_alert_system", "subtasks": [{"id": 1, "action": "Создать мониторинг с периодическим polling каждые 5 минут", "tool": "code_write"}, {"id": 2, "action": "Реализовать сравнение с историческими ценами", "tool": "code_write"}, {"id": 3, "action": "Добавить отправку уведомлений через Telegram Bot API", "tool": "code_write"}, {"id": 4, "action": "Настроить конфигурацию пороговых значений", "tool": "config_write"}], "estimated_time": "20 минут"}}',
        "bad_action": "Можно попробовать. Не уверен что получится.",
        "result_meta": {"tool_results": [{"tool": "planner", "success": True}]},
    },
    {
        "role": "Executor_Tools",
        "prompt": "Реализуй алерт-систему: если цена упала на >10%, отправь уведомление в Telegram.",
        "good_action": '```python\nimport aiohttp\nimport asyncio\nfrom datetime import datetime\n\nclass PriceAlertMonitor:\n    def __init__(self, bot_token: str, chat_id: int, threshold: float = 0.10):\n        self.bot_token = bot_token\n        self.chat_id = chat_id\n        self.threshold = threshold\n        self.price_history = {}\n\n    async def check_price_drop(self, item: str, current_price: float) -> bool:\n        if item in self.price_history:\n            prev_price = self.price_history[item]\n            drop_pct = (prev_price - current_price) / prev_price\n            if drop_pct >= self.threshold:\n                await self.send_alert(item, prev_price, current_price, drop_pct)\n                return True\n        self.price_history[item] = current_price\n        return False\n\n    async def send_alert(self, item, prev, curr, pct):\n        msg = f"🚨 {item}: -{pct:.1%} (${prev:.2f} → ${curr:.2f})"\n        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"\n        async with aiohttp.ClientSession() as s:\n            await s.post(url, json={"chat_id": self.chat_id, "text": msg})\n```',
        "bad_action": "# TODO: implement alert system later",
        "result_meta": {
            "tool_results": [{"tool": "code_write", "success": True}],
            "lint_passed": True,
        },
    },
]

# Additional diverse scenarios for richer training
EXTRA_SCENARIOS = [
    {
        "brigade": "Dmarket",
        "role": "Planner",
        "prompt": "Определи арбитражные возможности между Dmarket и Steam Market для AWP | Dragon Lore.",
        "good_action": '{"arbitrage": {"item": "AWP | Dragon Lore", "dmarket_price": 5200.00, "steam_price": 5450.00, "spread": 250.00, "spread_pct": 4.8, "fees": {"dmarket": 2.0, "steam": 15.0}, "net_profit": 87.50, "recommendation": "profitable_with_caution"}, "reasoning": "Спред 4.8% минус комиссии = ~1.7% чистой прибыли. Осторожно из-за высокой стоимости позиции."}',
        "bad_action": "Арбитраж не работает.",
        "result_meta": {"http_status": 200, "latency_ms": 900},
    },
    {
        "brigade": "OpenClaw",
        "role": "Executor_Tools",
        "prompt": "Напиши SQL запрос для анализа прибыльности по категориям предметов за последний месяц.",
        "good_action": "```sql\nSELECT \n    category,\n    COUNT(*) as total_trades,\n    ROUND(AVG(profit_usd), 2) as avg_profit,\n    ROUND(SUM(profit_usd), 2) as total_profit,\n    ROUND(SUM(CASE WHEN profit_usd > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate_pct\nFROM trades \nWHERE created_at >= NOW() - INTERVAL '30 days'\nGROUP BY category\nORDER BY total_profit DESC;\n```",
        "bad_action": "SELECT * FROM trades",
        "result_meta": {"tool_results": [{"tool": "sql_execute", "success": True}]},
    },
    {
        "brigade": "Dmarket",
        "role": "Executor_API",
        "prompt": "Размести ордер на продажу: 3 шт. Glock-18 | Fade по $95.00 каждый.",
        "good_action": '{"orders_placed": [{"item": "Glock-18 | Fade", "price": 95.00, "quantity": 1, "order_id": "sell_001"}, {"item": "Glock-18 | Fade", "price": 95.00, "quantity": 1, "order_id": "sell_002"}, {"item": "Glock-18 | Fade", "price": 95.00, "quantity": 1, "order_id": "sell_003"}], "total_value": 285.00, "status": "all_placed"}',
        "bad_action": '{"error": "Не удалось разместить ордера"}',
        "result_meta": {"http_status": 200, "latency_ms": 500, "profit": 15.0},
    },
    {
        "brigade": "OpenClaw",
        "role": "Planner",
        "prompt": "Пользователь спросил: 'Почему мой бот не торгует ночью?' Проанализируй проблему.",
        "good_action": '{"diagnosis": {"issue": "bot_inactive_at_night", "possible_causes": [{"cause": "cron schedule не включает ночные часы", "probability": 0.7}, {"cause": "vLLM сервер перезагружается по расписанию", "probability": 0.2}, {"cause": "API rate limits ночью строже", "probability": 0.1}], "recommended_fix": "Проверить crontab и конфигурацию OpenClaw daemon в config/openclaw_config.json", "priority": "medium"}}',
        "bad_action": "Не знаю, проверьте сами.",
        "result_meta": {"tool_results": [{"tool": "diagnostic", "success": True}]},
    },
    {
        "brigade": "Dmarket",
        "role": "Archivist",
        "prompt": "Проанализируй историю торгов за неделю и обнови hot memory с ключевыми инсайтами.",
        "good_action": '{"weekly_insights": {"total_trades": 47, "total_profit": 156.80, "win_rate": 0.72, "best_category": "rifles", "worst_category": "stickers", "key_patterns": ["Monday dips -4%", "Friday spikes +3%", "High-float items underperform"], "updated_files": ["Hot_Memory.md", "trading_patterns.jsonl"]}, "confidence": 9}',
        "bad_action": "Всё хорошо, торговля идёт. УВЕРЕННОСТЬ: 3/10",
        "result_meta": {"http_status": 200, "latency_ms": 200},
    },
]


# ── Training Metrics ────────────────────────────────────────────────────

@dataclass
class TrainingMetrics:
    """Complete training session metrics."""

    # Data
    total_interactions: int = 0
    total_episodes: int = 0
    brigades_covered: List[str] = field(default_factory=list)
    roles_covered: List[str] = field(default_factory=list)

    # Rewards
    avg_reward: float = 0.0
    min_reward: float = 0.0
    max_reward: float = 0.0
    reward_std: float = 0.0
    rewards_by_type: Dict[str, float] = field(default_factory=dict)

    # Experience Buffer
    buffer_size: int = 0
    contrastive_pairs_generated: int = 0
    corrections_generated: int = 0

    # GRPO Training
    grpo_status: str = "not_started"
    grpo_advantages_computed: int = 0
    avg_advantage: float = 0.0
    lambda_final: float = 0.0
    training_plan: Dict[str, Any] = field(default_factory=dict)

    # Timing
    total_duration_s: float = 0.0
    phases: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        """Human-readable training summary."""
        lines = [
            "═" * 60,
            "  РЕЗУЛЬТАТЫ ОБУЧЕНИЯ МОДЕЛИ OpenClaw Bot",
            "═" * 60,
            "",
            "📊 ДАННЫЕ:",
            f"  • Взаимодействий: {self.total_interactions}",
            f"  • Эпизодов: {self.total_episodes}",
            f"  • Бригады: {', '.join(self.brigades_covered)}",
            f"  • Роли: {', '.join(self.roles_covered)}",
            "",
            "🏆 НАГРАДЫ (RLVR):",
            f"  • Средняя награда: {self.avg_reward:.4f}",
            f"  • Мин/Макс: {self.min_reward:.4f} / {self.max_reward:.4f}",
            f"  • Стандартное отклонение: {self.reward_std:.4f}",
        ]

        if self.rewards_by_type:
            lines.append("  • По типам:")
            for rtype, val in sorted(self.rewards_by_type.items()):
                lines.append(f"    - {rtype}: {val:.4f}")

        lines.extend([
            "",
            "🧠 EXPERIENCE BUFFER (ExGRPO):",
            f"  • Размер буфера: {self.buffer_size}",
            f"  • Контрастивных пар: {self.contrastive_pairs_generated}",
            f"  • Коррекций (Self-Correct): {self.corrections_generated}",
            "",
            "📈 GRPO TRAINING:",
            f"  • Статус: {self.grpo_status}",
            f"  • Advantages вычислено: {self.grpo_advantages_computed}",
            f"  • Средний advantage: {self.avg_advantage:.4f}",
            f"  • λ (length penalty): {self.lambda_final:.4f}",
        ])

        if self.training_plan:
            lines.append(f"  • Модель: {self.training_plan.get('config', {}).get('model', 'N/A')}")
            lines.append(f"  • LoRA rank: {self.training_plan.get('config', {}).get('lora_rank', 'N/A')}")
            lines.append(f"  • Epochs: {self.training_plan.get('config', {}).get('epochs', 'N/A')}")
            lines.append(f"  • Estimated VRAM: {self.training_plan.get('estimated_vram_gb', 'N/A')} GB")

        lines.extend([
            "",
            "⏱️  ВРЕМЯ:",
            f"  • Общее время: {self.total_duration_s:.2f}с",
        ])
        for phase, dur in self.phases.items():
            lines.append(f"    - {phase}: {dur:.2f}с")

        lines.extend(["", "═" * 60])
        return "\n".join(lines)


# ── Training Orchestrator ───────────────────────────────────────────────

class TrainingOrchestrator:
    """
    End-to-end training pipeline orchestrator.

    Coordinates all training subsystems to execute a complete training cycle:
    1. Data generation/loading
    2. Reward computation (RLVR)
    3. Experience buffer filling (ExGRPO)
    4. GRPO training with LoRA + lambda adaptation
    5. Metrics reporting
    """

    def __init__(
        self,
        training_dir: Optional[str] = None,
        model_name: str = "Qwen/Qwen2.5-Coder-7B-Instruct",
        lora_rank: int = 32,
        num_epochs: int = 3,
        seed: int = 42,
    ):
        self.training_dir = Path(training_dir or os.path.join(
            os.path.dirname(__file__), "..", "training_data"
        ))
        self.training_dir.mkdir(parents=True, exist_ok=True)

        self.model_name = model_name
        self.lora_rank = lora_rank
        self.num_epochs = num_epochs
        self.seed = seed

        # Subsystems
        self.interaction_logger = InteractionLogger(log_dir=str(self.training_dir))
        self.reward_verifier = RewardVerifier()
        self.experience_buffer = ExperienceBuffer(
            config=ExperienceBufferConfig(
                max_size=10000,
                buffer_path=str(self.training_dir / "experience_buffer.jsonl"),
                seed=seed,
            )
        )
        self.grpo_config = GRPOConfig(
            model_name=model_name,
            lora_rank=lora_rank,
            num_epochs=num_epochs,
            data_path=str(self.training_dir / "interactions.jsonl"),
            rewards_path=str(self.training_dir / "rewards.jsonl"),
            output_dir=str(self.training_dir / ".." / "lora_adapters" / "latest"),
        )
        self.grpo_trainer = GRPOTrainer(self.grpo_config)
        self.preprocessor = GRPODataPreprocessor()

        self._rng = random.Random(seed)
        self._metrics = TrainingMetrics()

        logger.info(
            "training_orchestrator_initialized",
            training_dir=str(self.training_dir),
            model=model_name,
            lora_rank=lora_rank,
        )

    # ── Phase 1: Data Generation ────────────────────────────────────

    def generate_synthetic_data(self) -> List[Dict[str, Any]]:
        """
        Generate synthetic training data from predefined scenarios.

        Each scenario produces two interactions:
        - A high-quality "good" response (reward ≈ 0.7-1.0)
        - A low-quality "bad" response (reward ≈ 0.0-0.3)

        This contrastive data is ideal for GRPO training where the model
        learns to prefer good outputs over bad ones.
        """
        t0 = time.time()
        all_interactions = []

        for scenario_set, brigade in [
            (DMARKET_SCENARIOS, "Dmarket"),
            (OPENCLAW_SCENARIOS, "OpenClaw"),
        ]:
            ep_id = self.interaction_logger.start_episode(
                brigade=brigade,
                task_description=f"Synthetic training data for {brigade} brigade",
            )

            for i, scenario in enumerate(scenario_set):
                role = scenario["role"]
                prompt = scenario["prompt"]
                result_meta = scenario.get("result_meta", {})

                # Log good action
                good_record = self.interaction_logger.log_interaction(
                    brigade=brigade,
                    role=role,
                    model=self.model_name,
                    prompt=prompt,
                    action=scenario["good_action"],
                    next_state="success",
                    metadata={**result_meta, "quality": "good", "scenario_idx": i},
                )
                all_interactions.append(good_record)

                # Log bad action (with correction)
                bad_record = self.interaction_logger.log_interaction(
                    brigade=brigade,
                    role=role,
                    model=self.model_name,
                    prompt=prompt,
                    action=scenario["bad_action"],
                    next_state="needs_improvement",
                    user_correction=scenario["good_action"],
                    metadata={**result_meta, "quality": "bad", "scenario_idx": i},
                )
                all_interactions.append(bad_record)

            self.interaction_logger.end_episode(
                success=True,
                final_reward=0.75,
                summary=f"Synthetic {brigade} training data generated",
            )

        # Add extra scenarios
        ep_id = self.interaction_logger.start_episode(
            brigade="Mixed",
            task_description="Extra diverse training scenarios",
        )
        for scenario in EXTRA_SCENARIOS:
            brigade = scenario.get("brigade", "OpenClaw")
            role = scenario["role"]
            result_meta = scenario.get("result_meta", {})

            good_record = self.interaction_logger.log_interaction(
                brigade=brigade,
                role=role,
                model=self.model_name,
                prompt=scenario["prompt"],
                action=scenario["good_action"],
                next_state="success",
                metadata={**result_meta, "quality": "good"},
            )
            all_interactions.append(good_record)

            bad_record = self.interaction_logger.log_interaction(
                brigade=brigade,
                role=role,
                model=self.model_name,
                prompt=scenario["prompt"],
                action=scenario["bad_action"],
                next_state="needs_improvement",
                user_correction=scenario["good_action"],
                metadata={**result_meta, "quality": "bad"},
            )
            all_interactions.append(bad_record)

        self.interaction_logger.end_episode(
            success=True,
            final_reward=0.70,
            summary="Extra diverse scenarios generated",
        )

        duration = time.time() - t0
        self._metrics.phases["data_generation"] = round(duration, 2)

        logger.info(
            "synthetic_data_generated",
            total_interactions=len(all_interactions),
            duration_s=round(duration, 2),
        )
        return all_interactions

    # ── Phase 2: Reward Computation ─────────────────────────────────

    def compute_rewards(
        self, interactions: List[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Compute RLVR rewards for all interactions.

        Uses the RewardVerifier to compute verifiable rewards from objective
        signals: JSON validity, HTTP status, latency, tool success, etc.
        """
        t0 = time.time()
        results = []
        reward_sums_by_type: Dict[str, List[float]] = {}

        for interaction in interactions:
            brigade = interaction.get("brigade", "OpenClaw")
            role = interaction.get("role", "Unknown")
            action = interaction.get("action", "")
            meta = interaction.get("metadata", {})

            reward_result = self.reward_verifier.compute_reward(
                brigade=brigade,
                role=role,
                action=action,
                result=meta,
            )

            total_reward = reward_result.total_reward

            # Log reward
            ep_id = interaction.get("episode_id", "")
            step = interaction.get("step_index", 0)
            if ep_id:
                self.interaction_logger.log_reward(
                    episode_id=ep_id,
                    step_index=step,
                    reward_type="rlvr_aggregate",
                    reward_value=total_reward,
                    details={
                        "signals": [
                            {"type": s.reward_type, "value": s.value, "weight": s.weight}
                            for s in reward_result.signals
                        ]
                    },
                )

            # Track per-type averages
            for signal in reward_result.signals:
                if signal.reward_type not in reward_sums_by_type:
                    reward_sums_by_type[signal.reward_type] = []
                reward_sums_by_type[signal.reward_type].append(signal.value)

            results.append((interaction, total_reward))

        # Update metrics
        rewards = [r for _, r in results]
        if rewards:
            self._metrics.avg_reward = round(sum(rewards) / len(rewards), 4)
            self._metrics.min_reward = round(min(rewards), 4)
            self._metrics.max_reward = round(max(rewards), 4)
            mean_r = sum(rewards) / len(rewards)
            var_r = sum((r - mean_r) ** 2 for r in rewards) / len(rewards)
            self._metrics.reward_std = round(var_r ** 0.5, 4)

        for rtype, values in reward_sums_by_type.items():
            self._metrics.rewards_by_type[rtype] = round(
                sum(values) / len(values), 4
            )

        duration = time.time() - t0
        self._metrics.phases["reward_computation"] = round(duration, 2)

        logger.info(
            "rewards_computed",
            total=len(results),
            avg_reward=self._metrics.avg_reward,
            duration_s=round(duration, 2),
        )
        return results

    # ── Phase 3: Experience Buffer ──────────────────────────────────

    async def fill_experience_buffer(
        self, rewarded_interactions: List[Tuple[Dict[str, Any], float]]
    ) -> None:
        """
        Fill the ExGRPO experience buffer with rewarded interactions.

        Also generates self-correction pairs from corrected interactions.
        """
        t0 = time.time()
        corrections = 0
        contrastive_pairs = 0

        for interaction, reward in rewarded_interactions:
            prompt = interaction.get("prompt", "")
            action = interaction.get("action", "")
            if not prompt or not action:
                continue

            await self.experience_buffer.add_experience(
                prompt=prompt,
                completion=action,
                reward=reward,
                metadata={
                    "brigade": interaction.get("brigade", ""),
                    "role": interaction.get("role", ""),
                    "quality": interaction.get("metadata", {}).get("quality", "unknown"),
                },
            )

            # Generate correction pair if this was a corrected interaction
            correction = interaction.get("user_correction")
            if correction and reward < 0.5:
                corr_exp = await self.experience_buffer.generate_correction_pair(
                    prompt=prompt,
                    initial_response=action,
                    reward=reward,
                )
                if corr_exp:
                    corrections += 1

        # Count contrastive pairs across unique prompts
        unique_prompts = set()
        for interaction, _ in rewarded_interactions:
            p = interaction.get("prompt", "")
            if p:
                unique_prompts.add(p)

        for prompt in unique_prompts:
            pairs = await self.experience_buffer.get_contrastive_pairs(prompt, k=4)
            contrastive_pairs += len(pairs)

        self._metrics.buffer_size = self.experience_buffer.size
        self._metrics.contrastive_pairs_generated = contrastive_pairs
        self._metrics.corrections_generated = corrections

        duration = time.time() - t0
        self._metrics.phases["experience_buffer"] = round(duration, 2)

        logger.info(
            "experience_buffer_filled",
            buffer_size=self.experience_buffer.size,
            contrastive_pairs=contrastive_pairs,
            corrections=corrections,
            duration_s=round(duration, 2),
        )

    # ── Phase 4: GRPO Training ──────────────────────────────────────

    async def run_grpo_training(
        self, rewarded_interactions: List[Tuple[Dict[str, Any], float]]
    ) -> Dict[str, Any]:
        """
        Execute GRPO training pipeline.

        1. Prepare training data with rewards
        2. Compute GRPO advantages with ExGRPO buffer enrichment
        3. Run training (or generate plan if GPU not available)
        """
        t0 = time.time()

        # Prepare training data
        training_data = []
        for interaction, reward in rewarded_interactions:
            prompt = interaction.get("prompt", "")
            action = interaction.get("action", "")
            if not prompt or not action:
                continue
            training_data.append({
                "prompt": prompt,
                "completion": action,
                "reward": reward,
                "brigade": interaction.get("brigade", ""),
                "role": interaction.get("role", ""),
                "model": interaction.get("model", ""),
            })

        # Apply prompt augmentations
        training_data = self.preprocessor.create_prompt_augmentations(
            training_data, num_augmentations=2
        )

        # Compute GRPO advantages with experience buffer enrichment
        rewards = [d["reward"] for d in training_data]
        lengths = [len(d["completion"]) for d in training_data]
        advantages = self.grpo_trainer.compute_grpo_advantages(rewards, lengths)

        # Also compute ExGRPO advantages using buffer history
        buffer_advantages = await self.experience_buffer.compute_experience_advantages(
            training_data
        )

        # Blend standard GRPO and ExGRPO advantages
        final_advantages = []
        for i in range(len(advantages)):
            if i < len(buffer_advantages):
                # 60% GRPO + 40% ExGRPO
                blended = 0.6 * advantages[i] + 0.4 * buffer_advantages[i]
            else:
                blended = advantages[i]
            final_advantages.append(round(blended, 4))

        # Add advantages to training data
        for i, adv in enumerate(final_advantages):
            if i < len(training_data):
                training_data[i]["advantage"] = adv

        self._metrics.grpo_advantages_computed = len(final_advantages)
        if final_advantages:
            self._metrics.avg_advantage = round(
                sum(final_advantages) / len(final_advantages), 4
            )
        self._metrics.lambda_final = round(self.grpo_trainer._lambda, 4)

        # Run actual training (or generate plan)
        result = self.grpo_trainer.train(training_data)
        self._metrics.grpo_status = result.get("status", "unknown")
        self._metrics.training_plan = result

        duration = time.time() - t0
        self._metrics.phases["grpo_training"] = round(duration, 2)

        logger.info(
            "grpo_training_complete",
            status=result.get("status"),
            advantages_computed=len(final_advantages),
            training_examples=len(training_data),
            duration_s=round(duration, 2),
        )
        return result

    # ── Main Orchestration ──────────────────────────────────────────

    async def run_full_training(self) -> TrainingMetrics:
        """
        Execute the complete training pipeline end-to-end.

        Returns:
            TrainingMetrics with all results.
        """
        total_t0 = time.time()

        logger.info("training_pipeline_starting", model=self.model_name)

        # Phase 1: Generate synthetic training data
        interactions = self.generate_synthetic_data()
        self._metrics.total_interactions = len(interactions)
        self._metrics.total_episodes = self.interaction_logger._total_episodes

        brigades = set()
        roles = set()
        for ix in interactions:
            brigades.add(ix.get("brigade", ""))
            roles.add(ix.get("role", ""))
        self._metrics.brigades_covered = sorted(brigades - {""})
        self._metrics.roles_covered = sorted(roles - {""})

        # Phase 2: Compute RLVR rewards
        rewarded_interactions = self.compute_rewards(interactions)

        # Phase 3: Fill experience buffer
        await self.fill_experience_buffer(rewarded_interactions)

        # Phase 4: GRPO training
        training_result = await self.run_grpo_training(rewarded_interactions)

        # Save experience buffer
        await self.experience_buffer.save()

        # Total timing
        self._metrics.total_duration_s = round(time.time() - total_t0, 2)

        logger.info(
            "training_pipeline_complete",
            total_interactions=self._metrics.total_interactions,
            avg_reward=self._metrics.avg_reward,
            buffer_size=self._metrics.buffer_size,
            grpo_status=self._metrics.grpo_status,
            total_duration_s=self._metrics.total_duration_s,
        )

        return self._metrics

    @property
    def metrics(self) -> TrainingMetrics:
        return self._metrics


# ── CLI Entry Point ─────────────────────────────────────────────────────

def main():
    """Run full training pipeline from CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="OpenClaw Bot Training Orchestrator")
    parser.add_argument("--model", default="Qwen/Qwen2.5-Coder-7B-Instruct")
    parser.add_argument("--lora-rank", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    orchestrator = TrainingOrchestrator(
        training_dir=args.output_dir,
        model_name=args.model,
        lora_rank=args.lora_rank,
        num_epochs=args.epochs,
        seed=args.seed,
    )

    metrics = asyncio.run(orchestrator.run_full_training())

    if args.json:
        print(json.dumps(metrics.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(metrics.summary())


if __name__ == "__main__":
    main()
