---
name: openrouter-models
description: "OpenRouter model selection, routing, failover, cost optimization, prompt engineering. Use when: choosing models for tasks, configuring model routing, optimizing LLM costs, comparing model capabilities on OpenRouter."
version: 1.0.0
---

# OpenRouter Model Expert

## Purpose

Expert model selection, routing, and cost optimization for OpenRouter API.

## Model Tiers (for bot pipeline)

### Tier 1: Free Models (daily tasks, bulk processing)

| Model                                         | Context | Strengths                        |
| --------------------------------------------- | ------- | -------------------------------- |
| `deepseek/deepseek-chat-v3-0324:free`         | 128K    | Coding, analysis, multilingual   |
| `nvidia/llama-3.1-nemotron-70b-instruct:free` | 128K    | Instruction following, reasoning |
| `google/gemini-2.0-flash-exp:free`            | 1M      | Huge context, fast, multimodal   |
| `meta-llama/llama-3.3-70b-instruct:free`      | 128K    | General purpose, balanced        |

### Tier 2: Budget Models ($0.01–0.10 per 1M tokens)

| Model                        | Strengths                  |
| ---------------------------- | -------------------------- |
| `deepseek/deepseek-r1`       | Deep reasoning, math, code |
| `qwen/qwen-2.5-72b-instruct` | Multilingual, coding       |
| `anthropic/claude-3.5-haiku` | Fast, accurate, tool use   |

### Tier 3: Premium (when quality matters)

| Model                       | Strengths                |
| --------------------------- | ------------------------ |
| `anthropic/claude-sonnet-4` | Best coding, analysis    |
| `google/gemini-2.5-pro`     | Huge context reasoning   |
| `openai/gpt-4.1`            | Reliable general purpose |

## Routing Strategy

```python
MODEL_ROUTING = {
    "code_generation": "deepseek/deepseek-chat-v3-0324:free",
    "code_review": "anthropic/claude-sonnet-4",
    "reasoning": "deepseek/deepseek-r1",
    "summarization": "google/gemini-2.0-flash-exp:free",
    "translation": "qwen/qwen-2.5-72b-instruct",
    "classification": "meta-llama/llama-3.3-70b-instruct:free",
    "creative_writing": "anthropic/claude-sonnet-4",
}

async def route_request(task_type: str, messages: list, fallback_chain: list[str] | None = None):
    model = MODEL_ROUTING.get(task_type, "deepseek/deepseek-chat-v3-0324:free")
    chain = fallback_chain or [model, "google/gemini-2.0-flash-exp:free", "meta-llama/llama-3.3-70b-instruct:free"]
    for m in chain:
        try:
            return await call_openrouter(messages, model=m)
        except (httpx.HTTPStatusError, asyncio.TimeoutError):
            continue
    raise AllModelsFailedError(chain)
```

## Failover Configuration

```json
{
  "route": "fallback",
  "models": [
    "deepseek/deepseek-chat-v3-0324:free",
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free"
  ]
}
```

## Cost Optimization Rules

1. **Start with free tier** — DeepSeek v3 and Gemini Flash handle 90% of tasks
2. **Use premium only for**: code review, complex reasoning, final user-facing output
3. **Batch processing**: use free models with longer timeouts
4. **Cache responses** for repeated queries (same prompt hash = same response)
5. **Monitor usage**: check `X-RateLimit-Remaining` headers

## Prompt Engineering for OpenRouter

1. **System prompt matters**: Smaller models (70B) need clearer system prompts
2. **Structured output**: Use JSON mode with `response_format: { type: "json_object" }`
3. **Chain of thought**: Add "Think step by step" for reasoning tasks on free models
4. **Temperature**:
   - 0.0 for deterministic tasks (code, classification)
   - 0.3 for analysis
   - 0.7 for creative tasks
