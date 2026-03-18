"""
Tests for Deep Research Parser — 40 deep research improvements (10 per site).

Validates:
  - DEEP_RESEARCH_IMPROVEMENTS list has exactly 40 items
  - All 4 sites represented (10 each)
  - compute_deep_research_relevance scoring
  - Markdown generation
  - JSON generation
  - DEEP_RESEARCH_TOPICS covers all 4 sites (10 each)
"""

import json
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from research_deep_research_parser import (
    ARXIV_TOPICS,
    DEEP_RESEARCH_IMPROVEMENTS,
    DEEP_RESEARCH_KEYWORDS,
    DEEP_RESEARCH_TOPICS,
    HUGGINGFACE_TOPICS,
    PAPERS_WITH_CODE_TOPICS,
    SEMANTIC_SCHOLAR_TOPICS,
    compute_deep_research_relevance,
    generate_deep_research_json,
    generate_deep_research_markdown,
)

from research_paper_parser import Paper


# ── Improvements list structure ──────────────────────────────

class TestDeepResearchImprovementsList:
    """Verify the 40 improvements list structure and content."""

    def test_exactly_40_improvements(self):
        assert len(DEEP_RESEARCH_IMPROVEMENTS) == 40

    def test_unique_ids(self):
        ids = [imp["id"] for imp in DEEP_RESEARCH_IMPROVEMENTS]
        assert len(set(ids)) == 40
        assert ids == list(range(1, 41))

    def test_all_required_fields(self):
        required = {"id", "category", "title", "source", "description", "benefit"}
        for imp in DEEP_RESEARCH_IMPROVEMENTS:
            missing = required - set(imp.keys())
            assert not missing, f"Improvement #{imp['id']} missing: {missing}"

    def test_four_categories(self):
        categories = {imp["category"] for imp in DEEP_RESEARCH_IMPROVEMENTS}
        expected = {"Semantic Scholar", "Papers With Code", "arXiv", "HuggingFace Papers"}
        assert categories == expected

    def test_ten_per_category(self):
        counts = {}
        for imp in DEEP_RESEARCH_IMPROVEMENTS:
            counts[imp["category"]] = counts.get(imp["category"], 0) + 1
        for cat, count in counts.items():
            assert count == 10, f"{cat}: expected 10, got {count}"

    def test_semantic_scholar_ids(self):
        ids = [imp["id"] for imp in DEEP_RESEARCH_IMPROVEMENTS if imp["category"] == "Semantic Scholar"]
        assert ids == list(range(1, 11))

    def test_papers_with_code_ids(self):
        ids = [imp["id"] for imp in DEEP_RESEARCH_IMPROVEMENTS if imp["category"] == "Papers With Code"]
        assert ids == list(range(11, 21))

    def test_arxiv_ids(self):
        ids = [imp["id"] for imp in DEEP_RESEARCH_IMPROVEMENTS if imp["category"] == "arXiv"]
        assert ids == list(range(21, 31))

    def test_huggingface_ids(self):
        ids = [imp["id"] for imp in DEEP_RESEARCH_IMPROVEMENTS if imp["category"] == "HuggingFace Papers"]
        assert ids == list(range(31, 41))

    def test_all_have_sources(self):
        for imp in DEEP_RESEARCH_IMPROVEMENTS:
            assert len(imp["source"]) > 10, f"#{imp['id']}: source too short"

    def test_descriptions_not_empty(self):
        for imp in DEEP_RESEARCH_IMPROVEMENTS:
            assert len(imp["description"]) > 50, f"#{imp['id']}: description too short"
            assert len(imp["benefit"]) > 30, f"#{imp['id']}: benefit too short"

    def test_titles_unique(self):
        titles = [imp["title"] for imp in DEEP_RESEARCH_IMPROVEMENTS]
        assert len(set(titles)) == 40


# ── Topics ──────────────────────────────────────

class TestDeepResearchTopics:
    """Verify topic coverage per site."""

    def test_total_topics_count(self):
        assert len(DEEP_RESEARCH_TOPICS) == 40

    def test_semantic_scholar_10_topics(self):
        assert len(SEMANTIC_SCHOLAR_TOPICS) == 10

    def test_papers_with_code_10_topics(self):
        assert len(PAPERS_WITH_CODE_TOPICS) == 10

    def test_arxiv_10_topics(self):
        assert len(ARXIV_TOPICS) == 10

    def test_huggingface_10_topics(self):
        assert len(HUGGINGFACE_TOPICS) == 10

    def test_topics_are_research_related(self):
        research_words = {"research", "reasoning", "retrieval", "search",
                          "question", "answering", "evidence", "synthesis",
                          "verification", "knowledge", "generation", "query",
                          "decomposition", "refinement", "citation", "chain",
                          "agent", "agents", "hallucination", "grounded", "document",
                          "rag", "augmented", "fusion", "pipeline",
                          "summarization", "benchmark", "dialogue", "tool",
                          "evaluation", "llm", "inference", "checking",
                          "uncertainty", "causal", "revision", "automation",
                          "extraction", "conversational", "orchestration",
                          "self-reflection", "self-critique", "iterative",
                          "multi-step", "multi-hop", "multi-source",
                          "chain-of-thought", "retrieval-augmented",
                          "cross-document", "agent-based", "tool-augmented",
                          "open-domain", "knowledge-intensive", "multi-agent",
                          "multi-turn", "multi-document", "long-form",
                          "counterfactual", "dense", "recursive", "adaptive",
                          "fact", "claim", "confidence", "planning"}
        for topic in DEEP_RESEARCH_TOPICS:
            words = set(topic.lower().split())
            has_research = bool(words & research_words)
            assert has_research, f"Topic not research-related: {topic}"


