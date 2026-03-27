# OpenClaw — Autonomous Multi-Agent AI Framework

> **Blackwell Edition · RTX 5060 Ti 16 GB · vLLM 0.17.1 · Chain-of-Agents**

OpenClaw — автономный мульти-агентный Telegram/Discord-бот, построенный на архитектуре **Chain-of-Agents** с гибридным LLM-инференсом. Основной провайдер — OpenRouter (cloud, multi-model routing); fallback — vLLM v0.17.1 (WSL2, локальный GPU). Единый вход — `route_llm()` (Unified LLM Gateway).

```
Telegram/Discord ──▶ OpenClawGateway ──▶ Safety Filter ──▶ Intent Classifier ──▶ Brigade Pipeline
  text/voice/doc      │                    │                                         │
                      │               Injection?               ┌─────────────────────┘
                      │               Blocked ✗                 ▼
                      │    ┌──── SmartModelRouter ──── Memory Recall (SuperMemory + RAG + MCP)
                      │    │                                    ▼
                      │    │                   Planner → Foreman → Executor(s) → Auditor → Archivist
                      │    │                                        ▲            │
                      ▼    ▼                                        │       Hallucination
             OpenRouter / vLLM ◀────────────────────────────────────┘       Detector
             (Metrics Collector)        Context Bridge              │
                                                              Reflexion Fallback
```

---

## Архитектура

### Компоненты

| Компонент                   | Технология                                                     | Назначение                                                                                             |
| --------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Telegram Gateway**        | aiogram 3.26, Python 3.14                                      | Текст, голос (STT), документы, inline-кнопки, стриминг ответов                                         |
| **Safety Filter**           | PromptInjectionDefender (5-layer)                              | Блокировка injection/jailbreak на входе                                                                |
| **Intent Classifier**       | LLM + keyword fallback + LRU-кеш                               | Маршрутизация задач в бригаду (Dmarket/OpenClaw/General)                                               |
| **Pipeline Executor**       | Chain-of-Agents с параллельными исполнителями                  | Последовательное выполнение ролей в бригаде                                                            |
| **Hallucination Detector**  | HallucinationDetector (heuristic)                              | Детекция галлюцинаций на выходе пайплайна                                                              |
| **vLLM Server**             | vLLM 0.17.1, WSL2 Ubuntu 24.04                                 | OpenAI-совместимый API (`localhost:8000/v1`)                                                           |
| **Context Bridge**          | SQLite + ChromaDB (3 слоя)                                     | Сохранение контекста между шагами и моделями                                                           |
| **AutoRollback**            | HMAC-signed git checkpoints                                    | Автооткат конфигурации при ошибках hot-reload                                                          |
| **Brigade REST API**        | FastAPI, порт 8765                                             | HTTP/SSE-интерфейс для внешних клиентов                                                                |
| **Tailscale Monitor**       | Tailscale CLI                                                  | VPN mesh-мониторинг, remote vLLM routing                                                               |
| **Prometheus**              | prometheus_client, порт 9090                                   | Метрики: промпты, VRAM, модели                                                                         |
| **Memory GC**               | Anchored Iterative Compressor v2                               | Компрессия контекста, 24ч архивация в Cold_Memory                                                      |
| **SmartModelRouter**        | Task classification + quality scoring                          | Авто-выбор модели по типу задачи (code/math/creative/general)                                          |
| **SuperMemory**             | SQLite + ChromaDB (3-tier: hot/warm/cold)                      | Персистентная память с автовоспоминанием на входе пайплайна                                            |
| **RAG Engine**              | ChromaDB + markdown chunking                                   | Индексация docs/ и .memory-bank/, семантический поиск                                                  |
| **Inference Metrics**       | InferenceMetricsCollector                                      | TPS, TTFT, ITL — реал-тайм метрики каждого вызова                                                      |
| **Token Budget**            | AdaptiveTokenBudget                                            | Динамическая оценка бюджета токенов по задаче                                                          |
| **Reflexion**               | ReflexionAgent (self-reflection)                               | Авто-исправление при ошибке пайплайна (до 2 попыток)                                                   |
| **Scheduler**               | APScheduler (cron + interval)                                  | Фоновые задачи: GC, health-check, пользовательские cron-задачи                                         |
| **Discord Handler**         | discord.py 2.x                                                 | Второй канал: Discord бот (mention/prefix trigger, streaming edits)                                    |
| **TTS Engine**              | OpenAI TTS / ElevenLabs / edge-tts                             | Синтез речи с fallback-цепочкой провайдеров                                                            |
| **Unified LLM Gateway**     | `route_llm()` + Circuit Breaker                                | Единый вход для всего инференса: OpenRouter → vLLM fallback                                            |
| **ReAct Reasoner**          | ReActReasoner (chain-of-thought + tools)                       | Reasoning loop для Executor_Tools: Think → Act → Observe                                               |
| **Constitutional Guard**    | ConstitutionalChecker (safety rules)                           | Финальная проверка безопасности ответа перед отправкой                                                 |
| **Auditor Self-Reflection** | \_AUDITOR_PROTOCOL (self-check)                                | 5-точечная внутренняя рецензия (полнота, факты, безопасность)                                          |
| **Pydantic Validation**     | PipelineResult / PipelineStepResult                            | Структурная валидация результатов каждого шага пайплайна                                               |
| **HITL Approval Gate**      | `assess_risk()` + Telegram/Discord inline buttons              | Пауза пайплайна при high-risk действиях (удаление файлов, sudo, бюджет > $0.05)                        |
| **Mission Control**         | FastAPI + WebSocket (порт 8800)                                | Observability dashboard: `/status`, `/logs/live`, `/memory/stats`, `/sandbox/active`, `/pipeline/tree` |
| **Vision Pipeline**         | `route_llm(image_base64=...)` + auto-routing                   | Мультимодальный инференс: фото → Vision LLM (Llama-4-Maverick / Qwen3-VL)                              |
| **ClawHub Marketplace**     | `ClawHubClient.publish_skill()` / `fetch_marketplace_skills()` | Публикация/синхронизация Sandbox скиллов с ClawHub маркетплейсом                                       |

