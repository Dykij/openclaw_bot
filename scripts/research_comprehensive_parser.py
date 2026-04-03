#!/usr/bin/env python3
"""
Comprehensive Research Parser — Multi-category parser for OpenClaw bot improvements.

Fetches research papers and articles from multiple academic sources across
10 improvement categories for OpenClaw bot.

Categories (3 topics each = 36 total queries):
  1. Архитектура и инфраструктура (Architecture & Infrastructure)
  2. Интеллектуальные модули (Intelligent Modules)
  3. Системы памяти (Memory Systems)
  4. Deep Research
  5. Безопасность (Safety & Security)
  6. Производительность (Performance & Optimization)
  7. Пайплайны (Pipelines & Orchestration)
  8. Тестирование (Testing & Evaluation)
  9. Обучение моделей (Model Training)
  10. OpenClaw общее (General Agent Systems)
  11. Интеграция с Obsidian (Obsidian Integration)
  12. Улучшение моделей OpenRouter (OpenRouter Model Optimization)

Sources: Semantic Scholar, arXiv, Papers With Code, HuggingFace Papers

Usage:
    python scripts/research_comprehensive_parser.py [--limit 30] [--dry-run]
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Output directory
BASE_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "analysis", "research")

# ============================================================
# 10 categories × 3 topics = 30 research queries
# ============================================================
RESEARCH_CATEGORIES: Dict[str, Dict[str, List[str]]] = {
    "architecture": {
        "name_ru": "Архитектура и инфраструктура",
        "name_en": "Architecture & Infrastructure",
        "topics": [
            "microservice architecture LLM agent systems",
            "cloud-native AI deployment serverless inference",
            "event-driven architecture autonomous agents",
        ],
    },
    "intelligent_modules": {
        "name_ru": "Интеллектуальные модули",
        "name_en": "Intelligent Modules",
        "topics": [
            "mixture of agents multi-perspective generation",
            "ReAct reasoning acting language models",
            "constitutional AI self-improvement alignment",
        ],
    },
    "memory_systems": {
        "name_ru": "Системы памяти",
        "name_en": "Memory Systems",
        "topics": [
            "memory augmented language models long-term",
            "episodic memory retrieval augmented generation",
            "tiered memory management context compression LLM",
        ],
    },
    "deep_research": {
        "name_ru": "Deep Research",
        "name_en": "Deep Research & Information Retrieval",
        "topics": [
            "deep research agent web search synthesis",
            "evidence-based reasoning fact verification LLM",
            "multi-source information retrieval knowledge synthesis",
        ],
    },
    "safety": {
        "name_ru": "Безопасность",
        "name_en": "Safety & Security",
        "topics": [
            "hallucination detection mitigation language models",
            "prompt injection defense LLM security",
            "AI safety guardrails truthfulness evaluation",
        ],
    },
    "performance": {
        "name_ru": "Производительность",
        "name_en": "Performance & Optimization",
        "topics": [
            "speculative decoding inference acceleration LLM",
            "model quantization efficient inference deployment",
            "token budget optimization adaptive computation",
        ],
    },
    "pipelines": {
        "name_ru": "Пайплайны и оркестрация",
        "name_en": "Pipelines & Orchestration",
        "topics": [
            "chain-of-agents pipeline orchestration",
            "agentic workflow planning execution LLM",
            "tool-augmented language model pipeline",
        ],
    },
    "testing": {
        "name_ru": "Тестирование и оценка",
        "name_en": "Testing & Evaluation",
        "topics": [
            "LLM evaluation benchmark testing methodology",
            "automated testing AI agent systems",
            "adversarial testing robustness language models",
        ],
    },
    "model_training": {
        "name_ru": "Обучение моделей",
        "name_en": "Model Training",
        "topics": [
            "GRPO group relative policy optimization training",
            "reinforcement learning verifiable rewards LLM",
            "LoRA fine-tuning small language models efficient",
        ],
    },
    "general_agents": {
        "name_ru": "Агентные системы (OpenClaw общее)",
        "name_en": "General Agent Systems",
        "topics": [
            "autonomous AI agent system design",
            "multi-agent collaboration task decomposition",
            "self-improving AI agent continuous learning",
        ],
    },
    "obsidian_integration": {
        "name_ru": "Интеграция с Obsidian",
        "name_en": "Obsidian Integration & Knowledge Management",
        "topics": [
            "knowledge management personal knowledge base AI",
            "note-taking retrieval augmented generation LLM",
            "Zettelkasten knowledge graph linked notes AI",
        ],
    },
    "openrouter_models": {
        "name_ru": "Улучшение моделей OpenRouter",
        "name_en": "OpenRouter Model Optimization",
        "topics": [
            "LLM model routing selection optimization API",
            "multi-model ensemble routing inference cost",
            "model evaluation comparison benchmark selection",
        ],
    },
}

# GitHub repositories relevant to OpenClaw training
GITHUB_REPOS: List[Dict[str, str]] = [
    # RL Training Frameworks
    {"name": "huggingface/trl", "stars": "17.9k", "desc": "Train transformer language models with reinforcement learning (PPO, GRPO, DPO)", "category": "model_training"},
    {"name": "OpenRLHF/OpenRLHF", "stars": "9.3k", "desc": "Scalable Agentic RL Framework (PPO, DAPO, REINFORCE++, Ray, vLLM)", "category": "model_training"},
    {"name": "verl-project/verl", "stars": "20.4k", "desc": "Volcano Engine Reinforcement Learning for LLMs", "category": "model_training"},
    {"name": "rllm-org/rllm", "stars": "5.4k", "desc": "Democratizing Reinforcement Learning for LLMs (SWE-agent, coding agent)", "category": "model_training"},
    {"name": "TsinghuaC3I/MARTI", "stars": "472", "desc": "LLM-based Multi-Agent Reinforced Training and Inference", "category": "model_training"},
    {"name": "TIGER-AI-Lab/verl-tool", "stars": "942", "desc": "verl version supporting diverse tool use RL training", "category": "model_training"},
    {"name": "unslothai/notebooks", "stars": "5.1k", "desc": "250+ Fine-tuning & RL Notebooks (text, vision, audio, embedding, TTS)", "category": "model_training"},
    {"name": "0xZee/DeepSeek-R1-FineTuning", "stars": "18", "desc": "Fine-tuning DeepSeek-style reasoning models with RL + Quantization", "category": "model_training"},
    # Inference Optimization
    {"name": "vllm-project/vllm", "stars": "75.1k", "desc": "High-throughput memory-efficient inference and serving engine for LLMs", "category": "performance"},
    {"name": "NVIDIA/Model-Optimizer", "stars": "2.3k", "desc": "SOTA model optimization: quantization, pruning, distillation, speculative decoding", "category": "performance"},
    {"name": "kvcache-ai/Mooncake", "stars": "5k", "desc": "KV-cache disaggregated serving platform (Kimi)", "category": "performance"},
    # Agent Frameworks
    {"name": "bytedance/deer-flow", "stars": "57.1k", "desc": "Long-horizon SuperAgent: research, code, create with memory + tools", "category": "general_agents"},
    {"name": "run-llama/llama_index", "stars": "48.3k", "desc": "Leading document agent and OCR platform (RAG, fine-tuning, agents)", "category": "pipelines"},
    {"name": "run-llama/rags", "stars": "6.5k", "desc": "Build ChatGPT over your data with natural language (RAG)", "category": "deep_research"},
    # Deep Research
    {"name": "Kashif-E/Delve", "stars": "8", "desc": "AI deep research agent with multi-agent pipeline + persistent memory + RAG", "category": "deep_research"},
    # Training Techniques
    {"name": "sinanuozdemir/oreilly-llm-rl-alignment", "stars": "59", "desc": "RLHF, RLAIF, Reasoning LLMs training course with GRPO examples", "category": "model_training"},
    {"name": "TideDra/lmm-r1", "stars": "845", "desc": "Extend OpenRLHF for multimodal RL training (DeepSeek-R1)", "category": "model_training"},
    # Inference Optimization Labs
    {"name": "ss4983/llm-inference-optimization-lab", "stars": "0", "desc": "Benchmark vLLM vs TGI: quantization, prefix caching, speculative decoding", "category": "performance"},
    # Obsidian + AI Integration
    {"name": "khoj-ai/khoj", "stars": "33.8k", "desc": "AI second brain: self-hostable agents, deep research, RAG with Obsidian", "category": "obsidian_integration"},
    {"name": "nhaouari/obsidian-textgenerator-plugin", "stars": "1.9k", "desc": "Text generation in Obsidian via OpenAI, Anthropic, local models", "category": "obsidian_integration"},
    {"name": "your-papa/obsidian-Smart2Brain", "stars": "1k", "desc": "Privacy-focused AI assistant for Obsidian with RAG + embeddings", "category": "obsidian_integration"},
    {"name": "eugeneyan/obsidian-copilot", "stars": "559", "desc": "AI copilot for writing and thinking in Obsidian with RAG", "category": "obsidian_integration"},
    {"name": "qgrail/obsidian-ai-assistant", "stars": "366", "desc": "AI Assistant Plugin for Obsidian (multi-provider)", "category": "obsidian_integration"},
    {"name": "Roasbeef/obsidian-claude-code", "stars": "196", "desc": "Claude AI assistant embedded directly in Obsidian vault", "category": "obsidian_integration"},
    {"name": "edonyzpc/personal-assistant", "stars": "141", "desc": "AI agents for automatic Obsidian vault management", "category": "obsidian_integration"},
]


# ============================================================
# Data classes
# ============================================================

@dataclass
class ResearchArticle:
    """Represents a research article/paper."""
    title: str
    authors: List[str]
    abstract: str
    url: str
    source: str
    category: str
    category_ru: str
    published: str = ""
    arxiv_id: str = ""
    citations: int = 0
    code_url: str = ""
    relevance_score: float = 0.0
    improvement_summary: str = ""

    def to_markdown(self) -> str:
        """Convert article to markdown format."""
        authors_str = ", ".join(self.authors[:5])
        if len(self.authors) > 5:
            authors_str += f" и ещё {len(self.authors) - 5}"

        md = f"**Авторы:** {authors_str}\n"
        md += f"**Источник:** {self.source}\n"
        md += f"**Категория:** {self.category_ru}\n"
        if self.published:
            md += f"**Дата:** {self.published}\n"
        if self.citations:
            md += f"**Цитирования:** {self.citations}\n"
        md += f"**Ссылка:** <{self.url}>\n"
        if self.arxiv_id:
            md += f"**arXiv:** {self.arxiv_id}\n"
        if self.code_url:
            md += f"**Код:** <{self.code_url}>\n"
        md += f"**Релевантность:** {self.relevance_score:.1f}/10\n"
        md += f"\n{self.abstract[:800]}\n"
        if self.improvement_summary:
            md += f"\n**Применение для OpenClaw:** {self.improvement_summary}\n"
        return md


# ============================================================
# HTTP helpers
# ============================================================

def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> Any:
    """Simple HTTP GET returning JSON."""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "OpenClaw-Research-Parser/2.0 (academic research)")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  ⚠️ HTTP error for {url[:80]}: {e}")
        return None


def _http_get_text(url: str, timeout: int = 30) -> Optional[str]:
    """Simple HTTP GET returning text."""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "OpenClaw-Research-Parser/2.0 (academic research)")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"  ⚠️ HTTP error for {url[:80]}: {e}")
        return None


# ============================================================
# Source parsers
# ============================================================

def fetch_semantic_scholar(topic: str, category: str, category_ru: str, limit: int = 10) -> List[ResearchArticle]:
    """Fetch from Semantic Scholar API."""
    articles = []
    query = urllib.parse.quote(topic)
    url = (
        f"https://api.semanticscholar.org/graph/v1/paper/search"
        f"?query={query}"
        f"&limit={limit}"
        f"&fields=title,authors,abstract,url,year,citationCount,externalIds,openAccessPdf"
        f"&year=2024-2026"
    )

    data = _http_get_json(url)
    if not data or "data" not in data:
        return articles

    for item in data["data"][:limit]:
        if not item.get("abstract"):
            continue
        arxiv_id = ""
        ext_ids = item.get("externalIds") or {}
        if ext_ids.get("ArXiv"):
            arxiv_id = ext_ids["ArXiv"]

        articles.append(ResearchArticle(
            title=item.get("title", ""),
            authors=[a.get("name", "") for a in (item.get("authors") or [])],
            abstract=item.get("abstract", ""),
            url=item.get("url", ""),
            source="Semantic Scholar",
            category=category,
            category_ru=category_ru,
            published=str(item.get("year", "")),
            arxiv_id=arxiv_id,
            citations=item.get("citationCount", 0) or 0,
        ))

    return articles


def fetch_arxiv(topic: str, category: str, category_ru: str, limit: int = 10) -> List[ResearchArticle]:
    """Fetch from arXiv API (Atom XML)."""
    articles = []
    query = urllib.parse.quote(topic)
    url = (
        f"https://export.arxiv.org/api/query"
        f"?search_query=all:{query}"
        f"&sortBy=submittedDate&sortOrder=descending"
        f"&max_results={limit}"
    )

    xml_text = _http_get_text(url)
    if not xml_text:
        return articles

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return articles

    for entry in root.findall("atom:entry", ns)[:limit]:
        title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
        abstract = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")
        published = entry.findtext("atom:published", "", ns)[:10]

        authors = []
        for author in entry.findall("atom:author", ns):
            name = author.findtext("atom:name", "", ns)
            if name:
                authors.append(name)

        entry_id = entry.findtext("atom:id", "", ns)
        arxiv_id = entry_id.split("/abs/")[-1] if "/abs/" in entry_id else ""

        articles.append(ResearchArticle(
            title=title,
            authors=authors,
            abstract=abstract,
            url=entry_id,
            source="arXiv",
            category=category,
            category_ru=category_ru,
            published=published,
            arxiv_id=arxiv_id,
        ))

    return articles


def fetch_papers_with_code(topic: str, category: str, category_ru: str, limit: int = 10) -> List[ResearchArticle]:
    """Fetch from Papers With Code API."""
    articles = []
    query = urllib.parse.quote(topic)
    url = f"https://paperswithcode.com/api/v1/papers/?q={query}&items_per_page={limit}"

    data = _http_get_json(url)
    if not data or "results" not in data:
        return articles

    for item in data["results"][:limit]:
        abstract = item.get("abstract", "") or ""
        if not abstract and not item.get("title"):
            continue

        arxiv_id = item.get("arxiv_id", "") or ""
        paper_url = item.get("url_abs", "") or item.get("url", "")
        if not paper_url and arxiv_id:
            paper_url = f"https://arxiv.org/abs/{arxiv_id}"

        code_url = ""
        proc = item.get("proceeding", "")
        if proc and "github" in str(proc):
            code_url = proc

        articles.append(ResearchArticle(
            title=item.get("title", ""),
            authors=item.get("authors", "").split(", ") if isinstance(item.get("authors"), str) else [],
            abstract=abstract,
            url=paper_url,
            source="Papers With Code",
            category=category,
            category_ru=category_ru,
            published=item.get("published", ""),
            arxiv_id=arxiv_id,
            code_url=code_url,
        ))

    return articles


def fetch_huggingface_papers(topic: str, category: str, category_ru: str, limit: int = 10) -> List[ResearchArticle]:
    """Fetch from HuggingFace Papers API."""
    articles = []
    url = "https://huggingface.co/api/daily_papers"

    data = _http_get_json(url)
    if not data:
        return articles

    topic_words = set(topic.lower().split())

    for item in data[:100]:
        paper = item.get("paper", {})
        title = paper.get("title", "")
        abstract = paper.get("summary", "") or ""

        text = (title + " " + abstract).lower()
        matches = sum(1 for w in topic_words if w in text)
        if matches < 2:
            continue

        authors = [a.get("name", "") for a in paper.get("authors", [])]
        arxiv_id = paper.get("id", "")

        articles.append(ResearchArticle(
            title=title,
            authors=authors,
            abstract=abstract,
            url=f"https://huggingface.co/papers/{arxiv_id}" if arxiv_id else "",
            source="HuggingFace Papers",
            category=category,
            category_ru=category_ru,
            published=paper.get("publishedAt", "")[:10],
            arxiv_id=arxiv_id,
        ))

        if len(articles) >= limit:
            break

    return articles


# ============================================================
# Relevance scoring (category-aware)
# ============================================================

CATEGORY_KEYWORDS: Dict[str, Dict[str, int]] = {
    "architecture": {
        "microservice": 3, "event-driven": 3, "serverless": 3, "cloud-native": 3,
        "deployment": 2, "scalability": 2, "distributed": 2, "api gateway": 2,
        "container": 1, "kubernetes": 1, "docker": 1,
    },
    "intelligent_modules": {
        "mixture of agents": 3, "react": 3, "constitutional ai": 3, "reflexion": 3,
        "chain of thought": 3, "self-correction": 2, "multi-perspective": 2,
        "reasoning": 2, "planning": 2, "tool use": 2,
    },
    "memory_systems": {
        "memory augmented": 3, "episodic memory": 3, "tiered memory": 3,
        "context compression": 3, "long-term memory": 3, "retrieval": 2,
        "knowledge graph": 2, "memory management": 2, "summarization": 1,
    },
    "deep_research": {
        "deep research": 3, "web search": 3, "evidence synthesis": 3,
        "fact verification": 3, "information retrieval": 2, "multi-source": 2,
        "knowledge synthesis": 2, "citation": 1, "credibility": 1,
    },
    "safety": {
        "hallucination": 3, "prompt injection": 3, "safety guardrails": 3,
        "truthfulness": 3, "adversarial": 2, "toxicity": 2, "alignment": 2,
        "bias detection": 2, "red teaming": 1, "jailbreak": 1,
    },
    "performance": {
        "speculative decoding": 3, "quantization": 3, "inference optimization": 3,
        "token budget": 3, "prefix caching": 3, "kv cache": 3,
        "throughput": 2, "latency": 2, "vllm": 2, "batch": 2,
    },
    "pipelines": {
        "chain-of-agents": 3, "pipeline orchestration": 3, "workflow": 3,
        "tool augmented": 3, "agentic": 2, "task decomposition": 2,
        "routing": 2, "multi-step": 2, "function calling": 1,
    },
    "testing": {
        "evaluation": 3, "benchmark": 3, "testing": 3, "adversarial testing": 3,
        "robustness": 2, "automated testing": 2, "regression": 2,
        "coverage": 1, "quality assurance": 1,
    },
    "model_training": {
        "grpo": 3, "reinforcement learning": 3, "fine-tuning": 3, "lora": 3,
        "rlhf": 3, "reward model": 3, "policy optimization": 3,
        "distillation": 2, "curriculum learning": 2, "training efficiency": 2,
    },
    "general_agents": {
        "autonomous agent": 3, "multi-agent": 3, "self-improving": 3,
        "continuous learning": 3, "task planning": 2, "collaboration": 2,
        "agent architecture": 2, "goal-directed": 2, "emergent behavior": 1,
    },
    "obsidian_integration": {
        "knowledge management": 3, "personal knowledge": 3, "obsidian": 3,
        "zettelkasten": 3, "note-taking": 3, "knowledge graph": 3,
        "linked notes": 2, "retrieval": 2, "vault": 2, "markdown": 2,
        "second brain": 1, "pkm": 1,
    },
    "openrouter_models": {
        "model routing": 3, "model selection": 3, "api routing": 3,
        "ensemble": 3, "cost optimization": 3, "model evaluation": 3,
        "benchmark": 2, "inference cost": 2, "model comparison": 2,
        "multi-model": 2, "provider": 1, "fallback": 1,
    },
}

UNIVERSAL_KEYWORDS: Dict[str, int] = {
    "llm": 1, "language model": 1, "transformer": 1, "open source": 1,
    "python": 1, "neural network": 1, "deep learning": 1,
}


def compute_relevance(article: ResearchArticle) -> float:
    """Compute relevance score with category-awareness."""
    text = (article.title + " " + article.abstract).lower()
    score = 0.0

    # Category-specific keywords
    cat_kw = CATEGORY_KEYWORDS.get(article.category, {})
    for keyword, weight in cat_kw.items():
        if keyword in text:
            score += weight

    # Universal keywords
    for keyword, weight in UNIVERSAL_KEYWORDS.items():
        if keyword in text:
            score += weight

    score = min(10.0, score)

    # Recency bonus
    if article.published:
        try:
            year = int(article.published[:4])
            if year >= 2026:
                score = min(10.0, score + 1.0)
            elif year >= 2025:
                score = min(10.0, score + 0.5)
        except (ValueError, IndexError):
            pass

    # Code bonus
    if article.code_url:
        score = min(10.0, score + 0.5)

    return round(score, 1)


# Improvement suggestions by category
IMPROVEMENT_TEMPLATES: Dict[str, str] = {
    "architecture": "Улучшение архитектуры: {concept} для повышения масштабируемости и надёжности OpenClaw.",
    "intelligent_modules": "Новый интеллектуальный модуль: {concept} для улучшения качества рассуждений агентов.",
    "memory_systems": "Улучшение памяти: {concept} для более эффективного управления контекстом.",
    "deep_research": "Улучшение Deep Research: {concept} для более точного поиска и синтеза информации.",
    "safety": "Усиление безопасности: {concept} для защиты от некорректных/опасных ответов.",
    "performance": "Оптимизация: {concept} для ускорения инференса и снижения потребления ресурсов.",
    "pipelines": "Улучшение пайплайна: {concept} для более эффективной оркестрации агентов.",
    "testing": "Улучшение тестирования: {concept} для повышения надёжности и качества бота.",
    "model_training": "Улучшение обучения: {concept} для повышения качества дообучения моделей.",
    "general_agents": "Общее улучшение: {concept} для развития автономных возможностей OpenClaw.",
    "obsidian_integration": "Интеграция Obsidian: {concept} для улучшения управления знаниями и самообучения.",
    "openrouter_models": "Оптимизация моделей: {concept} для улучшения выбора и качества моделей OpenRouter.",
}


def generate_improvement_summary(article: ResearchArticle) -> str:
    """Generate improvement suggestion based on article content."""
    # Extract key concept from title
    title = article.title
    # Clean up title
    concept = title.split(":")[-1].strip() if ":" in title else title
    if len(concept) > 80:
        concept = concept[:77] + "..."

    template = IMPROVEMENT_TEMPLATES.get(article.category, "Применение: {concept}")
    return template.format(concept=concept)


# ============================================================
# Main parser
# ============================================================

def parse_all_categories(limit_per_source: int = 10, dry_run: bool = False) -> Dict[str, List[ResearchArticle]]:
    """
    Parse articles from all sources for all 10 categories.
    Returns dict: {category_key: [ResearchArticle, ...]}
    """
    all_articles: Dict[str, List[ResearchArticle]] = {k: [] for k in RESEARCH_CATEGORIES}

    sources = [
        ("Semantic Scholar", fetch_semantic_scholar),
        ("arXiv", fetch_arxiv),
        ("Papers With Code", fetch_papers_with_code),
        ("HuggingFace Papers", fetch_huggingface_papers),
    ]

    total_fetched = 0

    for cat_key, cat_info in RESEARCH_CATEGORIES.items():
        name_ru = cat_info["name_ru"]
        name_en = cat_info["name_en"]
        topics = cat_info["topics"]

        print(f"\n{'='*60}")
        print(f"📂 Категория: {name_ru} ({name_en})")
        print(f"{'='*60}")

        for topic in topics:
            print(f"\n  📖 Тема: {topic}")

            for source_name, fetch_fn in sources:
                if dry_run:
                    print(f"    🔍 [DRY RUN] {source_name}")
                    continue

                print(f"    🔍 {source_name}...", end=" ", flush=True)
                try:
                    articles = fetch_fn(topic, cat_key, name_ru, limit=limit_per_source)
                    for a in articles:
                        a.relevance_score = compute_relevance(a)
                        a.improvement_summary = generate_improvement_summary(a)

                    # Deduplicate
                    existing = {a.title.lower()[:50] for a in all_articles[cat_key]}
                    new_articles = [a for a in articles if a.title.lower()[:50] not in existing]
                    all_articles[cat_key].extend(new_articles)
                    total_fetched += len(new_articles)
                    print(f"✅ {len(new_articles)} новых")
                except Exception as e:
                    print(f"❌ {e}")

                time.sleep(1)  # Rate limiting

    # Sort by relevance within each category
    for cat_key in all_articles:
        all_articles[cat_key].sort(key=lambda a: (-a.relevance_score, -a.citations))

    print(f"\n\n📊 Итого: {total_fetched} статей по {len(RESEARCH_CATEGORIES)} категориям")
    return all_articles


def save_results(
    all_articles: Dict[str, List[ResearchArticle]],
    output_dir: str,
    limit_per_category: int = 30,
) -> Tuple[int, str]:
    """Save results as per-category markdown + master index. Returns (count, master_path)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    total = 0
    category_summaries: List[Dict[str, Any]] = []

    for cat_key, articles in all_articles.items():
        cat_info = RESEARCH_CATEGORIES[cat_key]
        name_ru = cat_info["name_ru"]
        top = articles[:limit_per_category]
        if not top:
            continue

        cat_dir = out / cat_key
        cat_dir.mkdir(parents=True, exist_ok=True)

        # Build category markdown
        md = f"# {name_ru}\n\n"
        md += f"> Статей: {len(top)} | Источники: Semantic Scholar, arXiv, Papers With Code, HuggingFace\n"
        md += f"> Дата: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"

        md += "| # | Статья | Источник | Релев. | Год |\n"
        md += "|---|--------|----------|--------|-----|\n"
        for i, a in enumerate(top, 1):
            safe = a.title[:70].replace("|", "\\|")
            md += f"| {i} | {safe} | {a.source} | {a.relevance_score}/10 | {a.published[:4] if a.published else '?'} |\n"

        md += "\n---\n\n"
        for i, a in enumerate(top, 1):
            md += f"### {i}. {a.title}\n\n"
            md += a.to_markdown()
            md += "\n---\n\n"

        with open(cat_dir / "README.md", "w", encoding="utf-8") as f:
            f.write(md)

        # JSON export
        raw = [asdict(a) for a in top]
        with open(cat_dir / "articles.json", "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)

        total += len(top)
        category_summaries.append({
            "key": cat_key,
            "name_ru": name_ru,
            "count": len(top),
            "avg_relevance": round(sum(a.relevance_score for a in top) / max(1, len(top)), 1),
        })

        print(f"  📁 {name_ru}: {len(top)} статей → {cat_dir}/")

    # Master index
    master = f"# 📚 Комплексное исследование для улучшения OpenClaw Bot\n\n"
    master += f"> Дата: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
    master += f"> Всего статей: {total} по {len(category_summaries)} категориям\n\n"

    master += "## Категории\n\n"
    master += "| Категория | Статей | Ср. релевантность |\n"
    master += "|-----------|--------|-------------------|\n"
    for s in category_summaries:
        master += f"| [{s['name_ru']}](./{s['key']}/README.md) | {s['count']} | {s['avg_relevance']}/10 |\n"

    master += f"\n## GitHub-репозитории для обучения\n\n"
    master += "| Репозиторий | ⭐ | Описание | Категория |\n"
    master += "|------------|-----|----------|----------|\n"
    for repo in GITHUB_REPOS:
        cat_ru = RESEARCH_CATEGORIES.get(repo["category"], {}).get("name_ru", repo["category"])
        master += f"| [{repo['name']}](https://github.com/{repo['name']}) | {repo['stars']} | {repo['desc'][:60]} | {cat_ru} |\n"

    master_path = out / "README.md"
    with open(master_path, "w", encoding="utf-8") as f:
        f.write(master)

    return total, str(master_path)


def main():
    parser = argparse.ArgumentParser(description="Comprehensive Research Parser for OpenClaw")
    parser.add_argument("--limit", type=int, default=30, help="Max articles per category (default: 30)")
    parser.add_argument("--limit-per-source", type=int, default=10, help="Max per source per topic (default: 10)")
    parser.add_argument("--dry-run", action="store_true", help="Don't fetch, just show what would be done")
    parser.add_argument("--output", default=BASE_OUTPUT_DIR, help="Output directory")
    args = parser.parse_args()

    print("🚀 OpenClaw Comprehensive Research Parser v2.0")
    print(f"   Категорий: {len(RESEARCH_CATEGORIES)}")
    print(f"   Тем: {sum(len(c['topics']) for c in RESEARCH_CATEGORIES.values())}")
    print(f"   Источников: 4 (Semantic Scholar, arXiv, Papers With Code, HuggingFace)")
    print(f"   GitHub-репозиториев: {len(GITHUB_REPOS)}")

    all_articles = parse_all_categories(
        limit_per_source=args.limit_per_source,
        dry_run=args.dry_run,
    )

    if not args.dry_run:
        total, master_path = save_results(all_articles, args.output, limit_per_category=args.limit)
        print(f"\n✅ Готово: {total} статей сохранено")
        print(f"   Мастер-индекс: {master_path}")
    else:
        print("\n✅ Dry run завершён")


if __name__ == "__main__":
    main()
