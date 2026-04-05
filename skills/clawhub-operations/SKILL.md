---
name: clawhub-operations
description: "ClawHub platform operations: pipeline management, brigade orchestration, SuperMemory, agent deployment, evaluation loops. Use when: managing multi-agent pipelines, configuring brigades, working with ClawHub or SuperMemory."
version: 1.0.0
---

# ClawHub Operations

## Purpose

Manage the ClawHub multi-agent platform: brigades, pipelines, SuperMemory, model routing, and evaluation.

## Brigade Architecture

### Dmarket Brigade (11 roles)

| Role              | Model Tier | Task                           |
| ----------------- | ---------- | ------------------------------ |
| Foreman (Аркадий) | Tier 1     | Task decomposition, delegation |
| Analyst_DMarket   | Tier 1     | Market analysis, price trends  |
| Executor_Tools    | Tier 1     | API calls, tool execution      |
| Strategist        | Tier 2     | Trading strategy formulation   |
| Risk_Assessor     | Tier 1     | Risk evaluation, limits        |
| Test_Writer       | Tier 1     | Test generation, QA            |

### OpenClaw Brigade (9 roles)

| Role         | Model Tier | Task                         |
| ------------ | ---------- | ---------------------------- |
| Orchestrator | Tier 1     | Cross-brigade coordination   |
| ML_Engineer  | Tier 2     | Model selection, fine-tuning |
| DevOps       | Tier 1     | Deployment, monitoring       |
| Security     | Tier 1     | Audit, vulnerability scan    |

## Pipeline Execution

```python
# Pipeline stages
STAGES = [
    "decompose",    # Foreman breaks task into subtasks
    "assign",       # Route subtasks to specialists
    "execute",      # Parallel execution by brigade
    "aggregate",    # Collect and merge results
    "evaluate",     # Quality check + scoring
    "report",       # Generate final output
]
```

## SuperMemory Integration

```python
# Memory tiers
MEMORY_CONFIG = {
    "short_term": {
        "backend": "in_memory",
        "ttl_seconds": 3600,
        "max_items": 1000,
    },
    "long_term": {
        "backend": "chromadb",
        "collection": "openclaw_memories",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    },
    "episodic": {
        "backend": "jsonl",
        "path": "~/.openclaw/agents/{agent_id}/sessions/",
    },
}
```

## Evaluation Loop

```python
# Role performance scoring
EVAL_METRICS = {
    "task_completion_rate": 0.3,  # Did the role complete its task?
    "latency_score": 0.2,        # Response time within budget?
    "quality_score": 0.3,        # Output quality (LLM-as-judge)
    "cost_efficiency": 0.2,      # Cost per quality unit
}

def evaluate_role(role: str, result: dict) -> float:
    score = sum(
        weight * result.get(metric, 0.0)
        for metric, weight in EVAL_METRICS.items()
    )
    return round(score, 3)
```

## Operational Commands

```bash
# Health check
openclaw channels status --probe

# View pipeline status
openclaw pipeline status --verbose

# Run brigade testbench
pnpm test -- --grep "brigade"

# SuperMemory stats
python -m src.supermemory.stats

# Model health report
python scripts/benchmark_tokens.py
```

## Troubleshooting

| Symptom          | Diagnosis                | Fix                                  |
| ---------------- | ------------------------ | ------------------------------------ |
| Pipeline timeout | Model rate limit         | Switch to free tier fallback         |
| Memory OOM       | ChromaDB index too large | Prune old embeddings                 |
| Role failure     | Model hallucination      | Increase temperature=0, add examples |
| Slow execution   | Wrong model for task     | Use model routing table              |