### Pipeline (Chain-of-Agents)

Каждая задача проходит через цепочку специализированных ролей:

```
1. Planner      — Глобальный план в формате STAR (Situation→Task→Action→Result)
2. Foreman      — Декомпозиция в структурированные JSON-задачи
3. Executor(s)  — Выполнение задач (параллельно: Executor_API + Executor_Parser) + ReAct reasoning
4. Auditor      — Self-Reflection ревью: полнота, факты, безопасность, галлюцинации
5. Archivist    — Итоговый отчёт → Telegram/Discord (стриминг ответа)
6. Constitutional Guard — Финальная safety-проверка перед отправкой
```

Контекст между шагами: `compress_for_next_step()` → `max_model_len = 8192` токенов. При переполнении — `_emergency_compress()`.

**Self-Healing:** при ошибке пайплайна — автоматический retry. Если результат пуст или содержит ошибку → **Reflexion fallback** (ReflexionAgent: reflect → correct → resubmit, до 2 итераций). Если Planner просит уточнение → `ask_user` loop с ForceReply в Telegram.

**Auto Memory Recall:** перед первым шагом пайплайна автоматически вызывается SuperMemory.recall() + RAG.query() + MCP memory_search — релевантный контекст подаётся как seed для context_briefing.

---

## Бригады и роли (20 ролей)

OpenClaw использует систему **бригад** — независимых конвейеров с персонализированными ролями. Каждая роль имеет уникальный system prompt с характером, доменом и ограничениями.

### Dmarket Brigade (11 ролей — HFT, Trading, API)

