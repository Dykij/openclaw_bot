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

This guide covers how AI models discover and consume documentation, and the techniques OpenClaw uses to make its docs findable and readable by both humans and machines. It also explains how deep research tools work and how to optimize documentation for them.

## How AI models search for information

Modern AI systems use a multi-stage pipeline to find, retrieve, and synthesize information from documentation and the internet. Understanding this pipeline is key to writing documentation that AI models can discover and use accurately.

### Stage 1: Query formulation

When a user asks a question, the AI model first decomposes it into search-friendly sub-queries. For example, "How do I set up WhatsApp with OpenClaw on Docker?" might become:

1. "OpenClaw WhatsApp channel setup"
2. "OpenClaw Docker installation"
3. "OpenClaw WhatsApp configuration"

**Documentation impact:** Pages with clear, search-friendly headings and terminology matching common user queries will rank higher in this stage.

### Stage 2: Source discovery

AI models discover sources through several mechanisms:

1. **Real-time web search** — Models with web search capability (Perplexity Sonar, Grok, ChatGPT with browsing, Gemini with Google Search grounding) issue search queries to web search APIs, fetch the top results, and extract content. They prioritize pages with clear structure, concise answers, and authoritative domain signals.

2. **Pre-trained knowledge** — Models trained on crawled web data have baseline knowledge of documentation that was public at training time. This knowledge degrades with time as documentation evolves.

3. **llms.txt standard** — AI agents increasingly check `llms.txt` at the documentation root for a curated, structured map of all available content before crawling individual pages. This reduces noise from navigation elements and improves accuracy.

4. **Retrieval-Augmented Generation (RAG)** — Many systems pre-index documentation into vector databases and retrieve relevant chunks at inference time. Chunk quality depends on clear paragraph boundaries, descriptive headings, and self-contained sections.

### Stage 3: Content extraction

Once sources are found, models extract useful content:

1. **HTML parsing** — Models strip navigation, ads, footers, and scripts to isolate main content. Clean semantic HTML with `<main>`, `<article>`, and proper heading hierarchy (`h1` > `h2` > `h3`) extracts cleanly.

2. **Markdown processing** — Native Markdown (used in `llms.txt` and raw doc files) is the most reliable format for AI extraction because it has no rendering ambiguity.

3. **Large context ingestion** — Modern models (up to 2M tokens for Gemini, 200K for Claude, 128K for GPT-4o) can ingest entire documentation sets. Well-organized docs with clear section boundaries perform better in these large-context scenarios.

4. **Chunk retrieval** — RAG systems retrieve specific text chunks (typically 400-1500 tokens) based on embedding similarity. Each chunk should be self-contained enough to be useful without its surrounding context.

### Stage 4: Synthesis and citation

Models combine extracted information into a coherent answer:

1. **Cross-referencing** — Models compare information across multiple pages to verify accuracy. Internally consistent documentation with clear cross-links produces more confident answers.

2. **Citation generation** — Models link back to source URLs. Pages with unique, descriptive titles and stable URLs get cited more accurately.

3. **Confidence assessment** — Models assign higher confidence to information found in multiple authoritative sources with consistent formatting and recent update dates.

### What makes documentation AI-friendly

| Factor | Impact | How OpenClaw addresses it |
| ------ | ------ | ------------------------- |
| **Clear heading hierarchy** | H1/H2/H3 help models understand document structure and navigate content | Consistent Markdown heading structure across all 650+ docs |
| **Frontmatter metadata** | `summary` and `read_when` fields give models quick context without full parsing | Present on all English docs via YAML frontmatter |
| **Self-contained sections** | Each section understandable in isolation (critical for RAG chunk retrieval) | Hub-based organization with focused, single-topic pages |
| **Code examples with language tags** | Models need real, working code to generate accurate answers | Fenced code blocks with language identifiers throughout |
| **Internal cross-linking** | Helps models navigate between related concepts and verify information | Hub page (`/start/hubs`) links to every doc; pages cross-reference related topics |
| **Concise, technical descriptions** | Brief, accurate descriptions beat marketing copy for search relevance | Technical-first writing style with answer-first paragraphs |
| **Structured data files** | `llms.txt`, `llms-full.txt` improve machine parsing and source discovery | Published at docs root with categorized URL maps |
| **Stable URLs with redirects** | Prevents broken citations in cached model knowledge | 190+ URL redirects in docs.json for backward compatibility |
| **FAQ sections** | Match natural question patterns used by both humans and AI models | FAQ-style sections on complex topic pages |

