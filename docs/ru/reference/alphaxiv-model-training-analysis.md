# Анализ статей AlphaXiv: Улучшения для обучения моделей в OpenClaw

> **Дата:** 2026-03-18
> **Целевое оборудование:** NVIDIA RTX 5060 Ti (16 ГБ VRAM, архитектура Blackwell GB206)
> **Текущий стек:** vLLM + AWQ-квантизация (Qwen2.5-14B, DeepSeek-R1-14B, Qwen-Coder-7B, Gemma-3-12B)
> **Статус системы:** Только инференс → цель: добавить обучение/дообучение

---

## 1. Основная статья: OpenClaw-RL (arXiv:2603.10165)

**"OpenClaw-RL: Train Any Agent Simply by Talking"**

- **Ссылка:** <https://arxiv.org/abs/2603.10165>
- **AlphaXiv:** <https://www.alphaxiv.org/abs/2603.10165>
- **GitHub:** <https://github.com/Gen-Verse/OpenClaw-RL>

### Ключевые идеи

| Концепция | Описание | Применимость к OpenClaw Bot |
|-----------|----------|----------------------------|
| **Unified Interaction Signals** | Каждое взаимодействие агента (ответ пользователя, вывод терминала, GUI-событие) генерирует next-state сигнал для обучения | ✅ Прямо применимо — бот уже логирует все взаимодействия через Telegram/MCP |
| **Evaluative Signals (PRM Judge)** | Параметрическая модель-судья извлекает скалярные rewards из обратной связи | ✅ Можно обучить маленькую PRM (~1.5B) на наших данных |
| **Directive Signals (OPD)** | Hindsight-Guided On-Policy Distillation — извлечение токен-уровневого фидбека о том, *как* улучшить ответ | 🟡 Требует сбора корпуса правок пользователя |
| **Асинхронная архитектура** | Обслуживание, оценка PRM и обучение политики работают параллельно без координации | ✅ Совместимо с текущей архитектурой vLLM + task_queue |
| **Онлайн-персонализация** | Агент улучшается просто через использование — из корректировок, повторных запросов, фидбека | ✅ Идеально для персонализации бригад Dmarket/OpenClaw |

### Что можно внедрить

1. **Сбор Interaction Logs** — структурированное логирование пар (action, next_state, user_correction) в JSONL-формат
2. **PRM Judge на базе Qwen2.5-1.5B** — маленькая модель-судья для оценки качества ответов агентов
3. **OPD-пайплайн** — после накопления корпуса правок, distillation на основной модели

---

## 2. Связанные статьи и техники

### 2.1 GRPO — Group Relative Policy Optimization

**Статья:** "RL for Reasoning in Small LLMs" (arXiv:2503.16219)
**Ссылки:** <https://arxiv.org/abs/2503.16219>, <https://github.com/knoveleng/open-rs>

| Параметр | Значение |
|----------|----------|
| Алгоритм | GRPO (без critic-модели, экономит VRAM) |
| Модель | DeepSeek-R1-Distill-Qwen-1.5B |
| Оборудование | 4× A40 (24 ч, ~$42) |
| Результат | AMC23 accuracy: 63% → 80% |

**Применение к OpenClaw Bot:**
- ✅ GRPO работает без value network (экономия ~4 ГБ VRAM vs PPO)
- ✅ Подходит для дообучения наших DeepSeek-R1-14B и Qwen моделей
- ✅ Reward function: правильность JSON-выхода, успешность MCP-вызовов, оценка Archivist

**Практическая реализация:**
```python
# Концепт: GRPO reward для OpenClaw бригады
def openclaw_reward(response: str, task: dict) -> float:
    score = 0.0
    # JSON валидность
    if is_valid_json(response): score += 0.3
    # MCP tool call успешен
    if tool_call_succeeded(response, task): score += 0.4
    # Archivist confidence > 7/10
    if archivist_score(response) > 0.7: score += 0.3
    return score
```