| Роль                  | Модель                |  T° | Описание                                         |
| --------------------- | --------------------- | --: | ------------------------------------------------ |
| **Planner**           | DeepSeek-R1 14B AWQ   | 0.1 | Оркестратор «Аркадий» — торговый план в STAR     |
| **Foreman**           | Qwen2.5-Coder 14B AWQ | 0.1 | Прораб — JSON-задачи для каждого Executor        |
| **Executor_API**      | Qwen2.5-Coder 14B AWQ | 0.2 | REST/WebSocket, DMarket HMAC, rate-limit         |
| **Executor_Parser**   | Qwen2.5-Coder 14B AWQ | 0.2 | Парсинг market feeds (JSON, CSV, Buff163)        |
| **Executor_Logic**    | Qwen2.5-Coder 14B AWQ | 0.1 | Торговая логика: SMA, stop-loss, position sizing |
| **Auditor**           | DeepSeek-R1 14B AWQ   | 0.1 | «Зубарев» — параноидальный security audit        |
| **Archivist**         | Qwen2.5-Coder 14B AWQ | 0.5 | Верификация → человеческий текст → Telegram      |
| **Risk_Analyst**      | DeepSeek-R1 14B AWQ   | 0.0 | Drawdown, position risk, daily loss limit        |
| **Latency_Optimizer** | Qwen2.5-Coder 14B AWQ | 0.2 | ms-оптимизация: async I/O, connection pooling    |
| **Data_Analyst**      | Qwen2.5-Coder 14B AWQ | 0.1 | Статистика, аномалии, confidence intervals       |
| **Debugger**          | Qwen2.5-Coder 14B AWQ | 0.1 | Root cause → minimal fix (stack trace анализ)    |

### OpenClaw Brigade (9 ролей — Framework, Infra, Self-improvement)

| Роль                     | Модель                |  T° | Описание                                               |
| ------------------------ | --------------------- | --: | ------------------------------------------------------ |
| **Planner**              | DeepSeek-R1 14B AWQ   | 0.1 | Архитектор «Аркадий» — глобальный план                 |
| **Foreman**              | Qwen2.5-Coder 14B AWQ | 0.1 | DevOps-лид — JSON-подзадачи                            |
| **Executor_Architect**   | Qwen2.5-Coder 14B AWQ | 0.2 | Ядро фреймворка: DRY, SOLID, KISS                      |
| **Executor_Tools**       | Qwen2.5-Coder 14B AWQ | 0.2 | Скрипты, MCP tools, CLI утилиты                        |
| **Executor_Integration** | Qwen2.5-Coder 14B AWQ | 0.3 | Интеграция модулей, prompt chains                      |
| **Auditor**              | DeepSeek-R1 14B AWQ   | 0.1 | Security audit: injection, path traversal, credentials |
| **Archivist**            | Qwen2.5-Coder 14B AWQ | 0.5 | CHANGELOG, README, git commit messages                 |
| **State_Manager**        | Qwen2.5-Coder 14B AWQ | 0.2 | ChromaDB, context compression, RAG-иерархия            |
| **Test_Writer**          | Qwen2.5-Coder 14B AWQ | 0.2 | pytest/vitest, edge cases, mocking vLLM                |

**Модели:** 15 ролей → `Qwen/Qwen2.5-Coder-14B-Instruct-AWQ`, 5 ролей (reasoning-heavy) → `casperhansen/deepseek-r1-distill-qwen-14b-awq`.

---

## Intent Classification

Трёхуровневая маршрутизация:

1. **LLM-классификатор** — промпт → vLLM → `{Dmarket, OpenClaw, General}` (таймаут 10 сек)
2. **Keyword fallback** — regex по ключевым словам:
   - `Dmarket`: buy, sell, trade, price, arbitrage, skin, inventory, hft
   - `OpenClaw`: config, pipeline, model, vllm, brigade, role, mcp, plugin
3. **LRU-кеш** (500 записей) — повторные промпты не вызывают LLM

`General` → fast path через OpenClaw с упрощённой цепочкой.

---

## vLLM Inference Engine

### Конфигурация

| Параметр                   | Значение                                         |
| -------------------------- | ------------------------------------------------ |
| **Модель**                 | `Qwen/Qwen2.5-Coder-14B-Instruct-AWQ` (9.38 GiB) |
| **Квантизация**            | AWQ Marlin kernel (4-bit, auto-detect)           |
| **Attention**              | FLASH_ATTN v2                                    |
| **max_model_len**          | 8 192 токенов                                    |
| **gpu_memory_utilization** | 0.92                                             |
| **Chunked Prefill**        | 2 048 batch tokens                               |
| **enforce_eager**          | true (без CUDAGraphs)                            |
| **Prefix Caching**         | APC, sha256 block hashing                        |
| **Async Scheduling**       | enabled                                          |

### Производительность (бенчмарк 2026-03-22)

