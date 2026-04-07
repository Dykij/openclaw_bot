---
type: protocol
domain: research
created: 2026-04-06
tags: [protocol, research, deep-research, methodology]
---

# Deep Research Protocol

## When to Trigger
- User explicitly requests research/analysis
- Task requires external knowledge not in vault
- Confidence on current knowledge < 0.5

## Execution Steps

1. **Query Reformulation** — Generate 3-5 perspective-shifted queries
2. **Multi-Source Search** — Academic + Web + News + Memory (parallel)
3. **Evidence Scoring** — Relevance (0-1), Source quality (0-1), Freshness
4. **Deduplication** — Semantic similarity > 0.85 → merge
5. **Contradiction Detection** — Cross-reference claims, flag severity
6. **Confidence Estimation** — Hybrid 5-signal:
   - Volume (20%): how many quality sources found
   - Diversity (20%): source variety (academic, news, web)
   - Contradiction penalty (15%): reduce for conflicts
   - Coverage (25%): query coverage
   - LLM assessment (20%): model's own confidence
7. **Adaptive Stopping** — Stop when confidence ≥ 0.75 or iterations ≥ 5
8. **Vault Persistence** — Save findings to `.obsidian/Knowledge/`
9. **Report Generation** — Structured markdown with sources

## Quality Guardrails
- Max 100K chars per LLM context call
- Search cache: Web 1hr, Academic 24hr, max 500 entries
- Always cite sources with URLs
- Flag contradictions in output

## Vault Integration
- Pre-research: Load relevant vault context via ObsidianBridge
- Post-research: Persist results via `persist_research_results()`
- Cross-reference: Check vault for existing knowledge to avoid redundant searches

[[Learning_Loop]] [[Pipeline_Patterns]]
