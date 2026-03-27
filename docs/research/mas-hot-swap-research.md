# Deep Research: MAS с горячей заменой моделей/ролей БЕЗ потери контекста

**Дата:** 2026-03-21  
**Модель:** Qwen/Qwen2.5-Coder-14B-Instruct-AWQ  
**Бенчмарк:** avg 22.1 tok/s, peak 36.1 tok/s, TTFT ~2.3s  
**Hardware:** RTX 5060 Ti 16GB, VRAM 15.8/16.3 GiB (97%)

---

## Текущая проблема

`VLLMModelManager.ensure_model_with_lora()` выполняет **полный перезапуск сервера** при смене модели/LoRA:

```python
await self._stop_server()
await self._start_server_with_lora(model_name, lora_adapter_path)
```

Это уничтожает весь KV-кеш, prefix-cache блоки, in-flight запросы. Перезапуск занимает ~3-5 минут.

---

## 1. KV Cache при смене модели

### Automatic Prefix Caching (APC)

vLLM использует хеш для кеширования KV-блоков:

```
block_hash = hash(parent_hash, block_tokens, extra_hashes)
```

`extra_hashes` включает LoRA ID → блоки разных LoRA НЕ разделяются.

**Но если все 20 ролей используют одну базовую модель БЕЗ LoRA** (как сейчас) — APC работает идеально, общие части промптов переиспользуются.

### KV Offloading (CPU)

vLLM v1 имеет `vllm/v1/kv_offload/` с CPU/SSD backends:

- Выгрузка KV-блоков из GPU VRAM в системную RAM
- LRU/ARC стратегии вытеснения
- Для 64GB RAM: ~4x расширение ёмкости кеша

### KV Transfer Connectors

| Коннектор              | Назначение                                   |
| ---------------------- | -------------------------------------------- |
| `lmcache_connector`    | Внешнее KV-хранилище, переживает перезапуски |
| `offloading_connector` | GPU→CPU с async prefetch                     |
| `nixl_connector`       | NVIDIA NIXL zero-copy GPU-to-GPU             |
| `mooncake_connector`   | Распределённый KV store                      |

### Вывод

- **Стратегия A (рекомендуемо):** Не менять базовую модель, dynamic LoRA swap → prefix cache СОХРАНЯЕТСЯ
- **Стратегия B:** KV offloading на CPU → расширяет ёмкость ~4x
- **Стратегия C:** LMCache → персистентный KV store на диске/RAM

---

## 2. Горячая смена LoRA БЕЗ перезапуска

### Dynamic LoRA Loading API (vLLM v0.17+)

```bash
# Загрузка (без остановки сервера!)
POST /v1/load_lora_adapter
{"lora_name": "planner-lora", "lora_path": "/mnt/d/lora_adapters/openclaw-14b-v1"}

# Выгрузка
POST /v1/unload_lora_adapter
{"lora_name": "planner-lora"}
```

**Требования:**

- `VLLM_ALLOW_RUNTIME_LORA_UPDATING=True`
- Сервер запущен с `--enable-lora`
- `--max-loras 5` (для 5 шагов pipeline)

### S-LoRA / Punica

- vLLM интегрировал Punica (`vllm/lora/punica_wrapper/`) — оптимизированные CUDA ядра
- Разные LoRA адаптеры в одном batch — нет необходимости serializing запросов
- Все адаптеры в RAM, в GPU загружаются по требованию

### Для OpenClaw

1. Запустить vLLM **один раз** с `--enable-lora --max-loras 5`
2. Загружать LoRA через REST API по мере необходимости
3. В запросе указывать `model="planner-lora"` для нужной роли
4. Base model KV cache СОХРАНЯЕТСЯ

---

## 3. Стратегии передачи контекста

### Общий системный промпт (максимизация prefix cache)

```python
COMMON_PREFIX = "[OpenClaw MAS] Task: {task} | State: {state}"
# + ROLE_SPECIFIC_SUFFIX для каждой роли
```

