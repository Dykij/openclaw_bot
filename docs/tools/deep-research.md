---
summary: "Using deep research with OpenClaw web search providers for multi-step internet research and synthesis"
read_when:
  - You want to use OpenClaw for deep research tasks
  - You want to understand how deep research differs from regular web search
  - You are configuring Perplexity sonar-reasoning-pro or ChatGPT deep research
  - You want to optimize research quality with web search tools
title: "Deep Research"
---

# Deep research

Deep research is multi-step internet research where the agent issues multiple search queries, reads and cross-references sources, and synthesizes a comprehensive answer with citations. This page covers how to configure and use deep research with OpenClaw.

## What deep research does

Regular web search returns a quick list of results for a single query. Deep research goes further:

1. **Decomposes** the question into sub-questions
2. **Searches** the web multiple times with refined queries
3. **Reads** full pages from promising results
4. **Cross-references** information across sources
5. **Identifies gaps** and searches again to fill them
6. **Synthesizes** a comprehensive answer with inline citations

Use deep research when you need thorough, multi-source answers — not quick lookups.

## Choosing a provider for deep research

OpenClaw supports multiple web search providers. Each has different strengths for deep research:

| Provider | Deep research capability | Model | Best for |
| -------- | ------------------------ | ----- | -------- |
| **Perplexity (Reasoning)** | Native multi-step research | `sonar-reasoning-pro` | Complex questions requiring chain-of-thought analysis |
| **Perplexity (Pro)** | Fast Q&A with web context | `sonar-pro` | Research questions needing AI-synthesized answers |
| **Gemini** | Google Search grounding | `gemini-2.5-flash` | Questions benefiting from Google search coverage |
| **Grok** | Real-time web search | `grok-4-1-fast` | Time-sensitive research requiring latest information |
| **Brave** | Traditional web search | N/A (returns raw results) | Structured results when the agent should do its own synthesis |
| **Kimi** | Native web search | `moonshot-v1-128k` | Research with Moonshot native $web_search integration |

### Recommended: Perplexity sonar-reasoning-pro

For deep research, `perplexity/sonar-reasoning-pro` provides the best results. It uses chain-of-thought reasoning with iterative web search to build comprehensive answers.

```json5
{
  tools: {
    web: {
      search: {
        provider: "perplexity",
        perplexity: {
          apiKey: "pplx-...",
          model: "perplexity/sonar-reasoning-pro",
        },
      },
    },
  },
}
```

## How to use deep research

### Via agent conversation

Ask the agent to research a topic. The agent uses `web_search` and `web_fetch` to gather information:

```
You: Research how other self-hosted AI gateways handle multi-channel routing
     and compare their approaches with OpenClaw's implementation.

Agent: I'll research this by searching for information about self-hosted AI
       gateway architectures and multi-channel routing patterns...
       [uses web_search multiple times, reads sources with web_fetch]
       
       Here's what I found: [comprehensive answer with citations]
```

### Via CLI

Send a research question directly:

```bash
openclaw message send "Research the latest developments in WebSocket
  protocol optimization for real-time AI agent communication.
  Include benchmarks and implementation patterns."
```

### Combining tools for deeper research

For the most thorough research, the agent combines multiple tools:

1. **web_search** — Initial queries to find relevant sources
2. **web_fetch** — Read full pages from the most promising results
3. **web_search** (again) — Follow-up queries to fill gaps
4. **Browser tool** — For JavaScript-heavy sites that `web_fetch` cannot parse

Enable all web tools in config:

```json5
{
  tools: {
    web: {
      search: { enabled: true },
      fetch: { enabled: true },
    },
    browser: { enabled: true },
  },
}
```

## Optimizing research quality

### Use specific, detailed prompts

Vague prompts produce shallow research. Be specific about what you need:

```
// ❌ Vague
"Tell me about WhatsApp bots"

// ✅ Specific
"Compare the authentication methods used by the top 5 WhatsApp Business API
 providers. Include OAuth flow details, token refresh patterns, and rate
 limits for each. Focus on self-hosted solutions."
```

### Request citations

Ask the agent to include sources:

```
"Research X and include citations for each claim with URLs."
```

### Set scope boundaries

Help the agent focus by specifying what to include and exclude:

```
"Research WebSocket scaling patterns for AI agents. Focus on:
 - Connection pooling strategies
 - Message compression techniques
 - Heartbeat and reconnection patterns
 Exclude: browser WebSocket client libraries"
```

### Use freshness filters

For time-sensitive research, use the `freshness` parameter:

```json5
// Only results from the past week
{ query: "AI agent frameworks 2026", freshness: "pw" }

// Only results from the past month
{ query: "LLM context window improvements", freshness: "pm" }
```

## Research with local documentation

OpenClaw can also search its own documentation via the memory search system:

- **`memory_search`** — Semantic search over indexed workspace documents
- **`openclaw docs <query>`** — Search the live docs.openclaw.ai index

Combine local documentation search with web research for the most complete answers — the agent can verify web findings against local docs, or use local docs as a starting point for web research.

## Troubleshooting

### Research results are shallow

- Switch to `sonar-reasoning-pro` for deeper chain-of-thought research
- Use more specific prompts with explicit scope
- Increase `maxResults` in search config for more source coverage

### Citations are missing or inaccurate

- Use Perplexity or Gemini providers (they return native citations)
- With Brave Search, the agent synthesizes its own citations — quality depends on the model
- Ask explicitly: "Include the source URL for each claim"

### Research is slow

- `sonar-reasoning-pro` is slower but more thorough than `sonar-pro`
- Increase `timeoutSeconds` in search config for complex queries
- Use `cacheTtlMinutes` to avoid re-fetching the same sources

### Pages fail to load with web_fetch

- Some sites block automated fetching — try the Browser tool instead
- Configure Firecrawl fallback for better extraction on complex sites
- Check `tools.web.fetch.maxResponseBytes` if pages are very large

## Related

- [Web tools](/tools/web) — Full web_search and web_fetch configuration reference
- [Browser tool](/tools/browser) — Full web browser automation for JavaScript-heavy sites
- [AI discoverability](/reference/ai-discoverability) — How to write documentation that AI deep research tools can find and use effectively
- [Memory](/concepts/memory) — Local documentation search via the memory system
