---
summary: "Полный анализ архитектуры Gemini Deep Research и план внедрения аналогичных возможностей в OpenClaw на локальной модели RTX 5060 Ti 16GB"
read_when:
  - Вы хотите понять как работает Deep Research от Google Gemini
  - Вы планируете внедрить аналогичный функционал на локальной модели
  - Вы проектируете агентный пайплайн для Deep Research
  - Вы оптимизируете OpenClaw бот для исследовательских задач
title: "Анализ Gemini Deep Research и план улучшений OpenClaw"
---

# Анализ Gemini Deep Research и план улучшений OpenClaw

Этот документ содержит полный технический анализ архитектуры Google Gemini Deep Research и конкретный список улучшений для реализации аналогичного функционала в OpenClaw боте на локальной модели (RTX 5060 Ti, 16GB VRAM).

---

## Часть 1: Как работает Gemini Deep Research

### 1.1 Общая архитектура

Gemini Deep Research — это **агентный исследовательский ассистент**, построенный на модели Gemini 3 Pro. В отличие от обычного чат-бота, Deep Research автономно планирует, ищет, читает, анализирует и синтезирует информацию в многоэтапном цикле.

**Ключевые компоненты:**

| Компонент | Описание | Аналог в OpenClaw |
| --------- | -------- | ----------------- |
| **Gemini 3 Pro** | Основная LLM для рассуждений и синтеза | Ollama + qwen2.5-coder:14b |
| **Google Search Grounding** | Доступ к индексу Google для поиска | `memory_search` (локальный) |
| **Interactions API** | Асинхронный API для долгих задач | `PipelineExecutor.execute()` |
| **Sparse MoE** | Mixture-of-Experts для масштабирования | Единая модель (VRAM лимит) |
| **1M контекстное окно** | Обработка огромных документов | 32K–128K (зависит от модели) |

### 1.2 Агентный цикл (Agentic Loop)

Gemini Deep Research использует **итеративный цикл deliberation → search → read → reason → repeat**:

```
┌─────────────────────────────────────────────────────────┐
│                  GEMINI DEEP RESEARCH                   │
│                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐           │
│  │ PLANNING │──▶│ SOURCING │──▶│ READING  │           │
│  └──────────┘   └──────────┘   └──────────┘           │
│       │                              │                  │
│       │         ┌──────────┐   ┌─────▼────┐           │
│       │         │  GAPS?   │◀──│ REASONING│           │
│       │         └────┬─────┘   └──────────┘           │
│       │              │ Да                               │
│       │         ┌────▼─────┐                           │
│       │         │ ITERATE  │──── (новый цикл)          │
│       │         └──────────┘                           │
│       │              │ Нет                              │
│       │         ┌────▼─────┐   ┌──────────┐           │
│       └────────▶│ SYNTHESIS│──▶│  REPORT  │           │
│                 └──────────┘   └──────────┘           │
└─────────────────────────────────────────────────────────┘
```

### 1.3 Шесть фаз Deep Research

#### Фаза 1: Планирование (Planning)

- Пользователь задаёт вопрос
- LLM декомпозирует его на **подзадачи** (sub-questions)
- Формируется **план исследования** (research plan)
- План предоставляется пользователю для проверки и корректировки
- **Ключевая особенность:** план прозрачен и редактируем

#### Фаза 2: Поиск источников (Sourcing)

- Агент автономно формулирует **таргетированные поисковые запросы**
- Использует Google Search для поиска по каждому подвопросу
- Может обработать **100+ источников** за одну сессию
- Оценивает релевантность и качество каждого источника

#### Фаза 3: Чтение и извлечение (Reading & Extraction)

- Полностью читает найденные страницы
- Извлекает ключевые факты, данные, цитаты
- Обрабатывает таблицы, PDF, код, изображения (мультимодальность)
- Сохраняет метаданные источника для цитирования

#### Фаза 4: Рассуждение и проверка (Reasoning & Verification)

- Chain-of-thought анализ собранных данных
- Перекрёстная проверка фактов из разных источников
- Выявление противоречий и информационных пробелов
- **Критическая фаза:** определяет нужно ли дополнительное исследование

#### Фаза 5: Итеративный дополнительный поиск (Iterative Re-search)

- Если обнаружены пробелы → новый цикл поиска с уточнёнными запросами
- Типично: **5–10+ итераций** поиска на сложных темах
- Продолжается до достижения полноты или лимита времени/бюджета
- Общее время: от 5 минут до нескольких часов

#### Фаза 6: Синтез и отчёт (Synthesis & Report)

