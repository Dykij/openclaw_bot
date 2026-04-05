---
name: prompt-engineer
description: "LLM prompt engineering: system prompts, chain-of-thought, few-shot, structured output, role playing, tool use prompts. Use when: crafting prompts for pipeline roles, optimizing LLM output quality, reducing hallucination."
version: 1.0.0
---

# Prompt Engineer

## Purpose

Craft high-quality LLM prompts: system prompts, CoT, few-shot, structured output for OpenRouter models.

## Prompt Patterns

### System Prompt Structure

```
You are [ROLE] with expertise in [DOMAIN].

## Rules
1. [Constraint 1]
2. [Constraint 2]

## Output Format
Respond in [FORMAT] with the following structure:
- field1: description
- field2: description
```

### Chain-of-Thought (for reasoning tasks)

```
Solve step by step:
1. Identify the key variables
2. Apply the relevant formula/rule
3. Calculate the result
4. Verify by checking edge cases

Show your reasoning before the final answer.
```

### Few-Shot (for classification/formatting)

```
Classify the sentiment of each review.

Review: "Great product, fast delivery!" → positive
Review: "Broken on arrival, worst purchase" → negative
Review: "It works, nothing special" → neutral

Review: "{user_input}" →
```

### Structured JSON Output

```
Respond ONLY with valid JSON matching this schema:
{
  "analysis": "string — Brief analysis",
  "score": "number — Confidence 0.0 to 1.0",
  "tags": ["string — Relevant category tags"]
}

Do not include any text before or after the JSON.
```

## Model-Specific Tips

| Model                | Tip                                                              |
| -------------------- | ---------------------------------------------------------------- |
| DeepSeek v3 (free)   | Works well with detailed system prompts, Chinese/English         |
| Llama 3.3 70B (free) | Needs clear formatting instructions, good at following rules     |
| Gemini Flash (free)  | Huge context — can include full codebases, good at summarization |
| DeepSeek R1          | Add "Think step by step" for complex reasoning                   |

## Anti-Hallucination Techniques

1. **Ground in context**: "Answer ONLY based on the provided text"
2. **Uncertainty signal**: "If unsure, say 'I don't have enough information'"
3. **Citation requirement**: "Quote the exact source text that supports your answer"
4. **Temperature 0.0** for factual tasks
5. **Verification step**: "After answering, verify your response against the input"

## Pipeline Role Prompt Template

```python
ROLE_PROMPT = """You are {role_name} in the OpenClaw MAS pipeline.

## Your Mission
{mission_description}

## Input
{input_schema}

## Output Requirements
{output_format}

## Constraints
- Stay within your role scope
- Do not make assumptions about other roles' outputs
- If input is insufficient, respond with {"status": "needs_info", "missing": [...]}
"""
```