# ── Relevance scoring ──────────────────────────────────────

class TestDeepResearchRelevance:
    """Test deep-research-specific relevance computation."""

    def test_high_relevance_deep_research_paper(self):
        paper = Paper(
            title="Multi-step Reasoning with Evidence Synthesis for Deep Research",
            authors=["Test Author"],
            abstract="Retrieval-augmented generation with chain-of-thought verification and fact verification",
            url="https://example.com",
            source="test",
            published="2026-01-01",
        )
        score = compute_deep_research_relevance(paper)
        assert score >= 7.0

    def test_low_relevance_unrelated_paper(self):
        paper = Paper(
            title="Protein Folding with AlphaFold",
            authors=["Test Author"],
            abstract="Novel approach to protein structure prediction",
            url="https://example.com",
            source="test",
        )
        score = compute_deep_research_relevance(paper)
        assert score <= 3.0

    def test_recent_paper_bonus(self):
        paper_old = Paper(
            title="Query decomposition study",
            authors=["Test"],
            abstract="Approaches to recursive decomposition in information retrieval systems",
            url="https://example.com",
            source="test",
            published="2023-01-01",
        )
        paper_new = Paper(
            title="Query decomposition study",
            authors=["Test"],
            abstract="Approaches to recursive decomposition in information retrieval systems",
            url="https://example.com",
            source="test",
            published="2026-01-01",
        )
        score_old = compute_deep_research_relevance(paper_old)
        score_new = compute_deep_research_relevance(paper_new)
        assert score_new > score_old

    def test_code_url_bonus(self):
        paper_no_code = Paper(
            title="Evidence Chain Construction",
            authors=["Test"],
            abstract="Building evidence chains for multi-hop reasoning",
            url="https://example.com",
            source="test",
        )
        paper_with_code = Paper(
            title="Evidence Chain Construction",
            authors=["Test"],
            abstract="Building evidence chains for multi-hop reasoning",
            url="https://example.com",
            source="test",
            code_url="https://github.com/test/test",
        )
        score_no = compute_deep_research_relevance(paper_no_code)
        score_yes = compute_deep_research_relevance(paper_with_code)
        assert score_yes >= score_no

    def test_score_capped_at_10(self):
        paper = Paper(
            title="Deep Research Multi-step Reasoning Evidence Synthesis RAG Chain-of-thought Agent",
            authors=["Test"],
            abstract="retrieval-augmented generation dense retrieval multi-hop knowledge graph cross-document self-reflection hallucination grounded generation confidence estimation counterfactual reasoning iterative refinement research methodology agent-based research tool-augmented web search",
            url="https://example.com",
            source="test",
            published="2026-06-01",
            code_url="https://github.com/test",
        )
        score = compute_deep_research_relevance(paper)
        assert score <= 10.0


# ── Markdown generation ──────────────────────────────────────

class TestMarkdownGeneration:
    """Test improvements document generation."""

    def test_markdown_not_empty(self):
        md = generate_deep_research_markdown()
        assert len(md) > 5000

    def test_markdown_has_all_40_titles(self):
        md = generate_deep_research_markdown()
        for imp in DEEP_RESEARCH_IMPROVEMENTS:
            assert imp["title"] in md, f"Missing: {imp['title']}"

    def test_markdown_has_four_site_sections(self):
        md = generate_deep_research_markdown()
        for site in ["Semantic Scholar", "Papers With Code", "arXiv", "HuggingFace Papers"]:
            assert site in md

    def test_markdown_has_summary_table(self):
        md = generate_deep_research_markdown()
        assert "| Источник |" in md
        assert "| **ИТОГО** | **40** |" in md

    def test_markdown_has_date(self):
        md = generate_deep_research_markdown()
        assert "**Дата:**" in md


# ── JSON generation ──────────────────────────────────────

class TestJSONGeneration:
    """Test JSON output."""

    def test_json_serializable(self):
        data = generate_deep_research_json()
        json_str = json.dumps(data, ensure_ascii=False)
        assert len(json_str) > 100

    def test_json_roundtrip(self):
        data = generate_deep_research_json()
        json_str = json.dumps(data, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert len(parsed) == 40

    def test_json_has_all_fields(self):
        data = generate_deep_research_json()
        for item in data:
            assert "id" in item
            assert "category" in item
            assert "title" in item
            assert "description" in item
            assert "benefit" in item


# ── Keywords coverage ──────────────────────────────────────

class TestKeywords:
    """Verify deep research keywords coverage."""

    def test_core_research_keywords(self):
        core = ["deep research", "multi-step reasoning", "evidence synthesis",
                "fact verification", "query decomposition"]
        for kw in core:
            assert kw in DEEP_RESEARCH_KEYWORDS, f"Missing core keyword: {kw}"

    def test_rag_keywords(self):
        rag = ["retrieval-augmented", "rag", "dense retrieval", "multi-hop"]
        for kw in rag:
            assert kw in DEEP_RESEARCH_KEYWORDS, f"Missing RAG keyword: {kw}"

    def test_all_keywords_positive_weight(self):
        for kw, weight in DEEP_RESEARCH_KEYWORDS.items():
            assert weight > 0, f"Keyword '{kw}' has non-positive weight"