### 2.2 GRPO-λ — Стабильное RL для Chain-of-Thought

**Статья:** "Stable RL for Efficient Reasoning" (arXiv:2505.18086)
**Ссылка:** <https://huggingface.co/papers/2505.18086>

**Ключевые улучшения:**
- Динамическая регулировка reward-стратегии на основе correctness ratio
- Снижение длины решений на ~50% при росте accuracy на 1.5%
- Предотвращение катастрофических провалов при агрессивных length penalties

**Применение к OpenClaw Bot:**
- ✅ Критично для обучения Planner-роли (сейчас генерирует слишком длинные STAR-планы)
- ✅ Уменьшение контекста = экономия VRAM при инференсе
- 🛠️ Реализация: добавить length penalty в reward function с λ-адаптацией

### 2.3 Prompt Augmentation для GRPO

**Статья:** "Prompt Augmentation Scales up GRPO Training on Mathematical Reasoning"
**Ссылка:** <https://www.aimodels.fyi/papers/arxiv/prompt-augmentation-scales-up-grpo-training-mathematical>

**Ключевая идея:**
- Тренировка с множественными вариациями каждого примера предотвращает entropy collapse
- Модель учит более разнообразные стратегии решения

**Применение к OpenClaw Bot:**
- ✅ Генерировать вариации задач Dmarket (разные товары, цены, стратегии)
- ✅ Предотвращает переобучение Executor-ролей на один паттерн API-вызовов

### 2.4 Self-Distillation для RL (SDPO)

**Статья:** "Reinforcement Learning via Self-Distillation" (arXiv:2601.20802)
**AlphaXiv:** <https://www.alphaxiv.org/overview/2601.20802v2>

**Ключевая идея:**
- Модель выступает собственным teacher — использует dense feedback из среды
- Ускорение обучения до 10× по сравнению со стандартным RL
- Особенно эффективна для code/logic задач

**Применение к OpenClaw Bot:**
- ✅ Идеально для Executor_Logic и Executor_API ролей
- ✅ Среда уже есть (MCP tools, database, API endpoints) — dense feedback доступен
- 🛠️ Qwen-Coder-7B как teacher+student модель

### 2.5 LoRA + 4-bit Quantization (Unsloth)

**Инструменты:** Unsloth, PEFT, bitsandbytes
**Ссылка:** <https://unsloth.ai/docs/models/qwen3-how-to-run-and-fine-tune>

| Модель | VRAM (4-bit) | Помещается в 16 ГБ? |
|--------|-------------|---------------------|
| Qwen3-7B | ~8 ГБ | ✅ Да, с запасом |
| Qwen3-14B | ~14 ГБ | ✅ Да, на пределе |
| DeepSeek-R1-14B | ~14 ГБ | ✅ Да, batch_size=2 |

**Конкретный рецепт для RTX 5060 Ti:**
```python
from unsloth import FastLanguageModel

# Загрузка модели в 4-bit
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen2.5-14B-Instruct",
    max_seq_length=2048,
    load_in_4bit=True,
)

# LoRA адаптер
model = FastLanguageModel.get_peft_model(
    model,
    r=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                     "gate_proj", "up_proj", "down_proj"],
    lora_alpha=32,
    use_gradient_checkpointing="unsloth",
)
```

### 2.6 ToolBrain — RL для Tool Use агентов

**Статья:** "ToolBrain: A Flexible RL Framework for Agentic Tools" (arXiv:2510.00023)
**Ссылка:** <https://arxiv.org/abs/2510.00023>

**Возможности:**
- GRPO и DPO для обучения tool use
- QLoRA пайплайны для квантизованного обучения
- Custom reward functions

**Применение к OpenClaw Bot:**
- ✅ Прямо применимо — бот активно использует MCP tools
- ✅ Reward на основе успешности tool calls (read_query, write_file, list_directory)
- 🛠️ Интеграция с существующим `pipeline_executor.py`