- Формирование структурированного отчёта с разделами
- Inline-цитирование каждого утверждения
- Таблицы, визуализации, сводки
- Экспорт в Google Docs/Canvas
- Опциональная аудио-сводка

### 1.4 Техническая реализация через API

```
// Gemini Deep Research использует Interactions API:
// 1. Создание исследования (асинхронно, background=true)
// 2. Поллинг статуса до завершения
// 3. Получение отчёта с цитатами

POST /interactions
{
  "agent": "deep-research-pro-preview-12-2025",
  "query": "...",
  "tools": ["google_search", "url_context", "file_search"],
  "background": true
}

// → Возвращает interaction_id
// → Поллинг GET /interactions/{id}/status
// → Результат: структурированный отчёт
```

### 1.5 Уникальные технические возможности

| Возможность | Описание | Сложность реализации локально |
| ----------- | -------- | ----------------------------- |
| **1M контекст** | Обработка целых книг за раз | ❌ Невозможно (14B модели: 32K–128K) |
| **Sparse MoE** | Эффективное масштабирование | ❌ Требует инфраструктуру Google |
| **Google Search** | Индекс всего интернета | ⚠️ Заменяется `memory_search` (локальный) |
| **Мультимодальность** | Обработка изображений и таблиц | ⚠️ Частично (LLaVA для изображений) |
| **Прозрачный план** | Пользователь видит/редактирует план | ✅ Реализуемо через `PipelineExecutor` |
| **Итеративный поиск** | 5–10+ циклов до полноты | ✅ Реализуемо через циклы в пайплайне |
| **Chain-of-thought** | Показ рассуждений | ✅ Уже есть (DeepSeek-R1, `<think>` теги) |
| **Цитирование** | Inline-ссылки на источники | ✅ Реализуемо через memory_get пути |

---

## Часть 2: Текущее состояние OpenClaw бота

### 2.1 Что уже реализовано

**PipelineExecutor** (`src/pipeline_executor.py`):

- Последовательное выполнение цепочки ролей: Planner → Executor → Archivist
- Передача сжатого контекста между шагами
- Поддержка бригад (Dmarket, OpenClaw)
- VRAM-менеджмент через `keep_alive=0`
- Автоматический handoff от Planner к Executor
- Интеграция с MCP-клиентом

**Memory MCP** (`src/memory_mcp.py`):

- Гибридный поиск: ripgrep (текстовый) + vectorDB (семантический)
- Эмбеддинги через vLLM (nvidia/nv-embedqa-e5-v5)
- Re-ranking через LLM
- Тегирование уверенности: `[RAG_CONFIDENCE: HIGH/MEDIUM/LOW/NONE]`
- Поддержка тиров: Hot/Cold/Domain

**OpenClaw TypeScript Agent Loop** (`docs/concepts/agent-loop.md`):

- `memory_search` — семантический поиск по workspace
- `memory_get` — чтение конкретных файлов
- Гибридный поиск: векторный + FTS5
- SQLite + sqlite-vec для хранения
- Локальные эмбеддинги (provider: "local")

### 2.2 Текущие ограничения (что не хватает для Deep Research)

| Компонент Gemini DR | Статус в OpenClaw | Что нужно |
| -------------------- | ----------------- | --------- |
| Планирование с декомпозицией | ⚠️ Частично (Planner роль) | Автоматическая декомпозиция на подвопросы |
| Итеративный поиск с gap-detection | ❌ Отсутствует | Цикл поиск→анализ→дополнительный поиск |
| Прозрачный план для пользователя | ❌ Отсутствует | UI/сообщение с планом исследования |
| Cross-reference проверка | ❌ Отсутствует | Проверка фактов из разных источников |
| Структурированный отчёт | ⚠️ Частично (Archivist) | Шаблон отчёта с секциями и цитатами |
| Контроль глубины (thinking_level) | ❌ Отсутствует | Параметр глубины исследования |
| Асинхронное выполнение | ⚠️ Частично | Фоновые задачи с отслеживанием статуса |
| Бюджет итераций | ❌ Отсутствует | Лимиты на количество циклов и время |

---

## Часть 3: Список улучшений для OpenClaw

### 🔴 Критические улучшения (реализовать первыми)

#### 3.1 Deep Research Pipeline — новая цепочка в PipelineExecutor

**Файл:** `src/pipeline_executor.py`

**Суть:** Добавить новую цепочку `"DeepResearch"` с итеративным циклом:

```python
self.default_chains = {
    "Dmarket": ["Planner", "Executor_API", "Archivist"],
    "OpenClaw": ["Planner", "Executor_Tools", "Archivist"],
    # НОВОЕ: Deep Research цепочка
    "DeepResearch": ["Decomposer", "Researcher", "Verifier", "Synthesizer"],
}
```

