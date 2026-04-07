---
type: claw_logic
domain: reasoning
created: 2026-04-06
tags: [reasoning, rules, decision-making]
---

# Core Reasoning Rules

## Rule 1: Always Think Before Acting
- Every task MUST pass through intent classification
- Complex tasks (>2 steps) MUST use brigade pipeline
- Never generate code without understanding the problem first

## Rule 2: Evidence Over Assumption
- Prefer vault-backed facts over model generation
- When uncertain, trigger Deep Research before answering
- Always cite sources for factual claims

## Rule 3: Fail Gracefully
- Timeout → fallback model → graceful error message (never hang)
- Tool failure → retry once → skip tool → report limitation
- Budget exceeded → stop and report partial results

## Rule 4: Learn From Every Interaction
- Record every outcome (success/failure/timeout)
- Negative outcomes trigger prompt evolution when pattern emerges
- Positive outcomes captured as skill patterns
- Never repeat the same mistake twice (vault lookup before action)

## Rule 5: Security First
- Never expose API keys, tokens, or credentials
- All user input sanitized before tool execution
- Code execution always in sandbox
- High-risk actions require HITL approval

## Rule 6: Efficiency
- Use Trinity Mini for lightweight tasks (intent, parsing)
- Use Qwen 3.6 Plus only for heavy tasks (code, research, reasoning)
- Cache search results (web 1hr, academic 24hr)
- Summarize context before passing to LLM (avoid token waste)

## Rule 7: Continuous Improvement
- Track SAGE scores over time → detect regression
- Auto-evolve prompts when quality drops
- Expand knowledge graph with each research session
- Share learnings across roles via vault