| Тест                            | Токены | Время | Скорость       |
| ------------------------------- | ------ | ----- | -------------- |
| Короткий ответ (117-169 tok)    | ~140   | ~7s   | 19-20 tok/s    |
| Код (310-400 tok)               | ~355   | ~14s  | 25-27 tok/s    |
| Развёрнутый ответ (389-418 tok) | ~404   | ~15s  | 26-27 tok/s    |
| **Average**                     | —      | —     | **24.2 tok/s** |
| **Peak**                        | —      | —     | **26.7 tok/s** |

### Хранение (WSL2)

```
/mnt/d/vllm_models/     — HF_HOME, кеш моделей (~9.4 GiB)
/mnt/d/vllm_env/        — Python 3.12 venv с vLLM 0.17.1
/mnt/d/lora_adapters/   — LoRA-адаптеры (hot-swap ready)
```

---

## Mission Control (Observability Dashboard)

FastAPI-приложение на порту **8800** для реал-тайм наблюдаемости бота.

### Эндпоинты

| Метод | Путь                     | Описание                                                                         |
| ----- | ------------------------ | -------------------------------------------------------------------------------- |
| GET   | `/status`                | Общий статус бота: uptime, cloud mode, pending HITL approvals, inference metrics |
| GET   | `/logs/recent?limit=100` | Последние 100 записей из structlog ring-buffer                                   |
| WS    | `/logs/live`             | WebSocket — стриминг логов в реальном времени                                    |
| GET   | `/memory/stats`          | Статистика SuperMemory, RAG Engine, Context Bridge                               |
| GET   | `/sandbox/active`        | Активные sandbox-сессии и список скиллов в SkillLibrary                          |
| GET   | `/pipeline/tree`         | Дерево мыслей последнего пайплайна (Thought → Action → Observation)              |

### Запуск

Dashboard стартует автоматически вместе с ботом (если `dashboard.enabled: true` в конфиге). Для ручного запуска:

```bash
uvicorn src.web.api:app --host 127.0.0.1 --port 8800
```

### Интеграция

- **structlog**: Все логи бота через `dashboard_log_processor` зеркалируются в WebSocket-клиенты.
- **HITL**: Pending approvals отображаются в `/status`.
- **Pipeline Tree**: Каждый шаг ReAct (Thought→Action→Observation) записывается через `record_pipeline_tree()`.

---

## HITL (Human-in-the-Loop) Approval Gate

Механизм безопасности для высокорисковых действий.

### Как работает

1. `route_llm()` анализирует промпт через `assess_risk()`
2. Если обнаружены опасные паттерны (rm -rf, sudo, DROP TABLE) или бюджет > $0.05 — пайплайн **ставится на паузу**
3. Бот отправляет сообщение с inline-кнопками: **[✅ Approve] [❌ Reject] [📝 Edit Plan]**
4. Оператор принимает решение → пайплайн продолжается или отменяется

### Конфигурация (`config/openclaw_config.json`)

```json
{
  "hitl": {
    "enabled": true,
    "budget_threshold": 0.05,
    "timeout_sec": 300
  }
}
```

---

## Vision Pipeline

Мультимодальный инференс: фото → Vision LLM → текстовый анализ.

### Поддерживаемые модели

| Модель                             | Провайдер  | Назначение                            |
| ---------------------------------- | ---------- | ------------------------------------- |
| `meta-llama/llama-4-maverick:free` | OpenRouter | Основная Vision-модель (auto-routing) |
| `qwen/qwen3-vl-235b-thinking:free` | OpenRouter | Альтернативная (extended thinking)    |

### Как использовать

1. Отправьте фото в Telegram/Discord
2. Добавьте caption (опционально) — промпт для анализа
3. SmartModelRouter автоматически выберет Vision-модель
4. Результат анализа придёт в чат

### API

```python
from src.llm_gateway import route_llm

result = await route_llm(
    "Что на этом изображении?",
    image_base64="...",  # или image_url="https://..."
    task_type="vision",
)
```

---

## Обработка ввода

### Текст

Любое текстовое сообщение (не команда) → Intent Classification → полный Chain-of-Agents pipeline → стриминг ответа в Telegram.

### Голосовые сообщения (STT)

Три fallback-бекенда транскрипции:

1. **vLLM Whisper** (`/v1/audio/transcriptions`) — если Whisper-модель загружена
2. **whisper-cpp** (локальный процесс) — fallback
3. **openai-whisper** (Python-библиотека) — финальный fallback

