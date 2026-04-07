---
type: concept
domain: pipeline
created: 2026-04-06
tags: [pipeline, patterns, chains, best-practices]
---

# Pipeline Patterns — Proven Execution Strategies

## Chain Patterns

### 1. Standard Brigade (default)
```
Planner → Coder → Auditor → Response
```
- Best for: code tasks, feature implementation
- SAGE threshold: ≥0.6
- Retry: up to 2x on SAGE failure

### 2. Research → Action
```
DeepResearch → Planner → Coder → Auditor → Response
```
- Best for: unknown domains, API exploration
- Triggers: explicit "исследуй"/"research" or high uncertainty

### 3. Direct Response
```
Intent → LLM → Response
```
- Best for: simple Q&A, greetings, status queries
- No brigade overhead

### 4. Ensemble Voting (complex tasks)
```
[Executor×2 (T=0.7, T=1.0)] → Auditor picks winner → Response
```
- Triggers: complexity ≥ "complex"
- 2x cost but higher quality

### 5. AFlow Dynamic
```
LLM generates chain → Execute chain → SAGE → Response
```
- Triggers: novel task patterns
- LLM decides which agents to invoke

## Anti-Patterns (Learned)

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| Infinite research loop | Confidence never reaches threshold | Hard limit: 5 iterations max |
| Tool spam | Agent calls tools repeatedly without progress | Exponential backoff on same tool |
| Context overflow | 32K context exhausted mid-chain | Adaptive token budget + summarization |
| Hallucination cascade | Bad output feeds next agent | MARCH verification between agents |
| Brigade deadlock | Planner waits for Coder, Coder waits for Planner | Timeout + fallback to Direct |

## Quality Gates

1. **Pre-execution**: Intent classification, budget check
2. **Mid-execution**: SAGE continuous scoring
3. **Post-execution**: MARCH hallucination check, code validation
4. **Post-response**: CognitiveEvolution learning signal

## Task Type → Pattern Mapping

| Task Type | Preferred Pattern | Model Tier |
|-----------|------------------|------------|
| code | Standard Brigade | Tier 1 (Qwen 3.6+) |
| research | Research → Action | Tier 1 |
| general | Direct Response | Tier 1 |
| intent | Direct Response | Tier 3 (Trinity Mini) |
| risk_analysis | Standard Brigade | Tier 1 |
| tool_execution | Standard Brigade | Tier 1 |
| data_parsing | Direct Response | Tier 3 |
| vision | Direct Response | Tier 4 (Nemotron VL) |

[[OpenClaw_Architecture]] [[Model_Quality_Baseline]] [[Learning_Loop]]
