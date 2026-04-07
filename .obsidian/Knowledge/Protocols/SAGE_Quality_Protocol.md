---
type: protocol
domain: quality
created: 2026-04-06
tags: [protocol, sage, quality, scoring]
---

# SAGE Quality Scoring Protocol

## Score Components

| Component | Weight | Range | Description |
|-----------|--------|-------|-------------|
| Relevance | 0.30 | 0-1 | How well answer addresses the question |
| Completeness | 0.25 | 0-1 | All aspects of question covered |
| Accuracy | 0.25 | 0-1 | Factual correctness (MARCH-verified) |
| Clarity | 0.10 | 0-1 | Readability, structure, formatting |
| Safety | 0.10 | 0-1 | No harmful content, proper disclaimers |

## Thresholds

| Score | Action |
|-------|--------|
| ≥ 0.8 | Accept, log as positive example |
| 0.6–0.8 | Accept with minor improvements |
| 0.4–0.6 | Retry with adjusted prompt |
| < 0.4 | Reject, escalate to different model/approach |

## Self-Learning Integration

On every SAGE evaluation:
1. Record outcome to CognitiveEvolutionEngine
2. If score < 0.6: record as "failure" with feedback
3. If score ≥ 0.8: record as "success" → skill pattern extraction
4. Save correction notes to Obsidian vault
5. After 5+ failures for same role: trigger prompt evolution

## Anti-Gaming
- Score cannot be overridden by the model being evaluated
- SAGE runs as separate LLM call with lower temperature
- Historical scores tracked for trend analysis

[[Learning_Loop]] [[Pipeline_Patterns]]
