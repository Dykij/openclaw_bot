# Hot Memory - OpenClaw Core System

## Текущая Архитектура Управления
* Системный мозг работает на ЕДИНОЙ физической модели (GPU: NVIDIA RTX 5060 Ti — 16GB VRAM).
* Запрещена параллельная загрузка нескольких больших LLM (во избежание Model Thrashing). Переключение ролей осуществляется исключительно сменой System Prompts.
* Иерархия управления:
  1. Главный Оркестратор (**Аркадий**) - Планирование (90%) и маршрутизация.
  2. Бригадир Ядра (**Прораб OpenClaw / Системщик**) - Работает в `D:\openclaw_bot\openclaw_bot`.
  3. Бригадир Торговли (**Прораб Dmarket / Трейдер**) - Работает в `D:\openclaw_bot\Dmarket_bot`.

## Базовые Принципы (Конституция)
1. **Фреймворк STAR:** Оркестратор обязан использовать метод Situation-Task-Action-Result перед сложными задачами для повышения точности рассуждений.
2. **Context Compression:** Перед подачей больших логов (более 2-3KB) в контекст, они должны быть сжаты через jq/ripgrep.
3. **Deterministic Feedback:** Любой написанный код проходит автоматический линтер и type-check.
4. **Proof-based Status Updates:** Агентам строго запрещено говорить "сделано", "делаю" или "запущено" без реальных доказательств. Любой статус ОБЯЗАН содержать подтверждение: PID процесса, абсолютный путь к файлу, URL или лог/вывод из терминала. Нет доказательств = действие не выполнялось.
## Текущий Контекст
* Внедряется RAG/MCP архитектура памяти (`.memory-bank/`).
* Идет настройка изоляции задач Dmarket от задач OpenClaw.
* Внедрён локальный Deep Research через `memory_search` + `memory_get` (полностью офлайн).
* Документация оптимизирована для AI-поиска: YAML frontmatter, llms.txt, самодостаточные секции.
* Создана русскоязычная документация: `docs/ru/tools/deep-research-local.md`, `docs/ru/reference/documentation-readability.md`.
* Выполнен анализ Gemini Deep Research: `docs/ru/reference/gemini-deep-research-analysis.md`.
* Следующий приоритет: Deep Research Pipeline (Decomposer → Researcher (цикл) → Verifier → Synthesizer) в `src/pipeline_executor.py`.