**Роли:**

| Роль | Модель | Задача |
| ---- | ------ | ------ |
| **Decomposer** | qwen2.5-coder:14b | Разбить вопрос на 3–7 подвопросов |
| **Researcher** | qwen2.5-coder:14b | Итеративный `memory_search` + `memory_get` по каждому подвопросу |
| **Verifier** | deepseek-r1:14b | Перекрёстная проверка и выявление пробелов |
| **Synthesizer** | qwen2.5-coder:14b | Синтез отчёта с цитатами |

**Ключевое отличие от текущего пайплайна:** Researcher работает в **цикле** (loop) — после каждого раунда поиска Verifier проверяет полноту. Если есть пробелы, Researcher запускается снова с уточнёнными запросами.

#### 3.2 Автоматическая декомпозиция запроса (Decomposer)

**Файл:** `src/pipeline_executor.py` — новая роль

**System Prompt для Decomposer:**

```
Ты — исследовательский декомпозитор. Получив сложный вопрос, 
разбей его на 3-7 конкретных подвопросов для последовательного 
исследования. 

ФОРМАТ ОТВЕТА (строго JSON):
{
  "research_plan": {
    "main_question": "Оригинальный вопрос",
    "sub_questions": [
      {"id": 1, "question": "Подвопрос 1", "search_terms": ["термин1", "термин2"]},
      {"id": 2, "question": "Подвопрос 2", "search_terms": ["термин3", "термин4"]}
    ],
    "expected_sections": ["Раздел 1", "Раздел 2"]
  }
}
```

#### 3.3 Итеративный цикл поиска с Gap Detection

**Файл:** `src/pipeline_executor.py` — метод `_deep_research_loop()`

```python
async def _deep_research_loop(self, plan: dict, max_iterations: int = 5) -> dict:
    """
    Итеративный цикл поиска аналогичный Gemini Deep Research.
    
    Цикл: search → read → verify → re-search (если есть gaps)
    Продолжается до max_iterations или полноты ответа.
    """
    all_findings = []
    gaps = plan["sub_questions"]  # Начинаем со всех подвопросов
    
    for iteration in range(max_iterations):
        if not gaps:
            break  # Все подвопросы покрыты
            
        # 1. SEARCH: memory_search по каждому gap
        search_results = await self._search_all_gaps(gaps)
        
        # 2. READ: memory_get для полного контента
        full_content = await self._read_relevant_files(search_results)
        
        # 3. VERIFY: LLM проверяет полноту
        verification = await self._verify_coverage(
            original_plan=plan,
            findings=all_findings + full_content,
            current_gaps=gaps
        )
        
        all_findings.extend(full_content)
        gaps = verification.get("remaining_gaps", [])
        
        logger.info(f"Iteration {iteration+1}: found={len(full_content)}, "
                     f"remaining_gaps={len(gaps)}")
    
    return {"findings": all_findings, "iterations": iteration + 1}
```

### 🟡 Важные улучшения (вторая очередь)

#### 3.4 Прозрачный план исследования для пользователя

**Суть:** Перед началом Deep Research показать пользователю план и дать возможность скорректировать.

**Реализация в Telegram-боте:**

```python
# После декомпозиции — отправить план пользователю
plan_message = f"""
🔍 **План исследования:**

Основной вопрос: {plan['main_question']}

📋 Подвопросы:
{format_sub_questions(plan['sub_questions'])}

📊 Ожидаемые разделы отчёта:
{format_sections(plan['expected_sections'])}

⏱ Оценка: ~{estimate_time(plan)} мин
🔄 Макс. итераций: {max_iterations}

Начать исследование? (Или скорректируйте план)
"""
```

#### 3.5 Структурированный шаблон отчёта

**System Prompt для Synthesizer:**

```
Ты — научный редактор. На основе собранных данных сформируй 
структурированный отчёт.

ОБЯЗАТЕЛЬНЫЙ ФОРМАТ:
# [Тема исследования]

## Резюме
[2-3 предложения с ключевыми выводами]

## Основные результаты
### [Раздел по каждому подвопросу]
[Содержание с inline-цитатами: (файл:строка)]

## Сравнительная таблица
[Если применимо — таблица с данными]

## Пробелы и ограничения
[Что не удалось найти или требует дополнительного исследования]

## Источники
[Список всех использованных файлов с путями]
```

#### 3.6 Контроль глубины исследования (Research Depth)

**Аналог `thinking_level` в Gemini:**

