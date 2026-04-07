---
type: protocol
domain: safety
created: 2026-04-06
tags: [protocol, safety, hallucination, march, verification]
---

# MARCH Hallucination Prevention Protocol

## Acronym
- **M**emory check — query SuperMemory for supporting evidence
- **A**rchive check — query Obsidian Vault for vault-backed verification
- **R**eference check — verify against web sources
- **C**ross-reference — compare across multiple sources
- **H**euristic check — structural hallucination patterns

## Cascade Priority
1. SuperMemory (fastest, most trusted)
2. Obsidian Vault (local knowledge base)
3. Web verification (slowest, least trusted)
4. Flag as unverified

## Detection Patterns

| Pattern | Detection Method | Confidence |
|---------|-----------------|------------|
| Fabricated citations | URL validation + source check | High |
| Invented statistics | Cross-reference with known data | Medium |
| Temporal confusion | Date/event timeline check | High |
| Authority fabrication | Verify person/org existence | Medium |
| Logical contradiction | Claim consistency analysis | High |

## Response Actions

- **Verified claim**: Mark as trusted, add to vault
- **Contradicted claim**: Flag to user, show sources
- **Unverifiable claim**: Add disclaimer, suggest verification
- **Known hallucination pattern**: Block and regenerate

## Vault Learning
- Each verification result → logged to vault
- Accumulates verified facts for future reference
- Reduces need for external verification over time

[[Pipeline_Patterns]] [[Learning_Loop]]