### 2.7 Memento — Обучение без градиентов

**Статья:** "Memento: Fine-tuning LLM Agents without Fine-tuning LLMs" (arXiv:2508.16153)
**Ссылка:** <https://arxiv.org/abs/2508.16153>

**Ключевая идея:**
- Эпизодическая память вместо обновления весов модели
- Агент учится через запоминание успешных эпизодов
- Не требует GPU для обучения вообще

**Применение к OpenClaw Bot:**
- ✅ Может работать параллельно с инференсом (нулевой VRAM overhead)
- ✅ Совместимо с существующим RAG (Hot_Memory, Cold_Memory)
- 🛠️ Расширить memory_gc.py для хранения успешных episode trajectories

### 2.8 RLVR — Reinforcement Learning with Verifiable Rewards

**Концепция из:** DeepSeek-R1 (arXiv:2501.12948)
**Ссылка:** <https://arxiv.org/pdf/2501.12948>

**Ключевая идея:**
- Замена субъективных preference-based rewards на верифицируемые (математическая корректность, валидность кода, успешность API-вызова)
- Особенно эффективно для маленьких моделей с ограниченным world knowledge

**Применение к OpenClaw Bot:**
- ✅ Награды легко верифицируемы: JSON-валидность, HTTP status codes, SQL-результаты
- ✅ Не требует costly human annotation
- ✅ Может быть реализовано полностью автоматически

---

## 3. Приоритетный план внедрения

### Фаза 1: Фундамент (1–2 недели) 🔴 КРИТИЧНО

| # | Задача | Файлы | VRAM | Сложность |
|---|--------|-------|------|-----------|
| 1 | **Structured Interaction Logging** — JSONL логи всех пар (action, result, correction) | `src/interaction_logger.py` (NEW) | 0 ГБ | Низкая |
| 2 | **Reward Verifier** — автоматическая оценка качества ответов (JSON valid, tool success, SQL result) | `src/reward_verifier.py` (NEW) | 0 ГБ | Средняя |
| 3 | **Memento-style Episode Memory** — сохранение успешных траекторий в Cold_Memory | `src/memory_gc.py` (UPDATE) | 0 ГБ | Низкая |

### Фаза 2: LoRA дообучение (2–4 недели) 🟡 ВАЖНО

| # | Задача | Файлы | VRAM | Сложность |
|---|--------|-------|------|-----------|
| 4 | **Unsloth Setup** — интеграция Unsloth для LoRA training в WSL2 | `scripts/setup_training.py` (NEW) | 14 ГБ | Средняя |
| 5 | **GRPO Training Loop** — обучение Qwen-Coder-7B на корпусе tool calls | `src/grpo_trainer.py` (NEW) | 8–10 ГБ | Высокая |
| 6 | **LoRA Adapter Hot-Swap** — загрузка обученных адаптеров в vLLM | `src/vllm_manager.py` (UPDATE) | +1–2 ГБ | Средняя |

### Фаза 3: Online RL (1–2 месяца) 🟢 БЭКЛОГ

| # | Задача | Файлы | VRAM | Сложность |
|---|--------|-------|------|-----------|
| 7 | **PRM Judge** — маленькая модель-судья (Qwen-1.5B) для оценки в реальном времени | `src/prm_judge.py` (NEW) | 2 ГБ | Высокая |
| 8 | **OPD Pipeline** — Hindsight distillation из пользовательских правок | `src/opd_pipeline.py` (NEW) | 14 ГБ | Очень высокая |
| 9 | **GRPO-λ Adaptive Rewards** — динамическая λ-регулировка для length control | `src/grpo_trainer.py` (UPDATE) | 0 ГБ | Средняя |

---

## 4. Конкретные reward-функции для OpenClaw бригад

### Dmarket Brigade