Транскрибированный текст → pipeline как обычный промпт.

### Документы

Поддерживаемые форматы: PDF, TXT, MD, PY, JSON, CSV, LOG.

- **PDF**: PyMuPDF → pdfminer.six (fallback chain)
- **Текстовые**: прямое чтение с определением кодировки (UTF-8 → CP-1251)

Извлечённый текст (до 3 000 символов) → pipeline с контекстом «Проанализируй документ».

### Фотографии

Изображения кодируются в base64 → отправляются в vLLM как multimodal input если модель поддерживает vision, иначе — fallback описание.

---

## Безопасность

### Prompt Injection Defense (вход пайплайна)

5-уровневый анализ (`PromptInjectionDefender`):

1. **Injection patterns** — system prompt override, role hijacking
2. **Jailbreak patterns** — DAN, hypothetical scenarios
3. **Encoding evasion** — base64, unicode tricks
4. **Tool output injection** — malicious tool responses
5. **SecurityAuditor leak** — попытки вытянуть system prompt

Пороги: `high/critical` → блокировка, `medium/low` → предупреждение + обработка.

### Hallucination Detection (выход пайплайна)

Heuristic-анализ (`HallucinationDetector`):

- Маркеры самоуверенности («безусловно», «гарантированно»)
- Фейковые ссылки (DOI, arxiv без реальных ID)
- Темпоральные утверждения (конкретные даты без источника)
- Подозрительные числа (сверхточные проценты)
- Внутренняя противоречивость

**0 VRAM** — чистый regex/Python. Risk level: low/medium/high.

### Code Validator

**semgrep** + **bandit** + **ruff** — проверка сгенерированного кода после guardrail loop для ролей `Executor_*`.

### AutoRollback (конфигурация)

- HMAC-signed git checkpoint перед hot-reload конфига
- py_compile валидация изменённых файлов
- Автоматический `git checkout` при ошибке загрузки
- Git hooks отключены на время операции

### Доступ

- Бот отвечает **только** `admin_chat_id` (single-user mode)
- Lock-файл предотвращает запуск нескольких инстансов

---

## Context Bridge (3 слоя)

Передача контекста при смене моделей (Qwen ↔ DeepSeek):

| Слой              | Backend                           | Назначение                                 |
| ----------------- | --------------------------------- | ------------------------------------------ |
| **Summary Layer** | JSON-снимки                       | Снапшоты перед выгрузкой модели            |
| **Fact Store**    | SQLite (`data/context_bridge.db`) | Хранение фактов, LRU-очистка (макс. 50)    |
| **Embedding DB**  | ChromaDB                          | Семантический поиск по историческим фактам |

Обе модели используют Qwen2 tokenizer → text-level трансфер без ретокенизации.

---

## Memory GC

**Anchored Iterative Context Compressor v2:**

- Инкрементальная компрессия: новые сообщения мержатся в summary
- Порог: 2 400 токенов → компрессия → таргет 800 токенов
- После 3-х компрессий → агрессивный режим (150 слов)
- Anchored preservation: критические факты не теряются
- Фоновый GC каждые 24ч → архивация в `Cold_Memory.md`
- Session auto-reset: 15 сообщений → полная очистка контекста

---

## Telegram Commands

| Команда            | Описание                                                                                                |
| ------------------ | ------------------------------------------------------------------------------------------------------- |
| `/start`           | Главное меню с inline-кнопками (Статус, Модели, Тест, Deep Research, История задач, Производительность) |
| `/help`            | Все команды, описание голоса и документов                                                               |
| `/status`          | Статус vLLM, GPU, бригад                                                                                |
| `/models`          | Активные модели и все 20 ролей                                                                          |
| `/test`            | Быстрый VRAM-тест                                                                                       |
| `/test_all_models` | Пинг всех 20 ролей с замером latency                                                                    |
| `/research`        | Deep Research через DeepSeek-R1                                                                         |
| `/tailscale`       | Статус Tailscale VPN mesh                                                                               |
| `/history`         | Последние 10 задач: бригада, цепочка, время                                                             |
| `/perf`            | Метрики производительности: avg/peak tok/s по ролям                                                     |

**Inline-кнопки** `/start`: ⚙️ Статус, 🤖 Модели, 🧪 Тест, 🔬 Deep Research, 📋 История задач, 📊 Производительность.

