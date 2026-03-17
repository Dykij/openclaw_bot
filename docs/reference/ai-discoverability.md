---
summary: "How to optimize OpenClaw documentation for AI search, deep research, and LLM discoverability"
read_when:
  - You want to improve documentation readability for AI models
  - You are working on documentation SEO or AI discoverability
  - You want to understand how AI models search the internet for information
  - You want to improve deep research results for OpenClaw documentation
title: "AI Discoverability"
---

# AI discoverability

This guide covers how AI models discover and consume documentation, and the techniques OpenClaw uses to make its docs findable and readable by both humans and machines.

## How AI models search documentation

Modern AI systems (ChatGPT, Claude, Gemini, Perplexity, Grok) use several methods to find and process documentation when answering user questions:

### Web search and retrieval

1. **Real-time web search** — Models with web search capability (Perplexity Sonar, Grok, ChatGPT with browsing) issue search queries, fetch pages, and synthesize results. They prioritize pages with clear structure, concise answers, and authoritative content.

2. **Large context windows** — Modern models (up to 2M tokens for Gemini, 200K for Claude, 128K for GPT-4o) can ingest entire documentation sets. Structured, well-organized docs perform better in these large-context scenarios.

3. **Document analysis** — Models extract information from HTML, Markdown, and PDFs. Clean semantic structure (headings, lists, code blocks) dramatically improves extraction accuracy vs. cluttered pages with heavy navigation or JavaScript rendering.

4. **Retrieval-Augmented Generation (RAG)** — Many systems pre-index documentation into vector databases and retrieve relevant chunks at inference time. Chunk quality depends on clear paragraph boundaries, descriptive headings, and self-contained sections.

### What makes documentation AI-friendly

| Factor | Impact | How OpenClaw addresses it |
| ------ | ------ | ------------------------- |
| **Clear heading hierarchy** | H1/H2/H3 help models understand document structure | Consistent Markdown heading structure across all docs |
| **Frontmatter metadata** | `summary` and `read_when` fields give models quick context | Present on key docs via YAML frontmatter |
| **Self-contained sections** | Each section should be understandable without reading the whole page | Hub-based organization with focused topic pages |
| **Code examples** | Models need real, working code to generate accurate answers | Code blocks with language tags throughout |
| **Internal linking** | Helps models navigate between related concepts | Hub pages (`/start/hubs`) link to every doc |
| **Concise descriptions** | Brief, accurate descriptions beat marketing copy | Technical-first writing style |
| **Structured data** | JSON-LD, schema.org, `llms.txt` improve machine parsing | `llms.txt` and `llms-full.txt` at docs root |
| **Last-updated dates** | Helps models assess information freshness | YAML frontmatter in key docs |

## OpenClaw AI discoverability features

### llms.txt standard

OpenClaw publishes `llms.txt` at the docs root — a Markdown file that provides AI models with a structured overview of all documentation, including:

- Project description and key links
- Categorized documentation map with URLs and descriptions
- Section hierarchy matching the docs navigation

The companion `llms-full.txt` provides expanded descriptions of every major feature, architecture component, and integration.

**How AI models use llms.txt:**

- At inference time, AI agents fetch `llms.txt` before crawling documentation
- The file provides a curated map of available resources
- Reduces noise from navigation elements, ads, and non-content HTML
- Improves citation accuracy and answer relevance

### Documentation frontmatter

Key documentation pages include YAML frontmatter with machine-readable metadata:

```yaml
---
summary: "Brief description of what this page covers"
read_when:
  - Context hint for when to read this page
  - Another context hint
title: "Page Title"
---
```

The `summary` field gives AI models a quick overview without parsing the full page. The `read_when` field helps AI agents decide whether a page is relevant to a specific query.

### RAG ingestion pipeline

OpenClaw includes a documentation ingestion pipeline (`scripts/doc_ingester.py`) that:

1. Downloads documentation pages from configured URLs
2. Strips navigation, scripts, and styling
3. Converts clean HTML to LLM-readable Markdown
4. Splits into context-friendly chunks (~1500 tokens)
5. Saves chunks with metadata for vector search

