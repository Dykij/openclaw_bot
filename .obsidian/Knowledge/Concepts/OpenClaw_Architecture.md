---
type: concept
domain: architecture
created: 2026-04-06
tags: [architecture, pipeline, agents, core]
---

# OpenClaw Bot Architecture

## Core Components

1. **LLM Gateway** (`src/llm/gateway.py`) — unified inference router
   - Primary: OpenRouter API (cloud-only)
   - SmartModelRouter for task-type → model mapping
   - AdaptiveTokenBudget for context management
   - HITL approval gate for high-risk actions

2. **Brigade Pipeline** (`src/pipeline/`) — multi-agent chain execution
   - Planner → Coder → Auditor → Archivist flow
   - SAGE quality scoring and chain rebuilds
   - AFlow dynamic chain generation via LLM

3. **Deep Research** (`src/research/`) — iterative research pipeline
   - Multi-perspective query reformulation
   - Academic + web + news + memory search
   - Evidence scoring, dedup, contradiction detection
   - Adaptive stopping based on confidence threshold (0.75)

4. **MAS Orchestrator** (`src/mas/orchestrator.py`) — agent lifecycle
   - Agent registration, capability-based routing
   - Autonomous loop for background tasks
   - Health monitoring and auto-recovery

5. **Memory System** (`src/memory_system/`) — tiered storage
   - Hot (ChromaDB vectors), Warm (disk), Cold (archive)
   - SuperMemory for cross-session knowledge
   - EpisodicMemory for session replay

6. **Safety** (`src/safety/`) — guardrails
   - HallucinationDetector (heuristic)
   - MARCH Protocol (cross-agent verification)
   - CodeValidator (semgrep, bandit, ruff)

7. **Obsidian Bridge** (`src/obsidian_bridge.py`) — knowledge persistence
   - Bidirectional vault integration
   - Research results → vault notes
   - Vault context → research pipeline

8. **Cognitive Evolution** (`src/cognitive_evolution.py`) — self-learning
   - Execution outcome tracking
   - Role prompt versioning and auto-tuning
   - Skill discovery from patterns

## Data Flow

```
User → Telegram/Discord → Intent Classification → Model Router
  → Brigade Pipeline (Planner → Coder → Auditor)
  → SAGE Quality Check → CognitiveEvolution
  → Response → User
  → Vault Persistence (learning logs, research notes)
```

## Key Constraints

- Cloud-only inference (no local GPU for LLM)
- Free models only (OpenRouter :free tier)
- RTX 5060 Ti 16GB VRAM available for local compute (embeddings, etc.)
- Context windows: 32K-1M depending on model

[[Model_Quality_Baseline]] [[Pipeline_Patterns]] [[Learning_Loop]]
