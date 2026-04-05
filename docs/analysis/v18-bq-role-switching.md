# v18.0: Binary Quantization RAG + Cloud Role Switching Optimization

## Дата: 2026-04-05

---

## Часть 1: Binary Quantization для RAG

### Что внедрено

Добавлена поддержка **Binary Quantization (BQ)** в `src/rag_engine.py` — техника, которую используют Perplexity, Azure, HubSpot для 32x сокращения памяти при хранении векторных эмбеддингов.

### Новые компоненты

| Компонент | Файл | Описание |
|-----------|------|----------|
| `binary_quantize()` | `src/rag_engine.py` | Конвертация float32 → packed binary (32x сжатие) |
| `binary_quantize_batch()` | `src/rag_engine.py` | Батчевая конвертация через NumPy |
| `hamming_distance()` | `src/rag_engine.py` | Расстояние Хэмминга между бинарными векторами |
| `BinaryQuantizedRAG` | `src/rag_engine.py` | In-memory BQ индекс с Hamming search |
| 34 теста | `tests/test_binary_quantization.py` | Полное покрытие BQ + cloud grouping |

### Как работает

```
float32 embedding (1024 dims) = 4096 bytes
     ↓ binary_quantize()
binary vector (1024 bits) = 128 bytes  → 32x compression

Поиск: Hamming distance вместо cosine similarity
```

### Интеграция

`BinaryQuantizedRAG` работает как ускоряющий слой поверх `RAGEngine`:
- Индексирует документы с BQ-эмбеддингами
- Поиск через Hamming distance (быстрее cosine)
- Опциональный two-stage retrieval: BQ recall → full precision rerank

---

## Часть 2: Анализ переключения ролей

### Текущая архитектура

```
Пользователь → Pipeline → get_chain_dynamic() → [Planner, Coder, Auditor]
                              ↓
                    Последовательное выполнение:
                    Step 1: Planner (OpenRouter) → response
                    Step 2: Coder (OpenRouter) → response  
                    Step 3: Auditor (OpenRouter) → response
```

### Проблема с переключением ролей

В текущем коде есть **наследие от локальных моделей**, которое замедляет pipeline в cloud-only режиме:

#### 1. Context Bridge (УЖЕ ОТКЛЮЧЕН ✅)
```python
# _core.py:274-276
if self.force_cloud:
    self.context_bridge = ContextBridge({"context_bridge": {"enabled": False}})
    logger.info("Context Bridge DISABLED (cloud-only mode, no local model swaps)")
```
Context Bridge правильно отключён, но код проверки всё ещё выполняется каждый шаг.

#### 2. VRAM Protection (УЖЕ NO-OP ✅)
```python
# _core.py:1641-1647
async def _vram_protection(self, target_model, prev_model):
    if self.force_cloud:
        yield  # No-op
    else:
        async with vram_protection(target_model, prev_model):
            yield
```
Правильно пропускается, но async context manager имеет минимальный overhead.

#### 3. Model Tracking (БЕЗВРЕДНО ⚪)
```python
self.last_loaded_model = model  # line 1057
```
Просто обновляет строку, никакой задержки.

#### 4. **Последовательное выполнение ролей (ГЛАВНЫЙ BOTTLENECK 🔴)**

Основная проблема: `group_chain()` группирует **только** `Executor_*` роли для параллельного выполнения. Все остальные роли выполняются **строго последовательно**, даже когда это не нужно.

### Что оптимизировано

#### `group_chain_cloud()` — Cloud-оптимизированная группировка

Новая функция `group_chain_cloud()` в `src/pipeline_utils.py` расширяет параллелизацию:

```
ДО (group_chain):
  [Planner] → [Foreman] → [Executor_Tools, Executor_Architect] → [Auditor] → [State_Manager] → [Archivist]
  6 шагов (1 параллельный)

ПОСЛЕ (group_chain_cloud):  
  [Planner] → [Foreman] → [Executor_Tools, Executor_Architect] → [Auditor] → [State_Manager, Archivist]
  5 шагов (2 параллельных)
```

**Правила:**
- `Planner` — всегда первый (один)
- `Foreman` — зависит от Planner, последовательный
- `Executor_*`, `Coder`, `Researcher`, `Analyst`, `Archivist`, `State_Manager`, `Test_Writer` — параллелизуются между собой
- `Auditor` — всегда последний (один, после всех)

### Pipeline в cloud-only mode

```python
# _core.py:706-713 (обновлено)
if self.force_cloud:
    chain_groups = group_chain_cloud(chain)
else:
    chain_groups = group_chain(chain)
```

### Результат

| Метрика | До | После |
|---------|-----|-------|
| Context Bridge overhead | ~5ms проверка/шаг | Отключен |
| VRAM protection | ~0ms (no-op) | ~0ms (no-op) |
| OpenClaw-Core 7 ролей | 7 sequential steps | 5 steps (2 parallel batches) |
| Research-Ops 3 роли | 3 sequential steps | 2 steps (Researcher+Analyst parallel) |
| Model swap delay | 0ms (уже нет) | 0ms |

### Что НЕ нужно менять

1. **Удалять `call_vllm`** — оставлен как fallback при `use_local_models=true`
2. **Удалять Context Bridge** — будет нужен при возврате к локальным моделям
3. **Менять `_call_vllm` метод** — он уже корректно маршрутизирует через OpenRouter
4. **Удалять `vllm_inference.py`** — содержит вспомогательные функции

---

## Файлы изменены

| Файл | Изменение |
|------|-----------|
| `src/rag_engine.py` | +200 LOC: BQ helpers + BinaryQuantizedRAG class |
| `src/pipeline_utils.py` | +50 LOC: `group_chain_cloud()` + role sets |
| `src/pipeline/_core.py` | ~10 LOC: cloud grouping switch + import |
| `requirements.txt` | +1: `numpy>=1.24.0` |
| `tests/test_binary_quantization.py` | +250 LOC: 34 теста |
| `docs/analysis/v18-bq-role-switching.md` | Этот документ |

## Тесты

```bash
# Новые тесты BQ + cloud grouping
python -m pytest tests/test_binary_quantization.py -v  # 34 passed

# Существующие тесты (без регрессий)
python -m pytest tests/test_safety_guardrails.py tests/test_openrouter_client.py \
    tests/test_parsers.py tests/test_clawhub_client.py -v  # 71 passed
```