This pipeline powers the memory search system, enabling the agent to search its own documentation at runtime.

### Documentation search

The `openclaw docs <query>` CLI command searches the live documentation index via the Mintlify search API, providing terminal-accessible documentation lookup. Internally, the search uses the `SearchOpenClaw` MCP tool.

## Best practices for documentation contributors

When writing or editing OpenClaw documentation, follow these guidelines to maximize AI discoverability:

### Structure

- **Use descriptive headings** — Write headings that clearly state what the section covers. Prefer "How to configure Telegram" over "Setup".
- **One topic per page** — Keep pages focused on a single topic. Split large guides into linked sub-pages.
- **Add frontmatter** — Every new doc should include `summary` and `read_when` fields.
- **Link related docs** — Use internal links to connect related concepts. The hub page (`/start/hubs`) should reference every new page.

### Content

- **Lead with the answer** — Put the most important information first. AI models often truncate context, so key facts should appear early.
- **Use code blocks with language tags** — Always specify the language (` ```typescript `, ` ```bash `, etc.) for syntax highlighting and model comprehension.
- **Avoid ambiguous pronouns** — Write "the Gateway" instead of "it" when context might be unclear to a model processing a document chunk.
- **Include examples** — Real, working examples are more valuable than abstract descriptions.
- **Keep sections self-contained** — Each H2 section should be understandable without reading the rest of the page, since RAG systems may retrieve individual sections.

### Metadata

- **Write accurate summaries** — The `summary` field should be a single sentence that accurately describes the page content. This is the most important field for AI discoverability.
- **Provide specific read_when hints** — Help AI agents decide when to recommend this page. Use specific scenarios, not vague descriptions.
- **Update last-modified dates** — When making significant changes, update the frontmatter to reflect the modification date.

### Search optimization

- **Use the terminology your users search for** — Include common variations and synonyms. If users search for "WhatsApp bot", make sure that phrase appears in the WhatsApp docs.
- **Add a FAQ section to complex pages** — FAQ-style content matches how both humans and AI models phrase questions.
- **Avoid decorative HTML** — Stick to Markdown. HTML components (Mintlify cards, columns) are fine for navigation but should not contain critical information that AI models need to index.

## Comparison: AI deep research tools

Different AI models have different strengths for researching OpenClaw documentation:

| Model | Best for | Notes |
| ----- | -------- | ----- |
| **Perplexity Sonar** | Real-time web search with citations | Built-in web search, `sonar-reasoning-pro` for deep research |
| **Claude** | Precise extraction from long docs | Large context window, low hallucination rate on technical content |
| **ChatGPT** | Broad research with reasoning | Good at synthesizing multiple sources, strong citation format |
| **Gemini** | Massive document analysis | 2M token context, multimodal (can process screenshots/diagrams) |
| **Grok** | Real-time information | Real-time web access via xAI |

### OpenClaw web search integration

OpenClaw itself provides web search capabilities through:

- **Perplexity provider** with Sonar models for deep research
- **web_search tool** for agent-initiated internet searches
- **web_fetch tool** for page retrieval and parsing
- **Browser tool** for full web automation

Configure web search in `openclaw config set tools.web_search.enabled true`.

## Measuring discoverability

To assess how well OpenClaw docs perform in AI search:

1. **Test with AI models** — Ask ChatGPT, Claude, Perplexity, and Gemini questions about OpenClaw. Check if answers are accurate and cite the correct docs.
2. **Check llms.txt** — Ensure `llms.txt` is accessible at `https://docs.openclaw.ai/llms.txt` and accurately reflects current documentation.
3. **Audit frontmatter** — Run `node scripts/docs-list.js` to check which docs have proper `summary` and `read_when` metadata.
4. **Monitor search quality** — Use `openclaw docs <query>` to test the built-in search and verify results match expectations.
5. **Review link integrity** — Run `node scripts/docs-link-audit.mjs` to check for broken internal links that would degrade AI navigation.