```python
def dmarket_reward(action: str, result: dict) -> float:
    """Reward для HFT/API задач Dmarket бригады."""
    score = 0.0

    # API вызов вернул 200 OK
    if result.get("http_status") == 200:
        score += 0.25

    # JSON-ответ валиден и содержит ожидаемые поля
    if result.get("json_valid") and result.get("has_required_fields"):
        score += 0.25

    # Время ответа < 2 секунд (latency critical)
    if result.get("latency_ms", 9999) < 2000:
        score += 0.2

    # Profit positive (для trading задач)
    if result.get("profit", 0) > 0:
        score += 0.3

    return min(score, 1.0)
```

### OpenClaw Brigade

```python
def openclaw_reward(action: str, result: dict) -> float:
    """Reward для self-improvement задач OpenClaw бригады."""
    score = 0.0

    # Код прошёл линтер (pnpm check)
    if result.get("lint_passed"):
        score += 0.2

    # Тесты прошли (pnpm test)
    if result.get("tests_passed"):
        score += 0.3

    # TypeScript type-check прошёл (pnpm tsgo)
    if result.get("typecheck_passed"):
        score += 0.2

    # Git commit создан и запушен
    if result.get("commit_created"):
        score += 0.15

    # Archivist уверенность > 7/10
    if result.get("archivist_confidence", 0) > 0.7:
        score += 0.15

    return min(score, 1.0)
```

---

## 5. Ограничения по VRAM и стратегия

### Текущее распределение (инференс)

| Модель | VRAM (AWQ) | Роль |
|--------|-----------|------|
| Qwen2.5-14B-AWQ | ~10 ГБ | General/Planning |
| DeepSeek-R1-14B-AWQ | ~10 ГБ | Analytical/Reasoning |
| Qwen-Coder-7B-AWQ | ~5 ГБ | Executor/Coding |
| Gemma-3-12B-AWQ | ~8 ГБ | Archivist/Summary |

### Стратегия обучения (последовательная)

```
Шаг 1: Остановить vLLM инференс (освободить 16 ГБ)
Шаг 2: Загрузить Unsloth + модель в 4-bit (~14 ГБ для 14B)
Шаг 3: Обучение с LoRA (batch_size=2, gradient_checkpointing=True)
Шаг 4: Сохранить LoRA адаптер (~50–200 МБ)
Шаг 5: Перезапустить vLLM с загруженным адаптером
```

> ⚠️ **ВАЖНО:** Обучение и инференс НЕ МОГУТ работать одновременно на 16 ГБ.
> Рекомендация: Планировать обучение на ночные часы (cron job).

---

## 6. Рекомендуемые датасеты

| Датасет | Назначение | Размер |
|---------|-----------|--------|
| `unsloth/OpenMathReasoning-mini` | GRPO reasoning training | ~50K примеров |
| `mlabonne/FineTome-100k` | Instruction following | 100K примеров |
| **Собственные логи OpenClaw** | Tool use, API calls | Накапливается |
| `glaiveai/glaive-function-calling-v2` | Function/tool calling | 113K примеров |
| `NousResearch/hermes-function-calling-v1` | Structured tool calls | 10K примеров |

---

## 7. Зависимости для обучения

```bash
# Установка в WSL2 Ubuntu (RTX 5060 Ti)
pip install unsloth bitsandbytes accelerate xformers peft trl \
    datasets huggingface_hub sentencepiece transformers torch
```

> **Примечание:** Эти зависимости устанавливаются отдельно от основного `requirements.txt`
> в виртуальное окружение для обучения: `/mnt/d/training_env/`

---

## 8. Сводная таблица техник