## How deep research works

Deep research is a multi-step process where AI models conduct extended internet research to answer complex questions. Unlike single-query web search, deep research involves iterative query refinement, source evaluation, and synthesis.

### Deep research pipeline

```
User question
  → Query decomposition (break into sub-questions)
  → Parallel web searches (5-20 queries)
  → Source evaluation and filtering
  → Content extraction and reading
  → Cross-reference and fact-checking
  → Iterative refinement (search for gaps)
  → Synthesis with citations
  → Final answer
```

### How deep research differs from web search

| Aspect | Single web search | Deep research |
| ------ | ----------------- | ------------- |
| **Queries** | 1 search query | 5-20+ iterative queries |
| **Sources** | Top 5-10 results | 20-50+ sources evaluated |
| **Depth** | Surface-level answers | Multi-page analysis with cross-referencing |
| **Time** | Seconds | Minutes (30s to 5+ minutes) |
| **Reasoning** | Direct extraction | Chain-of-thought analysis, gap identification |
| **Citations** | Basic URL references | Inline citations with relevance scoring |

### What documentation needs for deep research

Deep research tools perform best when documentation provides:

1. **Exhaustive topic coverage** — Deep research iterates until it finds comprehensive answers. Pages that thoroughly cover a topic (including edge cases, troubleshooting, and examples) satisfy queries in fewer iterations.

2. **Clear information hierarchy** — Deep research tools navigate from overview pages to detail pages. A clear hierarchy (hub → topic overview → detailed guide → reference) matches how these tools explore.

3. **Unique, descriptive page titles** — Each page title should uniquely identify its content. Deep research tools use titles to decide which pages to read in full vs. skip.

4. **Cross-linked related pages** — When deep research finds a partial answer on one page, it follows links to related pages for completeness. Strong internal linking improves synthesis quality.

5. **Machine-readable metadata** — `llms.txt`, frontmatter `summary` fields, and structured headings help deep research tools quickly triage which pages contain relevant information before committing to full extraction.

6. **Consistent terminology** — Deep research tools issue multiple related queries. Using consistent terminology (e.g., always "Gateway" not sometimes "server" or "daemon") ensures all queries find the same authoritative content.

7. **Dated content** — Timestamps help deep research tools prioritize recent information and flag potentially outdated content.

## OpenClaw AI discoverability features

### llms.txt standard

OpenClaw publishes `llms.txt` at the docs root — a Markdown file that provides AI models with a structured overview of all documentation, including:

- Project description and key links
- Categorized documentation map with URLs and short descriptions
- Section hierarchy matching the docs navigation

The companion `llms-full.txt` provides expanded descriptions of every major feature, architecture component, and integration — designed for deep research tools that benefit from rich context.

**How AI models use llms.txt:**

- At inference time, AI agents fetch `llms.txt` before crawling individual pages
- The file provides a curated map of available resources, organized by topic
- Reduces noise from navigation elements, ads, and non-content HTML
- Improves citation accuracy and answer relevance
- Deep research tools use `llms-full.txt` for initial context before issuing follow-up queries

### Documentation frontmatter

All English documentation pages include YAML frontmatter with machine-readable metadata:

```yaml
---
summary: "Brief description of what this page covers"
read_when:
  - Context hint for when to read this page
  - Another context hint
title: "Page Title"
---
```

- **`summary`** — Gives AI models a quick overview without parsing the full page. This is the single most important field for AI discoverability.
- **`read_when`** — Helps AI agents decide whether a page is relevant to a specific query scenario.
- **`title`** — Provides a clean page title independent of the Markdown H1 heading.

Run `node scripts/docs-list.js` to audit frontmatter coverage across all docs.

### RAG ingestion pipeline

OpenClaw includes a documentation ingestion pipeline (`scripts/doc_ingester.py`) that:

1. Downloads documentation pages from configured URLs
2. Strips navigation, scripts, and styling via BeautifulSoup
3. Converts clean HTML to LLM-readable Markdown via markdownify
4. Splits into context-friendly chunks (~1500 tokens with paragraph-boundary overlap)
5. Saves chunks with metadata (source URL, chunk index, content hash, timestamp) for vector search

This pipeline powers the memory search system, enabling the agent to search its own documentation and external references at runtime.

### Documentation search

The `openclaw docs <query>` CLI command searches the live documentation index via the Mintlify search API, providing terminal-accessible documentation lookup. Internally, the search uses the `SearchOpenClaw` MCP tool.

### Hub-based navigation

The [Docs hubs page](/start/hubs) provides a complete, categorized map of every documentation page. This structure is critical for both human and AI navigation:

- **For humans**: Organized by use case with clear section headings
- **For AI models**: A single page with links to every doc, enabling efficient crawling
- **For deep research**: Provides topic hierarchy that maps to natural query decomposition

## Best practices for documentation contributors

When writing or editing OpenClaw documentation, follow these guidelines to maximize readability for both humans and AI models:

### Structure

- **Use descriptive headings** — Write headings that clearly state what the section covers. Prefer "How to configure Telegram" over "Setup".
- **One topic per page** — Keep pages focused on a single topic. Split large guides into linked sub-pages.
- **Add frontmatter** — Every new doc must include `summary`, `read_when`, and `title` fields.
- **Link related docs** — Use internal links to connect related concepts. The hub page (`/start/hubs`) should reference every new page.
- **Answer-first paragraphs** — Start each section with the key fact or answer, then provide context and details. This matches how AI models prioritize information at the start of a section.

### Content

- **Lead with the answer** — Put the most important information first. AI models often truncate context, so key facts should appear early in each section.
- **Use code blocks with language tags** — Always specify the language (` ```typescript `, ` ```bash `, etc.) for syntax highlighting and model comprehension.
- **Avoid ambiguous pronouns** — Write "the Gateway" instead of "it" when context might be unclear to a model processing an isolated document chunk.
- **Include working examples** — Real, working examples are more valuable than abstract descriptions. Models use examples to verify their understanding.
- **Keep sections self-contained** — Each H2 section should be understandable without reading the rest of the page, since RAG systems may retrieve individual sections in isolation.
- **Use tables for comparisons** — Tables are parsed more reliably than prose when comparing features, options, or configurations.
- **Include troubleshooting sections** — "Common errors" and "FAQ" sections on complex pages match how both humans and AI models phrase questions.

### Metadata

- **Write accurate summaries** — The `summary` field should be a single sentence that accurately describes the page content. This is the most important field for AI discoverability.
- **Provide specific read_when hints** — Help AI agents decide when to recommend this page. Use specific scenarios (e.g., "Setting up WhatsApp for the first time") not vague descriptions (e.g., "WhatsApp stuff").
- **Update last-modified dates** — When making significant changes, update the frontmatter to reflect the modification date.

### Search and deep research optimization

- **Use the terminology your users search for** — Include common variations and synonyms. If users search for "WhatsApp bot", make sure that phrase appears in the WhatsApp docs.
- **Add FAQ sections to complex pages** — FAQ-style content matches how both humans and AI models phrase questions, and deep research tools specifically look for Q&A patterns.
- **Avoid decorative HTML** — Stick to Markdown. HTML components (Mintlify cards, columns) are fine for navigation but should not contain critical information that AI models need to index.
- **Write for chunk retrieval** — Each paragraph should ideally contain one complete thought. Avoid paragraphs that start mid-thought from a previous paragraph, since RAG systems may retrieve them in isolation.
- **Include entity definitions** — When introducing a concept (like "Gateway", "Node", or "Session"), define it explicitly on its main page. Deep research tools use these definitions for context across multiple queries.

## Comparison: AI deep research tools

Different AI models have different strengths when researching OpenClaw documentation. Understanding their behavior helps optimize documentation for each.

### Tool comparison