```python
RESEARCH_DEPTH = {
    "quick": {
        "max_iterations": 2,
        "max_sub_questions": 3,
        "model": "qwen2.5-coder:7b",  # Быстрая модель
        "timeout_minutes": 2,
    },
    "standard": {
        "max_iterations": 5,
        "max_sub_questions": 5,
        "model": "qwen2.5-coder:14b",
        "timeout_minutes": 10,
    },
    "deep": {
        "max_iterations": 10,
        "max_sub_questions": 7,
        "model": "qwen2.5-coder:14b",  # + deepseek-r1:14b для верификации
        "timeout_minutes": 30,
    },
}
```

#### 3.7 Интеграция с существующим Memory MCP

**Файл:** `src/memory_mcp.py` — добавить tool `deep_research`

```python
@mcp.tool()
async def deep_research(
    query: str, 
    depth: str = "standard",
    max_iterations: int = 5
) -> str:
    """
    Выполнить Deep Research по запросу используя итеративный 
    поиск по .memory-bank/.
    
    Args:
        query: Исследовательский вопрос
        depth: "quick" | "standard" | "deep"
        max_iterations: Максимум итераций поиска
    
    Returns:
        Структурированный отчёт с цитатами
    """
    # 1. Декомпозиция
    plan = await decompose_query(query)
    
    # 2. Итеративный поиск
    findings = await iterative_search(plan, max_iterations)
    
    # 3. Верификация
    verified = await verify_findings(findings)
    
    # 4. Синтез отчёта
    report = await synthesize_report(verified, plan)
    
    return report
```

### 🟢 Улучшения для бэклога (третья очередь)

#### 3.8 Автоматическая индексация при обновлении документации

**Суть:** Когда файлы в `.memory-bank/` или `docs/` обновляются — автоматически переиндексировать для `memory_search`.

```python
# Через watchdog или при каждом запуске Deep Research:
async def ensure_index_fresh():
    """Проверить актуальность индекса и переиндексировать при необходимости."""
    manifest_path = os.path.join(MEMORY_BANK_DIR, "docs", "manifest.json")
    if not os.path.exists(manifest_path):
        await reindex_all()
        return
    
    manifest = json.load(open(manifest_path))
    for file_path, meta in manifest.items():
        if os.path.getmtime(file_path) > meta.get("indexed_at", 0):
            await reindex_file(file_path)
```

#### 3.9 Кэширование результатов исследования

**Суть:** Сохранять результаты Deep Research для повторного использования.

```python
# Сохранение результата в .memory-bank/research/
research_output_path = os.path.join(
    MEMORY_BANK_DIR, "research",
    f"dr_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slugify(query)}.md"
)
```

#### 3.10 Прогресс-бар и стриминг статуса

**Суть:** Во время Deep Research показывать пользователю прогресс:

```
🔍 Deep Research: "Архитектура OpenClaw"
━━━━━━━━━━▓░░░░░░░░░░ 45%

📋 Итерация 2/5
✅ Подвопрос 1: Компоненты системы — найдено 3 источника
✅ Подвопрос 2: Маршрутизация — найдено 2 источника
🔄 Подвопрос 3: VRAM-менеджмент — поиск...
⏳ Подвопрос 4: Конфигурация — ожидание
⏳ Подвопрос 5: Безопасность — ожидание
```

#### 3.11 Мультимодальная поддержка (Images)

**Суть:** Добавить обработку изображений из документации через LLaVA модели.

Это пункт из ROADMAP (пункт 8), но для Deep Research можно:

- При нахождении `.png`/`.jpg` файлов в memory — анализировать их через vision-модель
- Включать описания изображений в отчёт

---

## Часть 4: Приоритезированный план внедрения

### Фаза 1: MVP Deep Research (1–2 недели)

| # | Задача | Файл | Сложность |
| - | ------ | ---- | --------- |
| 1 | Роль Decomposer в PipelineExecutor | `src/pipeline_executor.py` | Средняя |
| 2 | Итеративный цикл `_deep_research_loop()` | `src/pipeline_executor.py` | Высокая |
| 3 | Роль Verifier (gap detection) | `src/pipeline_executor.py` | Средняя |
| 4 | Роль Synthesizer (шаблон отчёта) | `src/pipeline_executor.py` | Низкая |
| 5 | Интеграция с `search_memory` из MCP | `src/pipeline_executor.py` | Средняя |
| 6 | Команда `/research` в Telegram | `src/main.py` | Низкая |

### Фаза 2: UX и контроль (2–3 недели)

