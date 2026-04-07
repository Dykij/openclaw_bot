---
type: claw_logic
domain: error_handling
created: 2026-04-06
tags: [errors, recovery, resilience]
---

# Error Handling & Recovery Patterns

## Error Classification

| Category | Severity | Action | Example |
|----------|----------|--------|---------|
| Transient | Low | Retry with backoff | API timeout, rate limit |
| Model Error | Medium | Fallback model | Bad response, hallucination |
| Tool Failure | Medium | Skip + report | Tool unavailable, permission denied |
| Budget Exceeded | High | Stop + partial results | Token/cost limit hit |
| Security Violation | Critical | Block + alert | Injection attempt, credential leak |
| System Fatal | Critical | Graceful shutdown | OOM, disk full |

## Recovery Strategies

### API Errors (OpenRouter)
```
Attempt 1: Same model, same request
Attempt 2: Same model, reduced context
Attempt 3: Fallback model (Nemotron)
Attempt 4: Secondary fallback (Trinity Large)
Attempt 5: Error message to user
```

### Hallucination Detected
```
1. Flag specific claims via MARCH
2. Re-generate with higher temperature restriction
3. Add "verified-only" constraint to system prompt
4. If persistent: switch to research mode
```

### Context Overflow
```
1. Summarize oldest messages (keep last 3)
2. Trim code blocks to relevant sections
3. Reduce vault context window
4. If still too large: split into sub-tasks
```

### Brigade Timeout
```
1. Kill stalled agent
2. Retry with timeout × 1.5
3. If 2nd timeout: skip agent, fallback to direct response
4. Log timeout pattern for future avoidance
```

## Learned Error Patterns

This section is dynamically updated by CognitiveEvolution:
- (empty — will be populated after first learning cycle)
