---
type: concept
domain: models
created: 2026-04-06
tags: [models, openrouter, quality, baseline]
---

# Model Quality Baseline

## Current Model Roster (FULL Qwen 3.6 Plus migration — v2)

### Tier 1 — Primary (ALL text tasks)
| Model | ID | Context | Cost | SWE-bench | Speed | Use |
|-------|----|---------|------|-----------|-------|-----|
| Qwen 3.6 Plus | `qwen/qwen3.6-plus:free` | 1M | $0 | 78.8% | 45 tok/s | **ALL**: general, code, research, risk, tools, meta, intent, data_parsing, expand, memory_gc |

### Tier 2 — Fallback only
| Model | ID | Context | Cost | Use |
|-------|----|---------|------|-----|
| DeepSeek R1 | `deepseek/deepseek-r1:free` | 131K | $0 | fallback reasoning |
| Gemma 3 27B | `google/gemma-3-27b-it:free` | 131K | $0 | fallback vision |

### Tier 3 — Vision (NOT replaceable)
| Model | ID | Context | Cost | Use |
|-------|----|---------|------|-----|
| Nemotron Nano 12B VL | `nvidia/nemotron-nano-12b-v2-vl:free` | 32K | $0 | vision, video analysis |

### Retired models (no longer in config)
- ~~`nvidia/nemotron-3-super-120b-a12b:free`~~ → replaced by Qwen 3.6+
- ~~`arcee-ai/trinity-large-preview:free`~~ → replaced by Qwen 3.6+
- ~~`arcee-ai/trinity-mini:free`~~ → replaced by Qwen 3.6+
- ~~`meta-llama/llama-3.3-70b-instruct:free`~~ → replaced by Qwen 3.6+
- ~~`qwen/qwen-2.5-coder-32b-instruct:free`~~ → replaced by Qwen 3.6+
- ~~`google/gemma-3-12b-it:free`~~ → replaced by Qwen 3.6+

## Why Qwen 3.6 Plus

1. **Контекст 1M** — в 31x больше чем Nemotron (32K). Позволяет анализировать целые кодовые базы
2. **SWE-bench 78.8%** — один из лучших показателей среди free моделей
3. **Reasoning tokens** — встроенное Chain-of-Thought, улучшает quality на сложных задачах
4. **Tool calling** — нативная поддержка, 4.61% error rate (приемлемо)
5. **45 tok/s** — достаточная скорость для interactive use
6. **$0** — бесплатная полностью (и input и output)
7. **Hybrid attention** — Linear attention + Sparse MoE = эффективна на длинных контекстах

## Quality Metrics (pre-training baseline)

| Metric | Nemotron Baseline | Expected Qwen 3.6+ |
|--------|-------------------|---------------------|
| Code quality (self-eval) | 6.5/10 | 8.0/10 |
| Research depth (sources/query) | 4-6 | 8-12 |
| Hallucination rate | ~15% | ~8% |
| Context utilization | 30% of 32K | 60% of 1M |
| Reasoning chain length | 2-3 steps | 5-8 steps |
| Tool calling success | 80% | 92% |
| Brigade coherence | Medium | High |

[[OpenClaw_Architecture]] [[Learning_Loop]] [[Pipeline_Patterns]]