Экономит до 50-70% токенов на prefill через APC.

### Shared Context Store (Redis)

```json
{
    "task_id": "uuid",
    "pipeline_state": {
        "planner_output": {"plan": "...", "summary": "..."},
        "foreman_output": {"subtasks": [...]},
        "executor_output": null
    },
    "shared_context": {
        "original_task": "...",
        "accumulated_tokens": 423
    }
}
```

### Semantic Memory (ChromaDB)

- Каждый pipeline сохраняет результат + паттерн в ChromaDB
- RAG поиск по предыдущим решениям для новых задач

---

## 4. Архитектура общей памяти

```
┌──────────────────────────────────────┐
│       Уровень 1: GPU VRAM           │
│  KV Cache (APC) ~6GB                │
│  LoRA Weights (active) ~0.5GB       │
├──────────────────────────────────────┤
│       Уровень 2: System RAM         │
│  KV Offload (evicted) ~24GB         │
│  LoRA Pool (all adapters) ~2GB      │
├──────────────────────────────────────┤
│       Уровень 3: Persistent         │
│  Redis (task state, summaries)      │
│  ChromaDB (semantic memory)         │
└──────────────────────────────────────┘
```

---

## 5. План реализации

### Фаза 1: Dynamic LoRA без перезапуска (1-2 дня)

- Добавить `load_lora_runtime()` / `unload_lora_runtime()` в VLLMModelManager
- Запускать сервер с `--enable-lora --max-loras 5`
- Env: `VLLM_ALLOW_RUNTIME_LORA_UPDATING=True`

### Фаза 2: Shared Context Architecture (2-3 дня)

- `PipelineContextManager` — передача состояния между шагами
- Общий `COMMON_PREFIX` для максимизации APC
- Redis/SQLite для pipeline state

### Фаза 3: KV Offloading (1 день)

- `--enable-kv-cache-offloading` в vLLM args
- CPU offload для расширения ёмкости кеша

### Фаза 4: Ролевые LoRA (5-7 дней)

- `planner-lora` (rank 16) — декомпозиция задач
- `executor-lora` (rank 32) — написание кода
- `auditor-lora` (rank 16) — code review
- `archivist-lora` (rank 8) — суммаризация

### Фаза 5: Мониторинг

- Prometheus: `vllm:prefix_cache_hit_rate`, `vllm:kv_cache_usage`, `vllm:time_to_first_token`

---

## 6. Ключевые статьи

| Статья                                   | Год  | Ключевая идея                                 |
| ---------------------------------------- | ---- | --------------------------------------------- |
| S-LoRA (arXiv:2311.03285)                | 2023 | Unified Paging для тысяч LoRA; Punica kernels |
| Punica (arXiv:2310.18547)                | 2023 | Multi-tenant LoRA serving, SGMV CUDA kernels  |
| PagedAttention (arXiv:2309.06180)        | 2023 | Paged KV-cache — основа vLLM                  |
| SGLang RadixAttention (arXiv:2312.07104) | 2023 | Radix tree KV cache; automatic prefix sharing |
| LMCache                                  | 2024 | Persistent KV cache, vLLM integration         |

---

## Итоговая рекомендация

**Да, горячая замена моделей/ролей без потери контекста ВОЗМОЖНА:**

1. **Быстрый путь (уже доступно):** Dynamic LoRA API в vLLM v0.17+ — загрузка/выгрузка LoRA без перезапуска сервера. KV cache базовой модели сохраняется.

2. **Для разных архитектур** (Qwen ↔ DeepSeek): контекст передаётся через Redis/ChromaDB в текстовом виде + сжатие. KV cache несовместим между разными архитектурами.

3. **Для одной архитектуры + LoRA:** Prefix caching + LoRA hot-swap = 0 потерь для общего контекста, ~2с на загрузку адаптера вместо ~3-5 мин перезапуска.

**Ожидаемый эффект:** TTFT снижается на 60-80% благодаря APC. Полное устранение 3-5 мин простоя при перезапуске сервера.
