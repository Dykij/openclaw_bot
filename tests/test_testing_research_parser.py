"""
Tests for Testing Research Parser — 40 testing improvements (10 per site).

Validates:
  - TESTING_IMPROVEMENTS list has exactly 40 items
  - All 4 sites represented (10 each)
  - compute_testing_relevance scoring
  - Markdown generation
  - JSON generation
  - ALL_TESTING_TOPICS covers all 4 sites (10 each)
"""

import json
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from research_testing_parser import (
    ALL_TESTING_TOPICS,
    ARXIV_TOPICS,
    HUGGINGFACE_TOPICS,
    PAPERS_WITH_CODE_TOPICS,
    SEMANTIC_SCHOLAR_TOPICS,
    TESTING_IMPROVEMENTS,
    TESTING_KEYWORDS,
    compute_testing_relevance,
    generate_testing_improvements_json,
    generate_testing_improvements_markdown,
)

from research_paper_parser import Paper


# ── Improvements list structure ──────────────────────────────

class TestTestingImprovementsList:
    """Verify the 40 improvements list structure and content."""

    def test_exactly_40_improvements(self):
        assert len(TESTING_IMPROVEMENTS) == 40

    def test_unique_ids(self):
        ids = [imp["id"] for imp in TESTING_IMPROVEMENTS]
        assert len(set(ids)) == 40
        assert ids == list(range(1, 41))

    def test_all_required_fields(self):
        required = {"id", "category", "title", "source", "description", "benefit"}
        for imp in TESTING_IMPROVEMENTS:
            missing = required - set(imp.keys())
            assert not missing, f"Improvement #{imp['id']} missing: {missing}"

    def test_four_categories(self):
        categories = {imp["category"] for imp in TESTING_IMPROVEMENTS}
        expected = {"Semantic Scholar", "Papers With Code", "arXiv", "HuggingFace Papers"}
        assert categories == expected

    def test_ten_per_category(self):
        counts = {}
        for imp in TESTING_IMPROVEMENTS:
            counts[imp["category"]] = counts.get(imp["category"], 0) + 1
        for cat, count in counts.items():
            assert count == 10, f"{cat}: expected 10, got {count}"

    def test_semantic_scholar_ids(self):
        ids = [imp["id"] for imp in TESTING_IMPROVEMENTS if imp["category"] == "Semantic Scholar"]
        assert ids == list(range(1, 11))

    def test_papers_with_code_ids(self):
        ids = [imp["id"] for imp in TESTING_IMPROVEMENTS if imp["category"] == "Papers With Code"]
        assert ids == list(range(11, 21))

    def test_arxiv_ids(self):
        ids = [imp["id"] for imp in TESTING_IMPROVEMENTS if imp["category"] == "arXiv"]
        assert ids == list(range(21, 31))

    def test_huggingface_ids(self):
        ids = [imp["id"] for imp in TESTING_IMPROVEMENTS if imp["category"] == "HuggingFace Papers"]
        assert ids == list(range(31, 41))

    def test_all_have_sources(self):
        for imp in TESTING_IMPROVEMENTS:
            assert len(imp["source"]) > 10, f"#{imp['id']}: source too short"

    def test_descriptions_not_empty(self):
        for imp in TESTING_IMPROVEMENTS:
            assert len(imp["description"]) > 50, f"#{imp['id']}: description too short"
            assert len(imp["benefit"]) > 30, f"#{imp['id']}: benefit too short"

    def test_titles_unique(self):
        titles = [imp["title"] for imp in TESTING_IMPROVEMENTS]
        assert len(set(titles)) == 40


# ── Topics ──────────────────────────────────────

class TestTestingTopics:
    """Verify topic coverage per site."""

    def test_total_topics_count(self):
        assert len(ALL_TESTING_TOPICS) == 40

    def test_semantic_scholar_10_topics(self):
        assert len(SEMANTIC_SCHOLAR_TOPICS) == 10

    def test_papers_with_code_10_topics(self):
        assert len(PAPERS_WITH_CODE_TOPICS) == 10

    def test_arxiv_10_topics(self):
        assert len(ARXIV_TOPICS) == 10

    def test_huggingface_10_topics(self):
        assert len(HUGGINGFACE_TOPICS) == 10

    def test_topics_are_testing_related(self):
        testing_words = {"test", "testing", "benchmark", "benchmarking",
                         "evaluation", "fuzz", "chaos", "regression",
                         "mutation", "adversarial", "robustness", "profiling",
                         "validation", "canary", "monitoring", "safety",
                         "security", "detection", "performance"}
        for topic in ALL_TESTING_TOPICS:
            words = set(topic.lower().split())
            has_testing = bool(words & testing_words)
            assert has_testing, f"Topic not testing-related: {topic}"


# ── Relevance scoring ──────────────────────────────────────