| Техника | Статья | VRAM | Сложность | Приоритет | Выгода |
|---------|--------|------|-----------|-----------|--------|
| **GRPO** | arXiv:2503.16219 | 8–14 ГБ | Средняя | 🔴 Высокий | Reasoning +17% accuracy |
| **GRPO-λ** | arXiv:2505.18086 | +0 ГБ | Низкая | 🟡 Средний | -50% длины ответов |
| **LoRA 4-bit** | Unsloth | 8–14 ГБ | Низкая | 🔴 Высокий | -90% VRAM vs full finetune |
| **OPD** | arXiv:2603.10165 | 14 ГБ | Высокая | 🟢 Низкий | Персонализация из правок |
| **PRM Judge** | arXiv:2603.10165 | 2 ГБ | Средняя | 🟡 Средний | Автоматическая оценка |
| **Memento** | arXiv:2508.16153 | 0 ГБ | Низкая | 🔴 Высокий | Обучение без GPU |
| **Self-Distillation** | arXiv:2601.20802 | 14 ГБ | Средняя | 🟡 Средний | 10× ускорение RL |
| **ToolBrain** | arXiv:2510.00023 | 8–14 ГБ | Средняя | 🟡 Средний | RL для tool use |
| **RLVR** | arXiv:2501.12948 | 8–14 ГБ | Средняя | 🔴 Высокий | Verifiable rewards |
| **Prompt Augmentation** | AlphaXiv | 0 ГБ | Низкая | 🟡 Средний | Предотвращение переобучения |

---

## 9. Быстрый старт: Минимальный MVP

Самый быстрый путь к обучению модели в OpenClaw Bot:

### Шаг 1: Собрать данные (0 VRAM, 1 день)
```bash
# Добавить в main.py логирование взаимодействий
python src/interaction_logger.py --mode collect --output /mnt/d/training_data/
```

### Шаг 2: Создать reward functions (0 VRAM, 1 день)
```bash
# Автоматические rewards из верифицируемых сигналов
python src/reward_verifier.py --data /mnt/d/training_data/ --output /mnt/d/rewards/
```

### Шаг 3: Обучить LoRA с GRPO (14 ГБ VRAM, 4–8 часов)
```bash
# Остановить vLLM, запустить обучение
python src/grpo_trainer.py \
    --model Qwen/Qwen2.5-Coder-7B-Instruct \
    --data /mnt/d/training_data/ \
    --rewards /mnt/d/rewards/ \
    --output /mnt/d/lora_adapters/qwen-coder-7b-openclaw/ \
    --epochs 3 \
    --batch-size 2 \
    --lora-rank 32
```

### Шаг 4: Загрузить адаптер в vLLM (5 ГБ VRAM)
```bash
# Перезапустить vLLM с LoRA адаптером
python src/vllm_manager.py \
    --model Qwen/Qwen2.5-Coder-7B-Instruct-AWQ \
    --lora-adapter /mnt/d/lora_adapters/qwen-coder-7b-openclaw/
```

---

## 10. Ссылки

1. **OpenClaw-RL** — <https://arxiv.org/abs/2603.10165> | <https://www.alphaxiv.org/abs/2603.10165>
2. **RL for Reasoning in Small LLMs (GRPO)** — <https://arxiv.org/abs/2503.16219>
3. **GRPO-λ Stable RL** — <https://huggingface.co/papers/2505.18086>
4. **Self-Distillation RL** — <https://www.alphaxiv.org/overview/2601.20802v2>
5. **ToolBrain** — <https://arxiv.org/abs/2510.00023>
6. **Memento** — <https://arxiv.org/abs/2508.16153>
7. **DeepSeek-R1 (RLVR)** — <https://arxiv.org/pdf/2501.12948>
8. **Prompt Augmentation for GRPO** — <https://www.aimodels.fyi/papers/arxiv/prompt-augmentation-scales-up-grpo-training-mathematical>
9. **Unsloth GRPO Training** — <https://unsloth.ai/blog/r1-reasoning>
10. **Qwen3 Fine-tuning Guide** — <https://unsloth.ai/docs/models/qwen3-how-to-run-and-fine-tune>
11. **LoRA Fine-tuning on Small GPU** — <https://heidloff.net/article/fine-tuning-llm-lora-small-gpu/>
12. **Small Language Models Survey** — <https://arxiv.org/html/2501.05465v1>
