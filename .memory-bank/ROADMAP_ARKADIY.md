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

## 🟡 Приоритет: ВАЖНЫЙ (AlphaXiv Research → РЕАЛИЗОВАНО)

### 7. Structured Interaction Logging (JSONL) ✅ ГОТОВО
**Файл:** `src/interaction_logger.py`
**Решение:** JSONL-логи пар (action, next_state, user_correction) для всех MCP tool calls.
**Источник:** OpenClaw-RL (arXiv:2603.10165) — unified interaction signals.
**VRAM:** 0 ГБ | **Тесты:** 12/12 ✅

### 8. GRPO Training Pipeline (LoRA + Unsloth) ✅ ГОТОВО
**Файл:** `src/grpo_trainer.py`
**Решение:** GRPO + LoRA 4-bit через Unsloth, GRPO-λ adaptive rewards, prompt augmentation.
**Источник:** arXiv:2503.16219 (GRPO for Small LLMs), arXiv:2505.18086 (GRPO-λ).
**VRAM:** 8–14 ГБ | **Тесты:** 13/13 ✅ | **Примечание:** GPU-зависимости нужны для обучения

### 9. Reward Verifier (RLVR) ✅ ГОТОВО
**Файл:** `src/reward_verifier.py`
**Решение:** 10 типов автоматических rewards для Dmarket и OpenClaw бригад.
**Источник:** DeepSeek-R1 (arXiv:2501.12948) — RLVR concept.
**VRAM:** 0 ГБ | **Тесты:** 17/17 ✅

### 10. LoRA Adapter Hot-Swap ✅ ГОТОВО
**Файл:** `src/vllm_manager.py` (обновлён)
**Решение:** `ensure_model_with_lora()` + `list_available_lora_adapters()` в VLLMModelManager.
**VRAM:** +1–2 ГБ к базовой модели

### 11. Memento Episode Memory ✅ ГОТОВО
**Файл:** `src/memory_gc.py` (обновлён)
**Решение:** `store_successful_episode()` + `retrieve_similar_episodes()` в MemoryGarbageCollector.
**Источник:** arXiv:2508.16153. **VRAM:** 0 ГБ

### 12. Training Environment Setup ✅ ГОТОВО
**Файл:** `scripts/setup_training.py`
**Решение:** Проверка GPU, зависимостей, создание директорий для обучения.

### 13. Research Paper Parser ✅ ГОТОВО
**Файл:** `scripts/research_paper_parser.py`
**Решение:** Парсер 4 сайтов (Semantic Scholar, Papers With Code, arXiv, HuggingFace).
**Результат:** 80 статей в `docs/ru/research/` (топ 20 с каждого сайта)

> 📚 Полный анализ: `docs/ru/reference/alphaxiv-model-training-analysis.md`
> 📚 Анализ сайтов: `docs/ru/research/site-analysis.md`
> 📚 Статьи: `docs/ru/research/` (4 папки × 20 статей)

---

## 🟢 Приоритет: БЭКЛОГ

### 10. Auto-scaling Context Window
Динамическая подстройка `num_ctx` в зависимости от сложности задачи.

### 11. Multi-modal Input (Images)
Поддержка Telegram-фото через vision-модели (LLaVA).

### 12. Prometheus Metrics Export
Экспорт метрик для Grafana-дашборда.

### 14. PRM Judge (Process Reward Model)
Маленькая модель-судья (Qwen-1.5B) для real-time оценки качества ответов.
**Источник:** OpenClaw-RL (arXiv:2603.10165). **VRAM:** 2 ГБ.

### 15. OPD Pipeline (On-Policy Distillation)
Hindsight-Guided distillation из пользовательских правок для персонализации.
**Источник:** OpenClaw-RL (arXiv:2603.10165). **VRAM:** 14 ГБ.
