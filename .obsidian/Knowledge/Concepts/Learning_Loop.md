---
type: concept
domain: learning
created: 2026-04-06
tags: [learning, evolution, self-improvement, cognitive]
---

# Learning Loop — Self-Improvement Pipeline

## Architecture

```
Execution → SAGE Score → CognitiveEvolution → Prompt Versioning
     ↓                        ↓
 ObsidianVault          SkillDiscovery
     ↓                        ↓
Context Injection ←── Pattern Extraction
```

## Components

### 1. CognitiveEvolutionEngine (`src/cognitive_evolution.py`)
- Записывает каждый outcome (role, task_type, success, score, feedback)
- Автоматически эволюционирует промпты ролей при ≥5 outcome'ах с регрессией
- Обнаруживает новые скиллы из паттернов успешных задач

### 2. ObsidianBridge (`src/obsidian_bridge.py`)
- Сохраняет результаты research в vault
- Подтягивает релевантный контекст перед каждым LLM-вызовом
- Структура: Research/, Learning/, Knowledge/, Pipeline/

### 3. SAGE Feedback (`src/pipeline/_sage.py`)
- Оценивает качество каждого chain execution (0.0-1.0)
- Записывает corrections в CognitiveEvolution
- Сохраняет feedback в vault для ретроспективного анализа

### 4. MARCH Protocol (`src/safety/hallucination.py`)
- Верифицирует клеймы через SuperMemory + Vault
- Cascade: Memory → Vault → Web → Flag
- Снижает hallucination rate через knowledge grounding

## Learning Signals

| Signal | Source | Weight | Frequency |
|--------|--------|--------|-----------|
| SAGE score | Pipeline execution | 0.3 | Every task |
| User feedback | Telegram reactions | 0.25 | Per response |
| Tool success rate | Tool execution logs | 0.2 | Per tool call |
| Research confidence | Research pipeline | 0.15 | Per research |
| Contradiction rate | MARCH protocol | 0.1 | Per verification |

## Obsidian Vault Training Data Structure

```
.obsidian/
├── Knowledge/
│   ├── Concepts/       ← Domain knowledge (architecture, APIs, protocols)
│   ├── Protocols/      ← Behavioral protocols (how to handle tasks)
│   └── Snippets/       ← Proven code patterns
├── claw_logic/         ← Bot-specific reasoning rules
├── Learning_Log.md     ← Chronological learning events
└── Obsidian_Brain_Dump.md ← Raw context
```

## Baseline Metrics (before Obsidian training)

- Research vault notes: 0
- Learning log entries: 0
- Skill notes: 0
- Protocol notes: 0
- Cognitive evolution state: empty
- Prompt versions: baseline (v1.0)
- Knowledge graph nodes: 20 (Concepts only, Dmarket domain)

[[Model_Quality_Baseline]] [[Pipeline_Patterns]] [[OpenClaw_Architecture]]