| Model | Best for | Search method | Context window | Citation style |
| ----- | -------- | ------------- | -------------- | -------------- |
| **Perplexity Sonar** | Real-time web search with citations | Native web search API | 127K | Inline numbered references |
| **Perplexity sonar-reasoning-pro** | Complex multi-step research | Iterative web search + CoT | 127K | Inline with reasoning trace |
| **Claude** | Precise extraction from long docs | Document analysis (no native search) | 200K | Verbatim quotes with context |
| **ChatGPT (Deep Research)** | Broad multi-source synthesis | Bing + browsing agent | 128K | Numbered footnotes with URLs |
| **Gemini (Deep Research)** | Massive document analysis | Google Search grounding | 2M | Inline with source cards |
| **Grok** | Real-time information | Native X/web search | 128K | Inline URL references |

### How each tool finds OpenClaw documentation

**Perplexity Sonar** searches the web in real-time and synthesizes answers with citations. It reads `llms.txt` if directed to the docs site and follows internal links for comprehensive coverage. Best results come from pages with clear H2 sections and concise answers near the top.

**Claude** does not have native web search but excels at analyzing documents provided in its context window. It benefits most from `llms-full.txt` (which provides the full documentation overview in a single file) and from well-structured pages with clear heading hierarchies.

**ChatGPT Deep Research** uses an autonomous browsing agent that opens multiple pages, reads them in full, and synthesizes findings. It follows links aggressively, so strong internal cross-linking between pages improves results. FAQ sections and troubleshooting pages are particularly effective.

**Gemini Deep Research** leverages Google Search grounding and can process extremely long documents (up to 2M tokens). It works well with comprehensive single-page references and benefits from structured data that Google can index.

**Grok** combines real-time web search with X (Twitter) data. It finds OpenClaw content through standard web search and benefits from pages with concise, factual content and clear code examples.

### OpenClaw web search integration

OpenClaw provides web search capabilities through multiple providers, enabling the agent itself to perform deep research:

- **Perplexity provider** with Sonar models for AI-synthesized web search answers with citations
- **Gemini provider** with Google Search grounding for Google-backed answers
- **Grok provider** for real-time web access via xAI
- **Brave Search** for traditional structured web search results
- **Kimi provider** for web search via Moonshot native $web_search
- **web_fetch tool** for direct page retrieval and readable content extraction
- **Browser tool** for full web automation on JavaScript-heavy sites

See [Web tools](/tools/web) for setup instructions and [Deep research](/tools/deep-research) for research-specific usage patterns.

## Measuring discoverability

To assess how well OpenClaw docs perform in AI search:

1. **Test with AI models** — Ask ChatGPT, Claude, Perplexity, and Gemini questions about OpenClaw. Check if answers are accurate and cite the correct docs.
2. **Check llms.txt** — Ensure `llms.txt` is accessible at `https://docs.openclaw.ai/llms.txt` and accurately reflects current documentation.
3. **Audit frontmatter** — Run `node scripts/docs-list.js` to check which docs have proper `summary` and `read_when` metadata. Target: zero docs without frontmatter in English.
4. **Monitor search quality** — Use `openclaw docs <query>` to test the built-in search and verify results match expectations.
5. **Review link integrity** — Run `node scripts/docs-link-audit.mjs` to check for broken internal links that would degrade AI navigation.
6. **Test deep research** — Use Perplexity Deep Research or ChatGPT Deep Research to ask complex, multi-part questions about OpenClaw. Evaluate whether the answer covers all aspects and cites the right pages.
7. **Compare llms.txt to hubs** — Ensure `llms.txt` and the [Docs hubs](/start/hubs) page are in sync so that both AI models and humans have access to the same complete documentation map.

## Checklist for new documentation pages

Before publishing a new documentation page, verify:

- [ ] YAML frontmatter includes `summary`, `read_when`, and `title`
- [ ] `summary` is a single, accurate sentence describing the page
- [ ] `read_when` lists 2-3 specific scenarios when this page is useful
- [ ] Page is linked from the [Docs hubs](/start/hubs) page
- [ ] Page is referenced in `llms.txt` with a descriptive one-line summary
- [ ] Headings are descriptive and follow H1 > H2 > H3 hierarchy
- [ ] Code blocks have language tags
- [ ] Key concepts are defined explicitly, not assumed
- [ ] Cross-links to related docs are present
- [ ] Run `node scripts/docs-list.js` confirms the page has valid frontmatter
