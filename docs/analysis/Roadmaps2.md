# 🗺️ OpenClaw Bot — Roadmaps2: Комплексный план улучшений

> Дата создания: 2026-04-03
> Обновлено: 2026-04-03 (добавлены Obsidian + OpenRouter категории)
> Основан на: анализе 25 GitHub-репозиториев + 36 исследовательских запросов по 12 категориям
> Источники: Semantic Scholar, arXiv, Papers With Code, HuggingFace Papers, GitHub

---

## 📑 Содержание

1. [GitHub-репозитории для обучения моделей](#-github-репозитории-для-обучения-моделей)
2. [Категория 1: Архитектура и инфраструктура](#1--архитектура-и-инфраструктура)
3. [Категория 2: Интеллектуальные модули](#2--интеллектуальные-модули)
4. [Категория 3: Системы памяти](#3--системы-памяти)
5. [Категория 4: Deep Research](#4--deep-research)
6. [Категория 5: Безопасность](#5--безопасность)
7. [Категория 6: Производительность](#6--производительность)
8. [Категория 7: Пайплайны и оркестрация](#7--пайплайны-и-оркестрация)
9. [Категория 8: Тестирование и оценка](#8--тестирование-и-оценка)
10. [Категория 9: Обучение моделей](#9--обучение-моделей)
11. [Категория 10: OpenClaw общее (Агентные системы)](#10--openclaw-общее-агентные-системы)
12. [Категория 11: Интеграция с Obsidian](#11--интеграция-с-obsidian)
13. [Категория 12: Улучшение моделей OpenRouter](#12--улучшение-моделей-openrouter)
14. [Сводная таблица улучшений](#-сводная-таблица-улучшений)
15. [Приоритеты реализации](#-приоритеты-реализации)

---

## 🔗 GitHub-репозитории для обучения моделей

### Фреймворки обучения (RL/RLHF/GRPO)

| Репозиторий | ⭐ Stars | Описание | Применение для OpenClaw |
|------------|---------|----------|----------------------|
| [huggingface/trl](https://github.com/huggingface/trl) | 17.9k | Train transformer LMs with RL (PPO, GRPO, DPO) | Основной фреймворк для GRPO обучения Qwen/DeepSeek моделей |
| [verl-project/verl](https://github.com/verl-project/verl) | 20.4k | Volcano Engine RL for LLMs | Масштабируемое RL-обучение с Ray распределением |
| [OpenRLHF/OpenRLHF](https://github.com/OpenRLHF/OpenRLHF) | 9.3k | Scalable Agentic RL Framework (PPO, DAPO, REINFORCE++, vLLM) | Agentic RL с интеграцией vLLM для онлайн-обучения |
| [rllm-org/rllm](https://github.com/rllm-org/rllm) | 5.4k | Democratizing RL for LLMs (coding agent, SWE-agent) | RL для coding-агентов, прямое применение к Dmarket-Dev бригаде |
| [TsinghuaC3I/MARTI](https://github.com/TsinghuaC3I/MARTI) | 472 | Multi-Agent Reinforced Training and Inference | Мульти-агентное RL — обучение бригад взаимодействовать |
| [TIGER-AI-Lab/verl-tool](https://github.com/TIGER-AI-Lab/verl-tool) | 942 | verl для tool-use RL training | Обучение моделей использованию инструментов (MCP tools) |
| [unslothai/notebooks](https://github.com/unslothai/notebooks) | 5.1k | 250+ Fine-tuning & RL Notebooks | Готовые рецепты для LoRA/QLoRA/GRPO обучения |

### Инференс и оптимизация

| Репозиторий | ⭐ Stars | Описание | Применение для OpenClaw |
|------------|---------|----------|----------------------|
| [vllm-project/vllm](https://github.com/vllm-project/vllm) | 75.1k | High-throughput inference engine for LLMs | Основной движок инференса (PagedAttention, continuous batching) |
| [NVIDIA/Model-Optimizer](https://github.com/NVIDIA/Model-Optimizer) | 2.3k | SOTA optimization: quantization, pruning, distillation, speculative decoding | Квантизация и pruning для ускорения RTX 5060 Ti |
| [kvcache-ai/Mooncake](https://github.com/kvcache-ai/Mooncake) | 5k | KV-cache disaggregated serving (Kimi) | Disaggregated KV-cache для multi-model serving |

### Агентные системы

| Репозиторий | ⭐ Stars | Описание | Применение для OpenClaw |
|------------|---------|----------|----------------------|
| [bytedance/deer-flow](https://github.com/bytedance/deer-flow) | 57.1k | Long-horizon SuperAgent with memory + tools | Эталон для long-horizon агентных систем |
| [run-llama/llama_index](https://github.com/run-llama/llama_index) | 48.3k | Leading RAG + agent platform | RAG/agent паттерны для Deep Research |
| [run-llama/rags](https://github.com/run-llama/rags) | 6.5k | Build ChatGPT over your data | RAG поверх пользовательских данных |

### Специализированные

| Репозиторий | ⭐ Stars | Описание | Применение для OpenClaw |
|------------|---------|----------|----------------------|
| [TideDra/lmm-r1](https://github.com/TideDra/lmm-r1) | 845 | Multimodal RL training (DeepSeek-R1) | Мультимодальное обучение для vision-задач |
| [sinanuozdemir/oreilly-llm-rl-alignment](https://github.com/sinanuozdemir/oreilly-llm-rl-alignment) | 59 | RLHF/RLAIF/GRPO training course | Обучающие материалы по GRPO/DPO |
| [0xZee/DeepSeek-R1-FineTuning](https://github.com/0xZee/DeepSeek-R1-FineTuning) | 18 | DeepSeek-R1 fine-tuning with RL + Quantization | Рецепты для дообучения DeepSeek-R1 моделей |
| [Kashif-E/Delve](https://github.com/Kashif-E/Delve) | 8 | Deep research agent with multi-agent pipeline + RAG | Паттерны multi-agent deep research |
| [ss4983/llm-inference-optimization-lab](https://github.com/ss4983/llm-inference-optimization-lab) | 0 | Benchmark vLLM vs TGI: quantization, prefix caching, speculative decoding | Бенчмарки для сравнения оптимизаций инференса |

### Obsidian + AI Integration

| Репозиторий | ⭐ Stars | Описание | Применение для OpenClaw |
|------------|---------|----------|----------------------|
| [khoj-ai/khoj](https://github.com/khoj-ai/khoj) | 33.8k | AI second brain: self-hostable agents, deep research, RAG с Obsidian | Эталон AI second brain с интеграцией Obsidian — паттерны RAG + агент поверх vault |
| [nhaouari/obsidian-textgenerator-plugin](https://github.com/nhaouari/obsidian-textgenerator-plugin) | 1.9k | Text generation в Obsidian через OpenAI, Anthropic, локальные модели | Паттерны multi-provider генерации текста в vault |
| [your-papa/obsidian-Smart2Brain](https://github.com/your-papa/obsidian-Smart2Brain) | 1k | Privacy-focused AI assistant для Obsidian с RAG + embeddings | RAG embeddings поверх Obsidian vault — локальная приватная обработка |
| [eugeneyan/obsidian-copilot](https://github.com/eugeneyan/obsidian-copilot) | 559 | AI copilot для writing and thinking с RAG | Паттерны retrieval из vault для генерации |
| [qgrail/obsidian-ai-assistant](https://github.com/qgrail/obsidian-ai-assistant) | 366 | AI Assistant Plugin для Obsidian (multi-provider) | Архитектура multi-provider AI assistant |
| [Roasbeef/obsidian-claude-code](https://github.com/Roasbeef/obsidian-claude-code) | 196 | Claude AI embedded directly in Obsidian vault | Паттерны прямой AI интеграции в vault |
| [edonyzpc/personal-assistant](https://github.com/edonyzpc/personal-assistant) | 141 | AI agents для автоматического управления Obsidian vault | Автоматизация vault management через агентов |

---

## 1. 🏗️ Архитектура и инфраструктура

### Текущее состояние
- Cloud-only через OpenRouter (5 бесплатных моделей)
- Единый LLM Gateway (`src/llm_gateway.py`)
- 3 бригады: Dmarket-Dev, OpenClaw-Core, Research-Ops
- Иерархия исключений (`src/exceptions.py`)

### Исследуемые статьи (30 статей)
**Темы поиска:**
- Microservice architecture for LLM agent systems
- Cloud-native AI deployment serverless inference
- Event-driven architecture for autonomous agents

### Планируемые улучшения

#### 1.1 Event-Driven Pipeline Architecture
**Что:** Перевод pipeline executor с синхронного pull на event-driven push модель с использованием внутренней шины событий.
**Зачем:** Текущий pipeline executor в `src/pipeline/_core.py` (1648 LOC) работает как монолит. Event-driven архитектура позволит добавлять новые обработчики без модификации core, улучшит тестируемость и позволит реализовать async retry/dead-letter queue.
**Как:** Создать `src/events/bus.py` — легковесная in-process шина событий (asyncio.Queue + подписчики). Каждый шаг pipeline публикует события (`StepComplete`, `StepFailed`, `NeedApproval`). Обработчики подписываются декоратором `@on_event`.
**Источник:** Research on event-driven architectures for autonomous agents.

#### 1.2 Graceful Degradation with Circuit Breaker Patterns
**Что:** Расширение circuit breaker из `openrouter_client.py` на все внешние зависимости (MCP серверы, веб-поиск, память).
**Зачем:** Сейчас circuit breaker работает только для OpenRouter. Если MCP сервер зависает, весь pipeline блокируется.
**Как:** Обобщённый `CircuitBreaker` класс в `src/infra/circuit_breaker.py` с per-service состоянием (closed/half-open/open), configurable thresholds, и health-check probes.
**Источник:** Cloud-native resilience patterns for AI services.

#### 1.3 Config Hot-Reload без перезапуска
**Что:** File-watcher для `config/openclaw_config.json` с мгновенным применением изменений без перезапуска бота.
**Зачем:** Сейчас изменение модели или параметров требует полного рестарта.
**Как:** `watchdog` библиотека + signal handler для плавного обновления конфигурации. Валидация JSON-схемы перед применением.
**Источник:** Cloud-native configuration management patterns.

---

## 2. 🧠 Интеллектуальные модули

### Текущее состояние
- MoA (Mixture-of-Agents) с параллельными пропозерами
- ReAct рассуждения, Constitutional AI, Reflexion
- UCB1 exploration в SmartModelRouter

### Исследуемые статьи (30 статей)
**Темы поиска:**
- Mixture of agents multi-perspective generation
- ReAct reasoning and acting in language models
- Constitutional AI self-improvement alignment

### Планируемые улучшения

#### 2.1 Adaptive MoA — динамическое число пропозеров
**Что:** Автоматическая настройка числа пропозеров в MoA на основе сложности задачи.
**Зачем:** Простые вопросы не нуждаются в 3 пропозерах (waste tokens), сложные — могут выиграть от 5.
**Как:** `TaskComplexityEstimator` оценивает входной запрос (длина, число вопросов, keywords). Простые = 1 пропозер, средние = 3, сложные = 5. Метрика: token_cost / quality_score.
**Источник:** arXiv research on adaptive mixture-of-agents.

#### 2.2 Self-Reflection Loop с Memory
**Что:** Reflexion agent сохраняет историю ошибок в episodic memory и использует их для предотвращения повторных ошибок.
**Зачем:** Текущий Reflexion не имеет долгосрочной памяти — одни и те же ошибки могут повторяться.
**Как:** `ReflexionMemory` в `src/ai/agents/reflexion_memory.py` — SQLite-хранилище пар (ошибка, исправление). При новом запросе — поиск похожих прошлых ошибок через TF-IDF.
**Источник:** Reflexion: Language Agents with Verbal Reinforcement Learning.

#### 2.3 Constitutional AI с пользовательскими правилами
**Что:** Позволить пользователям задавать собственные "конституционные" правила через конфигурацию.
**Зачем:** Разные бригады (Dmarket-Dev vs Research-Ops) имеют разные требования к безопасности.
**Как:** JSON-конфигурация правил в `config/constitutional_rules.json` + парсер в `src/ai/agents/constitutional.py`.
**Источник:** Research on configurable AI alignment.

---

## 3. 📝 Системы памяти

### Текущее состояние
- TieredMemory: hot/warm/cold тиры (MemGPT)
- Memory GC с CRITICAL/IMPORTANT приоритетами
- SuperMemory с эпизодической SQLite памятью
- Mem-α scoring

### Исследуемые статьи (30 статей)
**Темы поиска:**
- Memory augmented language models long-term
- Episodic memory retrieval augmented generation
- Tiered memory management context compression LLM

### Планируемые улучшения

#### 3.1 Knowledge Graph Memory
**Что:** Добавление графовой памяти поверх существующей TieredMemory для хранения связей между фактами.
**Зачем:** Текущая память хранит факты изолированно. Связи (A → B → C) теряются при сжатии.
**Как:** `src/memory/graph_engine.py` уже существует. Расширить его NetworkX-графом связей между MemoryItem. При запросе — traversal графа для контекстных фактов.
**Источник:** Research on knowledge-augmented LLMs with graph memory.

#### 3.2 Adaptive Compression Thresholds
**Что:** Динамические пороги сжатия памяти на основе типа задачи.
**Зачем:** Исследовательские задачи требуют больше контекста (высокий порог), простые вопросы — меньше (низкий порог).
**Как:** `MemoryGC.TOKEN_THRESHOLD` станет динамическим: `route_llm()` передаёт task_type → memory_gc выбирает порог (research=4000, code=3000, general=2400).
**Источник:** Research on context compression for LLMs.

#### 3.3 Cross-Session Memory Sync
**Что:** Синхронизация ключевых фактов между сессиями разных пользователей в пределах бригады.
**Зачем:** Факты, найденные Research-Ops, могут быть полезны для OpenClaw-Core.
**Как:** Shared memory pool с CRITICAL-only фактами, доступный всем ролям бригады. SQLite таблица `shared_facts`.
**Источник:** Research on multi-agent shared memory architectures.

---

## 4. 🔍 Deep Research

### Текущее состояние
- 5 источников (Habr, GitHub, Reddit, StackOverflow, HackerNews)
- 8 парсеров-адаптеров
- Evidence dedup + instant answers + weighted synthesis
- Jina Reader для web_fetch + TTL кэш

### Исследуемые статьи (30 статей)
**Темы поиска:**
- Deep research agent web search synthesis
- Evidence-based reasoning fact verification LLM
- Multi-source information retrieval knowledge synthesis

### Планируемые улучшения

#### 4.1 Academic Source Integration
**Что:** Добавление Semantic Scholar и arXiv как источников в Deep Research pipeline.
**Зачем:** Текущие 5 источников — все неакадемические. Для научных вопросов нужны peer-reviewed статьи.
**Как:** Новые адаптеры в `src/parsers/universal.py` (уже есть semantic_scholar и arxiv). Подключить их к `src/research/_searcher.py` как 6-й и 7-й источники.
**Источник:** Research on multi-source academic information retrieval.

#### 4.2 Iterative Research Deepening
**Что:** Автоматическое углубление исследования: если confidence < 0.7, pipeline запускает второй раунд с уточнёнными запросами.
**Зачем:** Сейчас Deep Research делает один проход. Для сложных тем одного прохода недостаточно.
**Как:** Loop в `_core.py`: после первого синтеза, если `confidence_score < 0.7`, извлечь gaps → сформировать sub-queries → второй поиск → обогатить evidence.
**Источник:** Research on iterative information synthesis.

#### 4.3 Source Credibility Tracking
**Что:** Долгосрочное отслеживание надёжности источников с обучением на обратной связи пользователя.
**Зачем:** Не все источники одинаково надёжны. Если StackOverflow даёт устаревшие ответы, его вес должен снижаться.
**Как:** SQLite таблица `source_reputation` с полями (domain, accuracy_score, last_updated). Обновляется на основе user feedback (thumbs up/down).
**Источник:** Research on source reliability in information retrieval systems.

---

## 5. 🛡️ Безопасность

### Текущее состояние
- Hallucination Detector (heuristic, zero VRAM)
- Prompt Injection Defender
- TruthfulnessScorer
- HITL approval gate
- SQLite аудит-лог

### Исследуемые статьи (30 статей)
**Темы поиска:**
- Hallucination detection mitigation language models
- Prompt injection defense LLM security
- AI safety guardrails truthfulness evaluation

### Планируемые улучшения

#### 5.1 Multi-Layer Injection Defense
**Что:** Трёхслойная защита от prompt injection: input sanitization → context isolation → output validation.
**Зачем:** Текущий defender работает на одном слое (regex). Sophisticated attacks могут обойти regex.
**Как:** Layer 1: regex + keyword detection (существующий). Layer 2: контекстная изоляция (system prompt неизменяем). Layer 3: проверка output на соответствие task scope.
**Источник:** Research on multi-layer LLM security defenses.

#### 5.2 Confidence-Calibrated Responses
**Что:** Автоматическое добавление disclaimers при низкой уверенности модели.
**Зачем:** Текущий TruthfulnessScorer оценивает, но не действует. Пользователь не знает о низкой уверенности.
**Как:** Если `truthfulness_score < 0.6`, автоматически добавить prefix: "⚠️ Ответ может быть неточным. Рекомендую проверить информацию."
**Источник:** Research on calibrated uncertainty in LLMs.

#### 5.3 Automated Red-Teaming
**Что:** Регулярное автоматическое тестирование бота на уязвимости с помощью adversarial prompts.
**Зачем:** Безопасность должна тестироваться проактивно, а не реактивно.
**Как:** Скрипт `scripts/red_team.py` с набором adversarial prompts → запуск через safety_guardrails → отчёт о пройденных/проваленных проверках.
**Источник:** Research on automated red-teaming for LLM systems.

---

## 6. ⚡ Производительность

### Текущее состояние
- Speculative Decoding + SmartRouter + DynamicBatch
- Мультиязычный token counter
- TTL кэш для поиска и intent classifier
- Parallel MoA proposers (asyncio.gather)

### Исследуемые статьи (30 статей)
**Темы поиска:**
- Speculative decoding inference acceleration LLM
- Model quantization efficient inference deployment
- Token budget optimization adaptive computation

### Планируемые улучшения

#### 6.1 Response Streaming
**Что:** Потоковая передача ответов пользователю по мере генерации вместо ожидания полного ответа.
**Зачем:** Среднее время ожидания ответа ~5-15 секунд. Streaming снижает perceived latency до <1 секунды.
**Как:** OpenRouter поддерживает streaming (`stream: true`). Расширить `openrouter_client.py` для чтения SSE chunks → передача в Telegram через `editMessageText`.
**Источник:** Research on streaming inference optimization.

#### 6.2 Intelligent Request Batching
**Что:** Группировка одновременных запросов от разных пользователей в один batch для OpenRouter.
**Зачем:** При нескольких одновременных запросах каждый идёт отдельным HTTP-вызовом. Batching снижает overhead.
**Как:** `RequestBatcher` в `src/infra/batcher.py` — собирает запросы в окно 100ms → отправляет одним запросом → распределяет ответы.
**Источник:** Research on request batching in LLM serving systems.

#### 6.3 Semantic Cache для повторяющихся запросов
**Что:** Кэширование ответов на семантически похожие вопросы (не только exact match).
**Зачем:** Текущий TTL-кэш использует exact key match. "Как дела?" и "Как ваши дела?" — разные ключи.
**Как:** Embedding-based similarity search через sentence-transformers (CPU-only). Если cosine_similarity > 0.95, вернуть кэшированный ответ.
**Источник:** Research on semantic caching for LLM applications (NVIDIA Model-Optimizer patterns).

---

## 7. 🔄 Пайплайны и оркестрация

### Текущее состояние
- Chain-of-Agents pipeline с LATS/AFlow/SAGE
- Context Bridge для передачи контекста
- Auto-rollback при ошибках
- Structured Concurrency через TaskGroup

### Исследуемые статьи (30 статей)
**Темы поиска:**
- Chain-of-agents pipeline orchestration
- Agentic workflow planning execution LLM
- Tool-augmented language model pipeline

### Планируемые улучшения

#### 7.1 Dynamic Pipeline Composition
**Что:** Автоматическая сборка pipeline из модулей на основе анализа задачи вместо фиксированных цепочек.
**Зачем:** Сейчас pipeline фиксирован. Простые вопросы проходят через все стадии (waste).
**Как:** `PipelineComposer` анализирует intent + complexity → выбирает подмножество стадий. Простой вопрос: intent → LLM → response. Сложный: intent → research → MoA → reflexion → safety → response.
**Источник:** Research on dynamic agentic workflow composition (deer-flow patterns).

#### 7.2 Parallel Sub-Task Execution
**Что:** Декомпозиция сложных задач на параллельные подзадачи с последующей агрегацией.
**Зачем:** Сейчас все шаги pipeline выполняются последовательно. Некоторые (research + code analysis) могут быть параллельными.
**Как:** `TaskDecomposer` → разбивает на независимые sub-tasks → `asyncio.gather()` → `ResultAggregator`. DAG зависимостей для управления порядком.
**Источник:** Research on task decomposition in multi-agent systems.

#### 7.3 Pipeline Observability Dashboard
**Что:** Веб-дашборд для мониторинга pipeline execution в реальном времени.
**Зачем:** Сейчас отладка pipeline возможна только через логи. Визуальный дашборд ускорит диагностику.
**Как:** Расширить существующий `src/web/dashboard_views.py` + `src/web/api.py` для real-time pipeline metrics (step latency, token usage, error rates).
**Источник:** Research on observability in agentic systems.

---

## 8. 🧪 Тестирование и оценка

### Текущее состояние
- 123 автотеста в 5 тест-сьютах
- Chaos testing (`tests/phase8/`)
- Safety guardrails тесты (42 теста)
- Mock-based unit tests

### Исследуемые статьи (30 статей)
**Темы поиска:**
- LLM evaluation benchmark testing methodology
- Automated testing AI agent systems
- Adversarial testing robustness language models

### Планируемые улучшения

#### 8.1 Golden Set Evaluation
**Что:** Набор из 100+ эталонных пар (вопрос, ожидаемый_ответ) для автоматической оценки качества ответов.
**Зачем:** Тесты проверяют что код работает, но не проверяют качество ответов LLM.
**Как:** `tests/golden_set/` с JSON-файлами пар. `scripts/eval_golden_set.py` — запускает каждый вопрос → сравнивает с эталоном через BLEU/ROUGE/BERTScore → отчёт.
**Источник:** Research on LLM evaluation benchmarks.

#### 8.2 Regression Testing for Model Updates
**Что:** Автоматическое сравнение качества ответов между версиями моделей при обновлении.
**Зачем:** При обновлении модели (Qwen 14B → 32B) нужно убедиться что качество не упало.
**Как:** Snapshot-тесты: сохранить ответы текущей модели → обновить модель → сравнить ответы → отчёт о деградации.
**Источник:** Research on regression testing for AI systems.

#### 8.3 End-to-End Integration Tests
**Что:** Полные E2E тесты от Telegram-сообщения до ответа с мокированным Telegram API.
**Зачем:** Текущие тесты проверяют отдельные модули. E2E тесты проверяют всю цепочку.
**Как:** `tests/e2e/` с pytest-asyncio, мокированный Telegram Bot API, полный pipeline execution.
**Источник:** Research on end-to-end testing for chatbot systems.

---

## 9. 🎓 Обучение моделей

### Текущее состояние
- Training Orchestrator с 4 фазами
- ExGRPO experience buffer
- Multi-model trainer для 4 моделей
- RLVR rewards + GRPO training

### Исследуемые статьи (30 статей)
**Темы поиска:**
- GRPO group relative policy optimization training
- Reinforcement learning verifiable rewards LLM
- LoRA fine-tuning small language models efficient

### Планируемые улучшения

#### 9.1 Online RL Training Pipeline
**Что:** Переход от offline GRPO к online RL с использованием OpenRLHF/verl для обучения на реальных взаимодействиях.
**Зачем:** Текущий orchestrator генерирует синтетические данные. Online RL учится на реальных диалогах.
**Как:** Интеграция с `verl-project/verl` (20.4k stars): реальные диалоги → reward model оценка → GRPO update → deploy. Требует GPU (RTX 5060 Ti 16GB).
**Источник:** verl-project/verl, OpenRLHF/OpenRLHF.

#### 9.2 Tool-Use RL Training
**Что:** Обучение моделей правильно использовать MCP инструменты через RL.
**Зачем:** Модели часто вызывают инструменты неоптимально или с неправильными параметрами.
**Как:** Интеграция с `TIGER-AI-Lab/verl-tool` (942 stars): создать среду с MCP tools → reward = tool_success_rate × response_quality → GRPO training.
**Источник:** TIGER-AI-Lab/verl-tool.

#### 9.3 Curriculum Learning Pipeline
**Что:** Постепенное усложнение обучающих примеров от простых к сложным.
**Зачем:** Модели учатся лучше когда примеры отсортированы по сложности (easy → hard).
**Как:** `src/training/curriculum.py` — сортировка training data по: длина → число шагов → reward difficulty. 3 этапа: basic (1-turn) → intermediate (multi-turn) → advanced (tool-use + research).
**Источник:** Research on curriculum learning for language models.

---

## 10. 🤖 OpenClaw общее (Агентные системы)

### Текущее состояние
- 20 ролей агентов в 3 бригадах
- 38 ClawHub skills
- Intent classifier с TTL кэшем
- Brigade routing

### Исследуемые статьи (30 статей)
**Темы поиска:**
- Autonomous AI agent system design
- Multi-agent collaboration task decomposition
- Self-improving AI agent continuous learning

### Планируемые улучшения

#### 10.1 Agent Personality Profiles
**Что:** Уникальные "личности" для каждой роли агента с настраиваемым стилем общения.
**Зачем:** Все 20 ролей отвечают одинаковым стилем. Personality profiles сделают ответы более контекстными.
**Как:** `config/agent_personas.json` — для каждой роли: tone (formal/casual), verbosity (concise/detailed), language_mix (ru/en/mixed), emoji_usage.
**Источник:** Research on agent personality in multi-agent systems.

#### 10.2 Inter-Brigade Communication Protocol
**Что:** Протокол для автоматической передачи задач между бригадами.
**Зачем:** Сейчас маршрутизация — одноразовая. Если Dmarket-Dev обнаруживает, что нужен research, он не может перенаправить.
**Как:** `BrigadeRouter.escalate(from_brigade, to_brigade, context)` — передача задачи с полным контекстом. Двусторонний: Dmarket-Dev ↔ Research-Ops.
**Источник:** Research on multi-agent communication protocols (deer-flow, MARTI patterns).

#### 10.3 Continuous Self-Improvement Loop
**Что:** Автоматический сбор метрик качества ответов → анализ трендов → adjustment параметров.
**Зачем:** Бот должен улучшаться автоматически на основе обратной связи.
**Как:** Daily cron: collect user_ratings → compute quality_trends → adjust model_router weights → adjust MoA proposer_count → log changes.
**Источник:** Research on self-improving autonomous agent systems.

---

## 11. 📓 Интеграция с Obsidian

### Текущее состояние
- `src/pipeline/_logic_provider.py` — Obsidian Logic Integration v16.0
- Чтение brigade logic из `.obsidian/claw_logic/<brigade>.md`
- Learning Log — запись обучающих выводов в `.obsidian/Learning_Log.md`
- Vault Map: Concepts, Snippets, Protocols, Logic, Learning_Log
- AFlow Obsidian override chain (`#instruction` tags)
- Автосохранение удачного кода в `.obsidian/Knowledge/Snippets/`

### Исследуемые статьи (30 статей)
**Темы поиска:**
- Knowledge management personal knowledge base AI
- Note-taking retrieval augmented generation LLM
- Zettelkasten knowledge graph linked notes AI

### Планируемые улучшения

#### 11.1 Obsidian Vault как RAG Source
**Что:** Полная индексация Obsidian vault для retrieval-augmented generation при ответах бота.
**Зачем:** Сейчас бот читает только `claw_logic/` файлы. Остальные заметки vault (Concepts, Protocols, ~сотни markdown файлов) не используются для обогащения ответов. Vault содержит накопленные знания, учебные материалы и протоколы, которые могут значительно улучшить качество ответов.
**Как:** (1) `scripts/index_obsidian_vault.py` — сканирование всех `.md` файлов в vault, chunking по заголовкам. (2) Embeddings через sentence-transformers (CPU, `all-MiniLM-L6-v2`). (3) SQLite vector store в `.obsidian/embeddings.db`. (4) При запросе — similarity search по vault → top-5 chunks в контекст LLM. (5) Обновление индекса по `watchdog` при изменении файлов.
**Источник:** khoj-ai/khoj (33.8k stars) — аналогичный RAG поверх Obsidian.

#### 11.2 Obsidian как обучающий инструмент (Self-Teaching Pipeline)
**Что:** Автоматическая генерация обучающих материалов из диалогов бота в формате Obsidian заметок для дообучения моделей.
**Зачем:** Текущий Learning Log записывает только ошибки и фиксы. Нужен полный pipeline: (диалоги → выводы → SFT/GRPO данные → Obsidian заметки → review → тренировка). Obsidian vault становится источником качественных обучающих данных.
**Как:** (1) Расширить `record_learning()` в `_logic_provider.py` для записи не только ошибок, а всех высокооценённых диалогов (reward > 0.7). (2) Формат: YAML frontmatter + Markdown body → `.obsidian/Training_Data/`. (3) `scripts/obsidian_to_training.py` — конвертация заметок в JSONL для SFT/GRPO. (4) Human-in-the-loop review через Obsidian UI (добавить тег `#approved` → включить в тренировку). (5) Периодический export в `data/training/` для `training_orchestrator.py`.
**Источник:** Research on human-in-the-loop data curation via knowledge management tools.

#### 11.3 Двусторонняя синхронизация знаний Obsidian ↔ Memory
**Что:** Автоматическая синхронизация между TieredMemory бота и Obsidian vault — факты из памяти бота записываются в vault, заметки vault загружаются в memory.
**Зачем:** Сейчас память бота и Obsidian vault — изолированные хранилища. CRITICAL факты из `memory_gc.py` не отражены в vault, а протоколы из vault не загружены в hot memory.
**Как:** (1) `MemoryGC.on_promote(CRITICAL)` → записать факт в `.obsidian/Knowledge/Facts/<date>.md`. (2) При старте бота — загрузить все `.obsidian/Knowledge/Protocols/*.md` в hot memory как system-level facts. (3) Cron (ежечасно): diff memory vs vault → sync новые факты в обе стороны. (4) Conflict resolution: vault wins (human-edited считается authority).
**Источник:** obsidian-Smart2Brain, eugeneyan/obsidian-copilot — паттерны bidirectional sync.

#### 11.4 Obsidian Graph для контекстной навигации
**Что:** Использование графа связей Obsidian (`[[ссылки]]`) для контекстной навигации при ответах.
**Зачем:** Obsidian vault содержит граф связей между заметками. Если пользователь спрашивает о "GRPO training", бот может найти заметку "GRPO" → перейти по связям к "Reward Model", "LoRA", "Qwen" → обогатить контекст.
**Как:** (1) Парсинг `[[wiki links]]` из всех `.md` файлов vault. (2) Построение NetworkX графа связей (аналогично `src/memory/graph_engine.py`). (3) При запросе: найти ближайшую заметку → BFS по графу (depth=2) → собрать контекст из связанных заметок.
**Источник:** Research on Zettelkasten + AI knowledge graph traversal.

#### 11.5 Obsidian Templates для стандартизации данных
**Что:** Obsidian Templates для стандартизации структуры обучающих данных, протоколов, и логов.
**Зачем:** Сейчас Learning Log — плоская markdown таблица. Templates позволят создавать структурированные заметки с YAML frontmatter, tags, и links.
**Как:** (1) `.obsidian/Templates/training_example.md` — шаблон с frontmatter: model, reward_score, task_type, date. (2) `.obsidian/Templates/protocol.md` — шаблон протокола бригады. (3) `_logic_provider.py` использует templates при записи. (4) `scripts/obsidian_to_training.py` парсит YAML frontmatter для фильтрации.
**Источник:** nhaouari/obsidian-textgenerator-plugin — паттерны structured templates.

---

## 12. 🔀 Улучшение моделей OpenRouter

### Текущее состояние
- Основная модель: `nvidia/nemotron-3-super-120b-a12b:free` (12 из 15 ролей)
- Вторичная: `arcee-ai/trinity-large-preview:free` (2 роли: research-brigade-lead, test-strategist)
- Лёгкая: `arcee-ai/trinity-mini:free` (3 роли: test-runner, code-reviewer, log-analyst)
- OpenRouter через `src/openrouter_client.py` с circuit breaker + retry
- SmartModelRouter с UCB1 exploration (`src/ai/inference/router.py`)
- Token counter (multilingual-aware) для оценки стоимости

### Исследуемые статьи (30 статей)
**Темы поиска:**
- LLM model routing selection optimization API
- Multi-model ensemble routing inference cost
- Model evaluation comparison benchmark selection

### Планируемые улучшения

#### 12.1 Intelligent Model Fallback Chain
**Что:** Автоматическая цепочка fallback моделей при недоступности основной: nemotron-120b → trinity-large → trinity-mini → deepseek:free.
**Зачем:** Сейчас при недоступности одной модели circuit breaker просто фейлит запрос. Нужен graceful fallback на альтернативную модель.
**Как:** (1) Конфигурация fallback chains в `config/openclaw_config.json` для каждой роли. (2) Расширить `openrouter_client.py`: если модель вернула 429/503/timeout → попробовать следующую в chain. (3) Логирование fallback events для анализа стабильности моделей. (4) Метрика: fallback_rate per model per hour.
**Источник:** Research on multi-model routing and failover patterns.

#### 12.2 Dynamic Model Selection по типу задачи
**Что:** Автоматический выбор оптимальной модели на основе типа задачи вместо фиксированного маппинга role → model.
**Зачем:** Сейчас все 12 основных ролей используют nemotron-120b, хотя для простых задач (intent classification, short answers) хватит trinity-mini. Это экономит rate limits и ускоряет ответы.
**Как:** (1) Расширить `SmartModelRouter` в `src/ai/inference/router.py`: task_type = `route_llm()` → complexity_score → выбор модели. (2) Маппинг: simple (< 50 tokens input) → trinity-mini, medium → trinity-large, complex (research, code) → nemotron-120b. (3) UCB1 exploration для обнаружения лучших моделей для каждого task_type.
**Источник:** Research on adaptive model routing for cost optimization.

#### 12.3 Model Quality Monitoring Dashboard
**Что:** Автоматический мониторинг качества ответов каждой модели с метриками и алертами.
**Зачем:** Бесплатные модели OpenRouter могут деградировать без предупреждения (версионирование, throttling). Нужен мониторинг.
**Как:** (1) `src/monitoring/model_quality.py` — сбор метрик: response_time, token_count, user_rating, safety_score per model. (2) SQLite таблица `model_metrics`. (3) Ежедневный анализ трендов: если quality_score модели упал > 15% за неделю → алерт в Telegram. (4) Автоматическое переключение на backup модель при sustained degradation.
**Источник:** Research on LLM monitoring and quality assurance.

#### 12.4 Prompt Optimization per Model
**Что:** Адаптация system prompt и форматирования под каждую конкретную модель OpenRouter.
**Зачем:** Nemotron-120b, Trinity-large, и Trinity-mini имеют разные сильные/слабые стороны и оптимальные prompt formats. Единый prompt не оптимален.
**Как:** (1) `config/model_prompts.json` — per-model system prompt templates с переменными. (2) Nemotron: подробные инструкции (128k контекст), Trinity-large: среднее, Trinity-mini: лаконичные (32k контекст). (3) `_core.py` подставляет prompt template по текущей модели. (4) A/B testing: 50/50 split → compare quality scores.
**Источник:** Research on model-specific prompt engineering.

#### 12.5 OpenRouter Cost Analytics
**Что:** Детальная аналитика расхода токенов и условной стоимости по моделям, ролям, и бригадам.
**Зачем:** Бесплатные модели имеют rate limits. Нужно понимать где тратятся токены и как оптимизировать.
**Как:** (1) Расширить `interaction_logger.py` для записи: model, input_tokens, output_tokens, latency, role, brigade. (2) `scripts/analytics_report.py` — еженедельный отчёт: top-10 expensive queries, tokens per brigade, model utilization. (3) Визуализация в Obsidian: `.obsidian/Analytics/weekly_report.md`.
**Источник:** Research on LLM cost optimization and usage analytics.

---

## 📊 Сводная таблица улучшений

| # | Категория | Улучшение | Приоритет | Сложность | Источник |
|---|-----------|-----------|-----------|-----------|----------|
| 1.1 | Архитектура | Event-Driven Pipeline | 🟡 Средний | Высокая | Research papers |
| 1.2 | Архитектура | Graceful Degradation | 🟢 Высокий | Средняя | Cloud-native patterns |
| 1.3 | Архитектура | Config Hot-Reload | 🟢 Высокий | Низкая | Cloud-native patterns |
| 2.1 | Интеллект | Adaptive MoA | 🟡 Средний | Средняя | arXiv papers |
| 2.2 | Интеллект | Self-Reflection Memory | 🟡 Средний | Средняя | Reflexion paper |
| 2.3 | Интеллект | Custom Constitutional Rules | 🟢 Высокий | Низкая | Constitutional AI |
| 3.1 | Память | Knowledge Graph Memory | 🟡 Средний | Высокая | Memory research |
| 3.2 | Память | Adaptive Compression | 🟢 Высокий | Низкая | LLM memory papers |
| 3.3 | Память | Cross-Session Sync | 🔴 Низкий | Средняя | Multi-agent memory |
| 4.1 | Research | Academic Sources | 🟢 Высокий | Низкая | Semantic Scholar API |
| 4.2 | Research | Iterative Deepening | 🟡 Средний | Средняя | IR research |
| 4.3 | Research | Source Credibility | 🟡 Средний | Средняя | Credibility research |
| 5.1 | Безопасность | Multi-Layer Injection Defense | 🟢 Высокий | Средняя | Security papers |
| 5.2 | Безопасность | Confidence Disclaimers | 🟢 Высокий | Низкая | Calibration research |
| 5.3 | Безопасность | Automated Red-Teaming | 🟡 Средний | Средняя | Red-team research |
| 6.1 | Производительность | Response Streaming | 🟢 Высокий | Средняя | Streaming inference |
| 6.2 | Производительность | Request Batching | 🟡 Средний | Средняя | vLLM patterns |
| 6.3 | Производительность | Semantic Cache | 🟡 Средний | Высокая | NVIDIA patterns |
| 7.1 | Пайплайны | Dynamic Composition | 🟡 Средний | Высокая | deer-flow |
| 7.2 | Пайплайны | Parallel Sub-Tasks | 🟢 Высокий | Средняя | Task decomposition |
| 7.3 | Пайплайны | Observability Dashboard | 🔴 Низкий | Средняя | Observability research |
| 8.1 | Тесты | Golden Set Evaluation | 🟢 Высокий | Средняя | Eval benchmarks |
| 8.2 | Тесты | Regression Testing | 🟡 Средний | Средняя | AI testing research |
| 8.3 | Тесты | E2E Integration Tests | 🟢 Высокий | Высокая | E2E testing |
| 9.1 | Обучение | Online RL (verl) | 🟢 Высокий | Высокая | verl/OpenRLHF |
| 9.2 | Обучение | Tool-Use RL | 🟡 Средний | Высокая | verl-tool |
| 9.3 | Обучение | Curriculum Learning | 🟡 Средний | Средняя | CL research |
| 10.1 | OpenClaw | Agent Personalities | 🔴 Низкий | Низкая | Agent design |
| 10.2 | OpenClaw | Inter-Brigade Protocol | 🟡 Средний | Средняя | MARTI patterns |
| 10.3 | OpenClaw | Self-Improvement Loop | 🟢 Высокий | Высокая | Self-improving AI |
| 11.1 | Obsidian | Vault как RAG Source | 🟢 Высокий | Средняя | khoj-ai/khoj |
| 11.2 | Obsidian | Self-Teaching Pipeline | 🟢 Высокий | Высокая | Training research |
| 11.3 | Obsidian | Двусторонняя синхронизация | 🟡 Средний | Средняя | Smart2Brain |
| 11.4 | Obsidian | Graph навигация | 🟡 Средний | Средняя | Zettelkasten research |
| 11.5 | Obsidian | Templates для данных | 🟢 Высокий | Низкая | TextGenerator plugin |
| 12.1 | OpenRouter | Fallback Chain | 🟢 Высокий | Низкая | Routing research |
| 12.2 | OpenRouter | Dynamic Model Selection | 🟢 Высокий | Средняя | Cost optimization |
| 12.3 | OpenRouter | Quality Monitoring | 🟢 Высокий | Средняя | LLM monitoring |
| 12.4 | OpenRouter | Prompt per Model | 🟡 Средний | Средняя | Prompt engineering |
| 12.5 | OpenRouter | Cost Analytics | 🟡 Средний | Низкая | Analytics research |

---

## 🎯 Приоритеты реализации

### Волна 1 — Quick Wins (1-2 дня каждое)
1. **1.3** Config Hot-Reload
2. **2.3** Custom Constitutional Rules
3. **3.2** Adaptive Compression Thresholds
4. **4.1** Academic Source Integration (Semantic Scholar + arXiv)
5. **5.2** Confidence-Calibrated Responses
6. **11.5** Obsidian Templates для стандартизации данных
7. **12.1** Intelligent Model Fallback Chain

### Волна 2 — Core Improvements (3-5 дней каждое)
8. **1.2** Graceful Degradation Circuit Breakers
9. **5.1** Multi-Layer Injection Defense
10. **6.1** Response Streaming
11. **7.2** Parallel Sub-Task Execution
12. **8.1** Golden Set Evaluation
13. **11.1** Obsidian Vault как RAG Source
14. **12.2** Dynamic Model Selection по типу задачи
15. **12.3** Model Quality Monitoring

### Волна 3 — Major Features (1-2 недели каждое)
16. **9.1** Online RL Training (verl integration)
17. **2.1** Adaptive MoA
18. **10.3** Self-Improvement Loop
19. **8.3** E2E Integration Tests
20. **3.1** Knowledge Graph Memory
21. **11.2** Obsidian Self-Teaching Pipeline
22. **11.3** Двусторонняя синхронизация Obsidian ↔ Memory

### Волна 4 — Advanced (2+ недели)
23. **1.1** Event-Driven Pipeline
24. **9.2** Tool-Use RL Training
25. **6.3** Semantic Cache
26. **7.1** Dynamic Pipeline Composition
27. **9.3** Curriculum Learning
28. **11.4** Obsidian Graph навигация
29. **12.4** Prompt Optimization per Model

---

## 📌 Как запустить парсер

```bash
# Полный парсинг (30 статей на категорию, 4 источника, 12 категорий)
python scripts/research_comprehensive_parser.py --limit 30

# Быстрый тест (dry run)
python scripts/research_comprehensive_parser.py --dry-run

# Пользовательский лимит (10 статей на категорию)
python scripts/research_comprehensive_parser.py --limit 10 --limit-per-source 5

# Тесты
python -m pytest tests/test_comprehensive_research_parser.py -v
```

---

> 📝 **Примечание:** Этот roadmap — живой документ. Приоритеты могут меняться на основе обратной связи пользователей и результатов исследований. Парсер `research_comprehensive_parser.py` можно перезапускать для обновления статей.

> 🆕 **Обновление 2026-04-03:** Добавлены категории 11 (Obsidian) и 12 (OpenRouter). Парсер расширен до 12 категорий × 3 темы × 4 источника = 144 поисковых запроса. Добавлены 7 GitHub-репозиториев для Obsidian + AI интеграции.
