# 🧠 ROADMAP ARKADIY — Главный Оркестратор OpenClaw
> Дата: 2026-03-17 | GPU: NVIDIA RTX 5060 Ti (16GB VRAM) | Версия: v2.2

---

## 🔴 Приоритет: КРИТИЧЕСКИЙ

### 1. Deep Research Pipeline (по аналогии с Gemini Deep Research)
**Файл:** `src/pipeline_executor.py`  
**Проблема:** Нет итеративного исследовательского цикла. Текущий пайплайн Planner→Executor→Archivist выполняет один проход без gap detection и re-search.  
**Решение:** Новая цепочка `DeepResearch`: Decomposer → Researcher (цикл) → Verifier → Synthesizer. Researcher работает в цикле с итеративным поиском через `memory_search` и верификацией полноты.  
**Анализ:** Полный анализ в `docs/ru/reference/gemini-deep-research-analysis.md`  
**Метрика:** Полнота ответа >80% (оценка Verifier), цитирование 100% утверждений.  
**Статус:** 🟡 Запланировано

### 2. Anchored Iterative Context Compressor
**Файл:** `memory_gc.py`  
**Проблема:** Наивная суммаризация — один вызов LLM на всю историю. При длинных сессиях теряются критические факты.  
**Решение:** Инкрементальное слияние: persistent summary + delta (новые сообщения) → merged summary.  
**Метрика:** Снижение token count на 40-60% при сохранении >95% критических фактов.  
**Статус:** 🟡 Запланировано

### 3. LLM-based Intent Router  
**Файл:** `main.py` (строки 236-240)  
**Проблема:** Keyword matching (`"buy", "sell", "dmarket"...`) — ломается на синонимах, жаргоне, контексте.  
**Решение:** Intent classifier через qwen2.5:1.5b (0.9GB VRAM) — JSON-ответ с brigade + confidence.  
**Fallback:** Keyword matching при недоступности Ollama.  
**Статус:** 🟡 Запланировано

### 4. Pipeline Executor (Chain-of-Agents)
**Файл:** `pipeline_executor.py`  
**Проблема:** `handle_prompt()` вызывает только Planner. SOUL.md описывает цепочку Planner→Executor→Auditor, но она не реализована.  
**Решение:** `PipelineExecutor` — последовательный вызов ролей из конфига с передачей compressed context между шагами.  
**Статус:** ✅ Реализовано (базовый вариант)

---

## 🟡 Приоритет: ВАЖНЫЙ

### 5. Прозрачный план исследования для пользователя
**Проблема:** Пользователь не видит что именно исследует агент и не может скорректировать.  
**Решение:** Перед запуском Deep Research показать план (подвопросы, ожидаемые разделы), дать возможность отредактировать. Аналог Gemini DR Planning phase.  
**Статус:** 🟡 Запланировано

### 6. Контроль глубины исследования (Research Depth)
**Проблема:** Нет способа выбрать баланс скорость/глубина для исследовательских задач.  
**Решение:** Три уровня: quick (2 итерации, 3 подвопроса), standard (5/5), deep (10/7). Аналог `thinking_level` в Gemini.  
**Статус:** 🟡 Запланировано

### 7. Structured Logging (JSON)
**Проблема:** Текстовые логи не поддаются машинному анализу.  
**Решение:** `structlog` с JSON-форматированием, ротация через `logging.handlers.RotatingFileHandler`.

### 8. Health Monitoring Endpoint
**Проблема:** Нет способа проверить состояние системы программно.  
**Решение:** `/health` endpoint: VRAM usage, queue depth, uptime, model status.

### 9. Hot-Reload Config
**Проблема:** Изменение `openclaw_config.json` требует перезапуска.  
**Решение:** `watchdog` FileSystemEventHandler для автоматической перезагрузки конфига.

---

## 🟢 Приоритет: БЭКЛОГ

### 10. Auto-scaling Context Window
Динамическая подстройка `num_ctx` в зависимости от сложности задачи.

### 11. Multi-modal Input (Images)
Поддержка Telegram-фото через vision-модели (LLaVA). Для Deep Research: анализ скриншотов и диаграмм.

### 12. Prometheus Metrics Export
Экспорт метрик для Grafana-дашборда.

### 13. MCP tool `deep_research`
Регистрация Deep Research как MCP tool для вызова из любого агента.

### 14. Кэширование результатов Deep Research
Сохранение отчётов в `.memory-bank/research/` для повторного использования.

### 15. Авто-индексация при обновлении файлов
`watchdog` для `.memory-bank/` и `docs/` — автоматическая переиндексация при изменении файлов.
