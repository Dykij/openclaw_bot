---
type: claw_logic
domain: model_selection
created: 2026-04-06
tags: [models, routing, optimization]
---

# Model Selection Logic

## Decision Tree (v2 — Full Qwen 3.6+ Migration)

```
Task received
  ├─ Is it vision/video? → Nemotron Nano 12B VL (only vision model)
  └─ Everything else → Qwen 3.6 Plus (1M context, reasoning tokens)
      ├─ intent classification
      ├─ data parsing  
      ├─ code generation
      ├─ research
      ├─ risk analysis
      ├─ tool execution
      ├─ memory GC / summarization
      └─ general Q&A
```

## Qwen 3.6 Plus — Single-Model Strategy
- **1M context**: можно загрузить всю кодовую базу (~200K tokens)
- **Reasoning tokens**: автоматический CoT для сложных задач
- **SWE-bench 78.8%**: топ для free моделей
- **Tool calling**: 4.61% error rate, достаточно для production
- **65K max output**: длинные ответы без обрезки
- Единая модель убирает overhead на model routing / fallback chains

## Fallback Chain
```
Qwen 3.6 Plus → DeepSeek R1 (reasoning fallback) → Error
```

## Context Window Strategy
- Short task (<4K tokens): standard prompt
- Medium task (4K-32K): add vault context + history
- Large task (32K-200K): full codebase context (Qwen 3.6+ only)
- Massive task (200K+): sliding window + summarization

## Token Budget Allocation
| Component | Budget % |
|-----------|----------|
| System prompt | 5% |
| Vault context | 15% |
| User message + history | 30% |
| Code/data payload | 30% |
| Output reservation | 20% |