| # | Задача | Файл | Сложность |
| - | ------ | ---- | --------- |
| 7 | Прозрачный план для пользователя | `src/main.py` | Низкая |
| 8 | Research Depth (quick/standard/deep) | `config/openclaw_config.json` | Низкая |
| 9 | Прогресс-бар и стриминг статуса | `src/main.py` | Средняя |
| 10 | Кэширование результатов | `src/memory_mcp.py` | Низкая |

### Фаза 3: Оптимизация (3–4 недели)

| # | Задача | Файл | Сложность |
| - | ------ | ---- | --------- |
| 11 | Авто-индексация при обновлении файлов | `src/memory_mcp.py` | Средняя |
| 12 | MCP tool `deep_research` | `src/memory_mcp.py` | Средняя |
| 13 | Мультимодальная поддержка | `src/pipeline_executor.py` | Высокая |

---

## Часть 5: Ограничения и компромиссы

### Что НЕ получится реализовать 1-в-1

| Возможность Gemini | Причина ограничения | Компромисс |
| ------------------ | -------------------- | ---------- |
| **1M токенов контекста** | RTX 5060 Ti: модели до 128K max | Чанкинг + итеративная обработка |
| **Живой поиск в интернете** | Локальная модель, без API | `memory_search` по проиндексированным docs |
| **Sparse MoE** | Требует облачной инфраструктуры | Одна модель, переключение ролей через промпты |
| **Обработка 100+ источников** | VRAM и контекст ограничены | Top-10 наиболее релевантных за итерацию |
| **Параллельный поиск** | Одна GPU, последовательная обработка | Последовательные запросы с `keep_alive=0` |

### Что получится реализовать хорошо

| Возможность | Почему реализуемо |
| ----------- | ----------------- |
| **Декомпозиция запроса** | Простой LLM-вызов, не требует большого контекста |
| **Итеративный поиск** | `memory_search` работает быстро локально |
| **Gap detection** | LLM хорошо определяет пробелы в информации |
| **Chain-of-thought** | DeepSeek-R1 нативно поддерживает `<think>` |
| **Цитирование файлов** | `memory_get` возвращает путь + строки |
| **Структурированный отчёт** | Шаблонный промпт для Synthesizer |
| **Прозрачный план** | JSON → сообщение пользователю |
| **Контроль глубины** | Параметры: max_iterations, max_sub_questions |

---

## Часть 6: Пример работы будущего Deep Research

```
Пользователь: /research Как работает маршрутизация сообщений в OpenClaw?

🤖 Аркадий (Decomposer):
📋 План исследования:
  1. Какие каналы поддерживает OpenClaw? [channels, routing]
  2. Как устроена очередь сообщений? [queue, concurrency]
  3. Как работают channel adapters? [adapters, webhook]
  4. Как настраивается маршрутизация? [config, routing rules]
  ⏱ Оценка: ~5 мин | 🔄 До 5 итераций

Начать? [Да / Скорректировать]

Пользователь: Да

🔍 Итерация 1/5:
  ✅ Подвопрос 1: найдено 4 файла (docs/channels/*.md)
  ✅ Подвопрос 2: найдено 2 файла (docs/concepts/queue.md)
  ✅ Подвопрос 3: найдено 3 файла (src/channels/*.ts)
  ⚠️ Подвопрос 4: 1 файл, недостаточно данных

🔍 Итерация 2/5 (уточнённый поиск):
  ✅ Подвопрос 4: найдено 2 дополнительных файла

✅ Исследование завершено (2 итерации)

📊 ОТЧЁТ: Маршрутизация сообщений в OpenClaw

## Резюме
OpenClaw поддерживает 6+ каналов (WhatsApp, Telegram, Discord, Slack, 
Signal, iMessage) с единой точкой входа через Gateway...

## 1. Поддерживаемые каналы
[Данные из docs/channels/*.md, строки 10-45]
...

## Источники
- docs/channels/whatsapp.md:10-45
- docs/concepts/queue.md:1-80
- src/channels/telegram.ts:15-120
- docs/configuration.md:200-250
```

---

## Связанные документы

- [Deep Research на локальной модели](/ru/tools/deep-research-local) — Текущая настройка локального Deep Research
- [Deep Research (внешние провайдеры)](/tools/deep-research) — Deep Research через Perplexity, Gemini, Grok
- [Читаемость документации](/ru/reference/documentation-readability) — Оптимизация документов для AI-поиска
- [Agent Loop](/concepts/agent-loop) — Как работает агентный цикл OpenClaw
- [Memory](/concepts/memory) — Система памяти OpenClaw
- [ROADMAP Аркадия](/.memory-bank/ROADMAP_ARKADIY.md) — Полный план развития
