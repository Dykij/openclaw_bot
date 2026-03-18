# 🧠 ROADMAP ARKADIY — Главный Оркестратор OpenClaw
> Дата: 2026-03-18 | GPU: NVIDIA RTX 5060 Ti (16GB VRAM) | Версия: v2.2

---

## 🔴 Приоритет: КРИТИЧЕСКИЙ

### 1. Anchored Iterative Context Compressor
**Файл:** `memory_gc.py`  
**Проблема:** Наивная суммаризация — один вызов LLM на всю историю. При длинных сессиях теряются критические факты.  
**Решение:** Инкрементальное слияние: persistent summary + delta (новые сообщения) → merged summary.  
**Метрика:** Снижение token count на 40-60% при сохранении >95% критических фактов.  
**Статус:** 🟡 Запланировано

### 2. LLM-based Intent Router  
**Файл:** `main.py` (строки 236-240)  
**Проблема:** Keyword matching (`"buy", "sell", "dmarket"...`) — ломается на синонимах, жаргоне, контексте.  
**Решение:** Intent classifier через qwen2.5:1.5b (0.9GB VRAM) — JSON-ответ с brigade + confidence.  
**Fallback:** Keyword matching при недоступности Ollama.  
**Статус:** 🟡 Запланировано

### 3. Pipeline Executor (Chain-of-Agents)
**Файл:** `pipeline_executor.py` (НОВЫЙ)  
**Проблема:** `handle_prompt()` вызывает только Planner. SOUL.md описывает цепочку Planner→Executor→Auditor, но она не реализована.  
**Решение:** `PipelineExecutor` — последовательный вызов ролей из конфига с передачей compressed context между шагами.  
**Статус:** 🟡 Запланировано

---

## 🟡 Приоритет: ВАЖНЫЙ

### 4. Structured Logging (JSON)
**Проблема:** Текстовые логи не поддаются машинному анализу.  
**Решение:** `structlog` с JSON-форматированием, ротация через `logging.handlers.RotatingFileHandler`.

### 5. Health Monitoring Endpoint
**Проблема:** Нет способа проверить состояние системы программно.  
**Решение:** `/health` endpoint: VRAM usage, queue depth, uptime, model status.

### 6. Hot-Reload Config
**Проблема:** Изменение `openclaw_config.json` требует перезапуска.  
**Решение:** `watchdog` FileSystemEventHandler для автоматической перезагрузки конфига.

---

## 🟡 Приоритет: ВАЖНЫЙ (NEW — AlphaXiv Research)

### 7. Structured Interaction Logging (JSONL)
**Файл:** `src/interaction_logger.py` (НОВЫЙ)
**Проблема:** Взаимодействия бригад не сохраняются в формате, пригодном для обучения.
**Решение:** JSONL-логи пар (action, next_state, user_correction) для всех MCP tool calls.
**Источник:** OpenClaw-RL (arXiv:2603.10165) — unified interaction signals.
**VRAM:** 0 ГБ | **Статус:** 🟡 Запланировано

### 8. GRPO Training Pipeline (LoRA + Unsloth)
**Файл:** `src/grpo_trainer.py` (НОВЫЙ)
**Проблема:** Модели используются as-is, без адаптации к нашим задачам.
**Решение:** GRPO + LoRA 4-bit через Unsloth для дообучения Qwen-Coder-7B на корпусе tool calls.
**Источник:** arXiv:2503.16219 (GRPO for Small LLMs), Unsloth toolkit.
**VRAM:** 8–14 ГБ | **Статус:** 🟡 Запланировано

### 9. Reward Verifier (RLVR)
**Файл:** `src/reward_verifier.py` (НОВЫЙ)
**Проблема:** Нет автоматической метрики качества ответов агентов.
**Решение:** Верифицируемые rewards: JSON-валидность, HTTP status, SQL-результаты, lint pass.
**Источник:** DeepSeek-R1 (arXiv:2501.12948) — RLVR concept.
**VRAM:** 0 ГБ | **Статус:** 🟡 Запланировано

> 📚 Полный анализ: `docs/ru/reference/alphaxiv-model-training-analysis.md`

---

## 🟢 Приоритет: БЭКЛОГ

### 10. Auto-scaling Context Window
Динамическая подстройка `num_ctx` в зависимости от сложности задачи.

### 11. Multi-modal Input (Images)
Поддержка Telegram-фото через vision-модели (LLaVA).

### 12. Prometheus Metrics Export
Экспорт метрик для Grafana-дашборда.

### 13. PRM Judge (Process Reward Model)
Маленькая модель-судья (Qwen-1.5B) для real-time оценки качества ответов.
**Источник:** OpenClaw-RL (arXiv:2603.10165). **VRAM:** 2 ГБ.

### 14. OPD Pipeline (On-Policy Distillation)
Hindsight-Guided distillation из пользовательских правок для персонализации.
**Источник:** OpenClaw-RL (arXiv:2603.10165). **VRAM:** 14 ГБ.

### 15. Memento Episode Memory
Эпизодическая память успешных траекторий (без GPU). Расширение memory_gc.py.
**Источник:** arXiv:2508.16153.