Голосовое → STT → pipeline. Документ → extraction → pipeline. Фото → vision/fallback.

---

## Brigade REST API (порт 8765)

| Метод  | Endpoint                  | Описание                  |
| ------ | ------------------------- | ------------------------- |
| `POST` | `/brigade/execute`        | Выполнить цепочку бригады |
| `POST` | `/brigade/execute/stream` | SSE-стрим шагов           |
| `GET`  | `/brigade/brigades`       | Список бригад и ролей     |
| `GET`  | `/brigade/status`         | Здоровье системы + vLLM   |

---

## Tailscale Integration

`src/tailscale_monitor.py`:

- `/tailscale` → статус подключения, пиры, IP
- Автоопределение CLI (Windows/Linux)
- Routing vLLM через Tailscale для удалённого доступа
- Health-check каждые 60 сек

---

## Стек технологий

| Слой           | Технологии                                                                      |
| -------------- | ------------------------------------------------------------------------------- |
| **Runtime**    | Python 3.14 (Windows bot), Python 3.12 (WSL2 vLLM)                              |
| **LLM**        | vLLM 0.17.1 — Qwen2.5-Coder-14B-Instruct-AWQ + DeepSeek-R1-14B-AWQ              |
| **Telegram**   | aiogram 3.26 (polling, стриминг, ForceReply, inline buttons)                    |
| **Discord**    | discord.py 2.x (mention/prefix trigger, typing indicator)                       |
| **TTS**        | OpenAI TTS-1, ElevenLabs v2, edge-tts (fallback chain)                          |
| **Scheduler**  | APScheduler 3.x (cron + interval triggers)                                      |
| **API**        | FastAPI (brigade REST/SSE), Prometheus (metrics)                                |
| **Storage**    | SQLite (facts), ChromaDB (embeddings), JSON (config)                            |
| **Safety**     | PromptInjectionDefender (5-layer), HallucinationDetector, semgrep, bandit, ruff |
| **Infra**      | WSL2 Ubuntu 24.04, CUDA 13.2, FLASH_ATTN v2, AWQ Marlin                         |
| **VPN**        | Tailscale (mesh networking, remote vLLM routing)                                |
| **Monitoring** | structlog (JSON), Prometheus, Watchdog (config hot-reload)                      |
| **Resilience** | AutoRollback (HMAC git), self-healing retry, session auto-reset                 |
| **GPU**        | NVIDIA RTX 5060 Ti 16 GB (Blackwell GB206, sm_120)                              |

---

## Установка и запуск

### Требования

- Windows 10/11 с WSL2 (Ubuntu 24.04)
- NVIDIA GPU 16 GB+ VRAM (RTX 5060 Ti / RTX 4070 Ti и выше)
- Python 3.12+ (WSL для vLLM), Python 3.14+ (Windows для бота)
- NVIDIA Driver 550+ с CUDA 12.x / 13.x

### 1. vLLM (WSL2)

```bash
python3 -m venv /mnt/d/vllm_env
source /mnt/d/vllm_env/bin/activate
pip install vllm torch --index-url https://download.pytorch.org/whl/cu128

# Запуск (оптимизированный скрипт)
bash scripts/start_vllm.sh
```