class TestTestingRelevance:
    """Test testing-specific relevance computation."""

    def test_high_relevance_testing_paper(self):
        paper = Paper(
            title="Mutation Testing for LLM Agent Evaluation Benchmark",
            authors=["Test Author"],
            abstract="Fuzzing and adversarial testing of LLM safety with coverage metrics",
            url="https://example.com",
            source="test",
            published="2026-01-01",
        )
        score = compute_testing_relevance(paper)
        assert score >= 7.0

    def test_low_relevance_unrelated_paper(self):
        paper = Paper(
            title="Protein Folding with AlphaFold",
            authors=["Test Author"],
            abstract="Novel approach to protein structure prediction",
            url="https://example.com",
            source="test",
        )
        score = compute_testing_relevance(paper)
        assert score <= 3.0

    def test_recent_paper_bonus(self):
        paper_old = Paper(
            title="Coverage analysis study",
            authors=["Test"],
            abstract="Approaches to code coverage measurement in software systems",
            url="https://example.com",
            source="test",
            published="2023-01-01",
        )
        paper_new = Paper(
            title="Coverage analysis study",
            authors=["Test"],
            abstract="Approaches to code coverage measurement in software systems",
            url="https://example.com",
            source="test",
            published="2026-01-01",
        )
        score_old = compute_testing_relevance(paper_old)
        score_new = compute_testing_relevance(paper_new)
        assert score_new > score_old

    def test_code_url_bonus(self):
        paper_no_code = Paper(
            title="Testing ML Pipelines",
            authors=["Test"],
            abstract="Testing framework for ML model evaluation",
            url="https://example.com",
            source="test",
        )
        paper_with_code = Paper(
            title="Testing ML Pipelines",
            authors=["Test"],
            abstract="Testing framework for ML model evaluation",
            url="https://example.com",
            source="test",
            code_url="https://github.com/test/test",
        )
        score_no = compute_testing_relevance(paper_no_code)
        score_yes = compute_testing_relevance(paper_with_code)
        assert score_yes >= score_no

    def test_score_capped_at_10(self):
        paper = Paper(
            title="Testing Benchmark Evaluation Fuzzing Mutation Adversarial Red Team Safety",
            authors=["Test"],
            abstract="testing test benchmark evaluation coverage regression hallucination prompt injection adversarial robustness monitoring ci/cd pipeline gpu vram latency agent model inference reproducibility snapshot api deploy",
            url="https://example.com",
            source="test",
            published="2026-06-01",
            code_url="https://github.com/test",
        )
        score = compute_testing_relevance(paper)
        assert score <= 10.0


# ── Markdown generation ──────────────────────────────────────

class TestMarkdownGeneration:
    """Test improvements document generation."""

    def test_markdown_not_empty(self):
        md = generate_testing_improvements_markdown()
        assert len(md) > 5000

    def test_markdown_has_all_40_titles(self):
        md = generate_testing_improvements_markdown()
        for imp in TESTING_IMPROVEMENTS:
            assert imp["title"] in md, f"Missing: {imp['title']}"

    def test_markdown_has_four_site_sections(self):
        md = generate_testing_improvements_markdown()
        for site in ["Semantic Scholar", "Papers With Code", "arXiv", "HuggingFace Papers"]:
            assert site in md

    def test_markdown_has_summary_table(self):
        md = generate_testing_improvements_markdown()
        assert "| Источник |" in md
        assert "| **ИТОГО** | **40** |" in md

    def test_markdown_has_date(self):
        md = generate_testing_improvements_markdown()
        assert "**Дата:**" in md


# ── JSON generation ──────────────────────────────────────

class TestJSONGeneration:
    """Test JSON output."""

    def test_json_serializable(self):
        data = generate_testing_improvements_json()
        json_str = json.dumps(data, ensure_ascii=False)
        assert len(json_str) > 100

    def test_json_roundtrip(self):
        data = generate_testing_improvements_json()
        json_str = json.dumps(data, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert len(parsed) == 40

    def test_json_has_all_fields(self):
        data = generate_testing_improvements_json()
        for item in data:
            assert "id" in item
            assert "category" in item
            assert "title" in item
            assert "description" in item
            assert "benefit" in item


# ── Keywords coverage ──────────────────────────────────────

class TestKeywords:
    """Verify testing keywords coverage."""

    def test_core_testing_keywords(self):
        core = ["testing", "benchmark", "evaluation", "coverage", "regression"]
        for kw in core:
            assert kw in TESTING_KEYWORDS, f"Missing core keyword: {kw}"

    def test_ai_testing_keywords(self):
        ai = ["adversarial", "hallucination", "prompt injection", "red team"]
        for kw in ai:
            assert kw in TESTING_KEYWORDS, f"Missing AI keyword: {kw}"

    def test_all_keywords_positive_weight(self):
        for kw, weight in TESTING_KEYWORDS.items():
            assert weight > 0, f"Keyword '{kw}' has non-positive weight"
