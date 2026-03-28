# BRAIN (Live Working Memory)

## Current Architecture (v2 — MAS + OpenRouter Primary)

- **Primary LLM Provider:** OpenRouter API (cloud, multi-model routing)
- **Fallback LLM Provider:** vLLM v0.17.1 (WSL2, local GPU) — used when OpenRouter is rate-limited or unavailable
- **Orchestration:** Multi-Agent System (MAS) — autonomous agent lifecycle with AgentOrchestrator
- **Memory:** SuperMemory (RAG + TieredMemory + EpisodicMemory + ChromaDB) — persistent cross-session context
- **Integration:** ClawHub platform connector for skills/tasks marketplace

## Active Components

- **AgentOrchestrator** (`src/mas/orchestrator.py`): manages agent lifecycle, task routing, autonomous loop
- **OpenRouter Client** (`src/openrouter_client.py`): primary cloud inference with rate-limit tracking, auto-fallback to vLLM
- **Unified LLM Gateway** (`src/llm_gateway.py`): single entry point `route_llm()` for all inference — SmartModelRouter, TokenBudget, Metrics, Circuit Breaker
- **SmartModelRouter** (`src/ai/inference/router.py`): tier-based routing (fast/balanced/premium/reasoning) per task type — replaces legacy ModelSelector
- **SuperMemory** (`src/supermemory.py`): unified RAG + tiered memory (hot/warm/cold) + episodic recall + SQLite persistence + decay scheduling
- **Multi-Source Parser** (`src/parsers/`): Habr, Reddit, GitHub content ingestion
- **DeepResearch v3** (`src/deep_research.py`): multi-perspective iterative research with adaptive stopping
- **ClawHub integration** (`src/clawhub/`): connector to ClawHub platform API
- **Pipeline Executor** (`src/pipeline_executor.py`): Chain-of-Agents (20 roles across 2 brigades)
- **Safety Stack:** PromptInjectionDefender (5-layer), HallucinationDetector, CodeValidator, AutoRollback

## Recent Changes (2026-03-28 — v12.0-ASCENDED):

- **Knowledge Ascension v12.0**: Deep ingestion of Python 3.14 and Rust 2024 Edition standards
- **KnowledgeStore** (`src/memory/knowledge_store.py`): Structured knowledge base with 23 entries — 13 Python 3.14 (PEP 649, 734, 750, 758, 765, 768, 784, asyncio, free-threading) + 10 Rust 2024 (RPIT, unsafe extern, gen keyword, never type, IntoIterator for Box)
- **Enriched Graph-RAG**: `DependencyGraphEngine.get_enriched_context()` auto-injects language-aware knowledge into RAG context
- **Skills JSON** (`src/ai/agents/special_skills.json`): 16 best-practice patterns with `STANDARD_LIBRARY_PY314` and `RUST_STABLE_2026` tags for FeedbackLoopEngine

## Recent Changes (2026-03-25):

- Transitioned to OpenRouter as primary LLM provider (vLLM → fallback only)
- Implemented MAS (Multi-Agent System) orchestrator for autonomous agent lifecycle
- Created SuperMemory system (RAG + TieredMemory fusion with cross-session persistence)
- Added ClawHub platform integration module
- Added multi-source parsers: Habr, Reddit, GitHub
- Enhanced DeepResearch v3 with OpenRouter multi-model support
- Updated Dockerfile and docker-compose.yml for new architecture

## Previous State (archived):

- vLLM-only inference with N-gram speculative decoding + enforce-eager
- Context Bridge (3-layer: Summary→SQLite→ChromaDB) for Qwen↔DeepSeek swaps
- Hardware: RTX 5060 Ti 16GB, VRAM 97%, gpu_memory_utilization=0.92

## Models (OpenRouter Primary):

- **fast_free:** arcee-ai/trinity-mini:free, stepfun/step-3.5-flash:free
- **balanced:** nvidia/nemotron-3-super-120b-a12b:free
- **premium:** deepseek/deepseek-chat-v3-0324:free, qwen/qwen-2.5-coder-32b-instruct:free
- **reasoning:** deepseek/deepseek-r1:free
- **local fallback:** Qwen/Qwen2.5-Coder-14B-Instruct-AWQ (vLLM)

## Hardware:

- RTX 5060 Ti 16GB (fallback vLLM inference)
- Context Bridge: SQLite fact store (data/context_bridge.db) + ChromaDB embeddings
- SuperMemory persistence: data/supermemory/