### 2. Бот (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python -m src.main
```

### 3. Конфигурация

`config/openclaw_config.json` — единый конфиг:

| Секция                      | Содержимое                                            |
| --------------------------- | ----------------------------------------------------- |
| `system.telegram`           | bot_token, admin_chat_id                              |
| `system.hardware`           | GPU, VRAM, inference engine                           |
| `system.vllm_*`             | URL, порт, gpu_utilization, max_model_len, extra_args |
| `system.model_router`       | Маппинг задач → модели                                |
| `system.context_bridge`     | SQLite/ChromaDB параметры                             |
| `system.tailscale`          | VPN настройки                                         |
| `system.session_management` | heartbeat, auto_reset_context                         |
| `brigades`                  | Бригады с ролями, system prompts, температурами       |
| `routing`                   | Правила маршрутизации задач                           |
| `code_validator`            | semgrep/bandit/ruff настройки                         |

---

## Структура проекта

```
src/
├── main.py                  # OpenClawGateway — точка входа, Telegram polling
├── gateway_commands.py      # Обработчики команд, голоса, документов
├── pipeline_executor.py     # Chain-of-Agents конвейер (execute, execute_stream)
├── intent_classifier.py     # LLM + keyword + LRU-кеш маршрутизация
├── safety_guardrails.py     # PromptInjectionDefender + HallucinationDetector
├── auto_rollback.py         # HMAC-signed git checkpoints + rollback
├── code_validator.py        # semgrep + bandit + ruff pipeline
├── vllm_manager.py          # Управление vLLM сервером (auto-start, health)
├── vllm_inference.py        # Low-level vLLM API wrapper
├── context_bridge.py        # 3-слойный контекстный мост
├── memory_gc.py             # Anchored Iterative Context Compressor v2
├── memory_enhanced.py       # RAG memory (Hot/Domain/Cold)
├── deep_research.py         # Deep Research через DeepSeek-R1
├── research_enhanced.py     # Enhanced research pipeline
├── brigade_api.py           # FastAPI REST/SSE для бригад
├── archivist_telegram.py    # Telegram-логирование (Archivist)
├── tailscale_monitor.py     # Tailscale VPN мониторинг
├── security_auditor.py      # Security audit module
├── scheduler.py             # APScheduler cron-задачи (GC, health-check, custom)
├── discord_handler.py       # Discord-канал (discord.py 2.x)
├── tts_engine.py            # TTS: OpenAI / ElevenLabs / edge-tts fallback
├── supermemory.py           # SuperMemory — 3-tier persistent memory
├── rag_engine.py            # RAG Engine — ChromaDB document retrieval
├── llm_gateway.py           # Unified LLM Gateway (route_llm)
├── mcp_client.py            # MCP (Model Context Protocol) client
├── telemetry.py             # Telemetry collection
├── task_queue.py            # Task queue for async processing
├── ai/
│   ├── inference/           # SmartModelRouter, Metrics, Budget, BatchScheduler
│   └── agents/              # ReActReasoner, ReflexionAgent
└── ...

config/
├── openclaw_config.json     # Главный конфиг (бригады, модели, vLLM, safety)
├── openclaw_agents.json     # Описания агентов
├── brigade_policy.json      # Политики бригад
└── openclaw.json            # Gateway config

scripts/
├── start_vllm.sh            # Запуск vLLM (полная конфигурация)
├── start_vllm_simple.sh     # Запуск vLLM (без speculative)
├── benchmark_tokens.py      # Бенчмарк генерации
├── benchmark_vllm.py        # vLLM-специфичный бенчмарк
└── ...

tests/                       # pytest (206 тестов)
data/
├── eval/                    # Evaluation datasets
├── training/                # Training data for LoRA
└── context_bridge.db        # SQLite fact store
```

---

## LoRA-адаптеры (обучены 2026-03-20)

| Адаптер                 | База                       | Rank | ROUGE-1 | Размер |
| ----------------------- | -------------------------- | ---: | ------- | ------ |
| openclaw-7b-v1          | Qwen2.5-Coder-7B-bnb-4bit  |   64 | 0.780   | 617 MB |
| openclaw-14b-v1         | Qwen2.5-Coder-14B-bnb-4bit |   32 | 0.788   | 526 MB |
| openclaw-deepseek-r1-v1 | DeepSeek-R1-14B-bnb-4bit   |   32 | 0.797   | 526 MB |

201 sample, 15 epochs, cosine LR 2e-4. vLLM API: `POST /v1/load_lora_adapter` (hot-swap, KV cache preserved).

---

## Документация

- [BRAIN.md](BRAIN.md) — Архитектура inference и оптимизации
- [VISION.md](VISION.md) — Roadmap 2026
- [IDENTITY.md](IDENTITY.md) — Личность и директивы
- [SOUL.md](SOUL.md) — Философия проекта
- [SECURITY.md](SECURITY.md) — Модель безопасности
- [AGENTS.md](AGENTS.md) — Документация всех 20 ролей
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Решение проблем
- [CONTRIBUTING.md](CONTRIBUTING.md) — Гайд для контрибьюторов
- [CHANGELOG.md](CHANGELOG.md) — Журнал изменений

---

_OpenClaw Foundation · 2026 · Blackwell Edition_
