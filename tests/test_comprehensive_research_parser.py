"""
Tests for Comprehensive Research Parser — 10 categories × 4 sources.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.research_comprehensive_parser import (
    CATEGORY_KEYWORDS,
    GITHUB_REPOS,
    IMPROVEMENT_TEMPLATES,
    RESEARCH_CATEGORIES,
    UNIVERSAL_KEYWORDS,
    ResearchArticle,
    compute_relevance,
    fetch_arxiv,
    fetch_huggingface_papers,
    fetch_papers_with_code,
    fetch_semantic_scholar,
    generate_improvement_summary,
    parse_all_categories,
    save_results,
)


# ============================================================
# Category structure tests
# ============================================================

class TestCategoryStructure:
    """Tests for the 10-category research structure."""

    def test_exactly_10_categories(self):
        assert len(RESEARCH_CATEGORIES) == 10

    def test_category_keys(self):
        expected = {
            "architecture", "intelligent_modules", "memory_systems",
            "deep_research", "safety", "performance", "pipelines",
            "testing", "model_training", "general_agents",
        }
        assert set(RESEARCH_CATEGORIES.keys()) == expected

    def test_each_category_has_3_topics(self):
        for key, info in RESEARCH_CATEGORIES.items():
            assert len(info["topics"]) == 3, f"{key} should have 3 topics, has {len(info['topics'])}"

    def test_total_30_topics(self):
        total = sum(len(c["topics"]) for c in RESEARCH_CATEGORIES.values())
        assert total == 30

    def test_each_category_has_names(self):
        for key, info in RESEARCH_CATEGORIES.items():
            assert "name_ru" in info, f"{key} missing name_ru"
            assert "name_en" in info, f"{key} missing name_en"
            assert len(info["name_ru"]) > 3, f"{key} name_ru too short"
            assert len(info["name_en"]) > 3, f"{key} name_en too short"

    def test_russian_names_are_present(self):
        """All categories should have non-empty Russian or English names."""
        for key, info in RESEARCH_CATEGORIES.items():
            name = info["name_ru"]
            assert len(name) >= 3, f"{key} name_ru too short: '{name}'"

    def test_topics_are_non_empty_strings(self):
        for key, info in RESEARCH_CATEGORIES.items():
            for topic in info["topics"]:
                assert isinstance(topic, str)
                assert len(topic) > 10, f"Topic too short in {key}: '{topic}'"

    def test_no_duplicate_topics(self):
        all_topics = []
        for info in RESEARCH_CATEGORIES.values():
            all_topics.extend(info["topics"])
        assert len(all_topics) == len(set(all_topics)), "Duplicate topics found"


# ============================================================
# GitHub repos tests
# ============================================================

class TestGitHubRepos:
    """Tests for the GitHub repositories list."""

    def test_repos_exist(self):
        assert len(GITHUB_REPOS) >= 15

    def test_repo_has_required_fields(self):
        for repo in GITHUB_REPOS:
            assert "name" in repo, f"Missing 'name' in {repo}"
            assert "stars" in repo, f"Missing 'stars' in {repo}"
            assert "desc" in repo, f"Missing 'desc' in {repo}"
            assert "category" in repo, f"Missing 'category' in {repo}"

    def test_repo_categories_are_valid(self):
        valid = set(RESEARCH_CATEGORIES.keys())
        for repo in GITHUB_REPOS:
            assert repo["category"] in valid, f"Invalid category '{repo['category']}' for {repo['name']}"

    def test_repo_names_are_valid(self):
        for repo in GITHUB_REPOS:
            name = repo["name"]
            assert "/" in name, f"Repo name should be 'owner/repo': {name}"
            parts = name.split("/")
            assert len(parts) == 2, f"Repo name should have exactly one '/': {name}"

    def test_key_repos_present(self):
        names = {r["name"] for r in GITHUB_REPOS}
        assert "huggingface/trl" in names
        assert "OpenRLHF/OpenRLHF" in names
        assert "vllm-project/vllm" in names
        assert "verl-project/verl" in names


# ============================================================
# ResearchArticle tests
# ============================================================

class TestResearchArticle:
    """Tests for the ResearchArticle data class."""

    def _make_article(self, **kwargs):
        defaults = {
            "title": "Test Paper on GRPO Training",
            "authors": ["Author A", "Author B"],
            "abstract": "We propose a novel approach to GRPO training...",
            "url": "https://arxiv.org/abs/2024.12345",
            "source": "arXiv",
            "category": "model_training",
            "category_ru": "Обучение моделей",
            "published": "2025-06-01",
            "arxiv_id": "2024.12345",
            "citations": 42,
            "relevance_score": 7.5,
        }
        defaults.update(kwargs)
        return ResearchArticle(**defaults)

    def test_create_article(self):
        a = self._make_article()
        assert a.title == "Test Paper on GRPO Training"
        assert a.category == "model_training"
        assert a.relevance_score == 7.5

    def test_to_markdown_basic(self):
        a = self._make_article()
        md = a.to_markdown()
        assert "Author A" in md
        assert "arXiv" in md
        assert "7.5/10" in md

    def test_to_markdown_with_code_url(self):
        a = self._make_article(code_url="https://github.com/test/repo")
        md = a.to_markdown()
        assert "github.com/test/repo" in md

    def test_to_markdown_many_authors(self):
        a = self._make_article(authors=[f"Author {i}" for i in range(10)])
        md = a.to_markdown()
        assert "и ещё 5" in md

    def test_to_markdown_with_improvement(self):
        a = self._make_article(improvement_summary="Применить GRPO для дообучения")
        md = a.to_markdown()
        assert "Применить GRPO" in md

    def test_asdict(self):
        from dataclasses import asdict
        a = self._make_article()
        d = asdict(a)
        assert d["title"] == "Test Paper on GRPO Training"
        assert d["citations"] == 42

    def test_json_serializable(self):
        from dataclasses import asdict
        a = self._make_article()
        j = json.dumps(asdict(a), ensure_ascii=False)
        assert "GRPO" in j


# ============================================================
# Relevance scoring tests
# ============================================================

class TestRelevanceScoring:
    """Tests for category-aware relevance scoring."""

    def _make_article(self, title="", abstract="", category="model_training", published="2025"):
        return ResearchArticle(
            title=title,
            authors=[],
            abstract=abstract,
            url="",
            source="test",
            category=category,
            category_ru="",
            published=published,
        )

    def test_low_for_empty(self):
        a = self._make_article(title="", abstract="", published="")
        assert compute_relevance(a) <= 1.0

    def test_high_for_matching_keywords(self):
        a = self._make_article(
            title="GRPO: Group Relative Policy Optimization for LLM Fine-tuning",
            abstract="reinforcement learning with reward model and LoRA",
            category="model_training",
        )
        score = compute_relevance(a)
        assert score >= 5.0

    def test_category_aware_scoring(self):
        """Safety keywords should score higher in safety category."""
        a_safety = self._make_article(
            title="Hallucination Detection in LLMs with Safety Guardrails",
            abstract="prompt injection defense",
            category="safety",
        )
        a_training = self._make_article(
            title="Hallucination Detection in LLMs with Safety Guardrails",
            abstract="prompt injection defense",
            category="model_training",
        )
        score_safety = compute_relevance(a_safety)
        score_training = compute_relevance(a_training)
        assert score_safety > score_training

    def test_recency_bonus_2026(self):
        a2025 = self._make_article(title="Test LLM paper", published="2025-01-01")
        a2026 = self._make_article(title="Test LLM paper", published="2026-01-01")
        assert compute_relevance(a2026) > compute_relevance(a2025)

    def test_code_bonus(self):
        a_no_code = self._make_article(title="GRPO training")
        a_code = self._make_article(title="GRPO training")
        a_code.code_url = "https://github.com/test/repo"
        assert compute_relevance(a_code) > compute_relevance(a_no_code)

    def test_max_score_is_10(self):
        a = self._make_article(
            title="GRPO reinforcement learning fine-tuning LoRA RLHF reward model policy optimization distillation curriculum learning training efficiency",
            abstract="LLM language model transformer open source",
            category="model_training",
            published="2026",
        )
        a.code_url = "https://github.com/test"
        score = compute_relevance(a)
        assert score <= 10.0

    def test_all_categories_have_keywords(self):
        for cat_key in RESEARCH_CATEGORIES:
            assert cat_key in CATEGORY_KEYWORDS, f"Missing keywords for {cat_key}"
            assert len(CATEGORY_KEYWORDS[cat_key]) >= 5, f"Too few keywords for {cat_key}"


# ============================================================
# Improvement summary tests
# ============================================================

class TestImprovementSummary:
    """Tests for improvement summary generation."""

    def test_generates_summary(self):
        a = ResearchArticle(
            title="Novel Approach: GRPO for Code Generation",
            authors=[], abstract="", url="", source="",
            category="model_training", category_ru="Обучение моделей",
        )
        summary = generate_improvement_summary(a)
        assert "Улучшение обучения" in summary
        assert "GRPO" in summary

    def test_all_categories_have_templates(self):
        for key in RESEARCH_CATEGORIES:
            assert key in IMPROVEMENT_TEMPLATES, f"Missing template for {key}"

    def test_template_has_placeholder(self):
        for key, tmpl in IMPROVEMENT_TEMPLATES.items():
            assert "{concept}" in tmpl, f"Template for {key} missing {{concept}}"

    def test_long_title_truncated(self):
        a = ResearchArticle(
            title="A" * 200,
            authors=[], abstract="", url="", source="",
            category="safety", category_ru="Безопасность",
        )
        summary = generate_improvement_summary(a)
        assert len(summary) < 300


# ============================================================
# Fetch function mock tests
# ============================================================

class TestFetchSemantic:
    """Tests for Semantic Scholar fetcher."""

    def test_returns_list(self):
        mock_data = {
            "data": [
                {
                    "title": "Test Paper",
                    "authors": [{"name": "Alice"}],
                    "abstract": "This is a test abstract about GRPO.",
                    "url": "https://example.com",
                    "year": 2025,
                    "citationCount": 10,
                    "externalIds": {"ArXiv": "2025.12345"},
                    "openAccessPdf": None,
                }
            ]
        }
        with patch("scripts.research_comprehensive_parser._http_get_json", return_value=mock_data):
            results = fetch_semantic_scholar("test", "model_training", "Обучение")
            assert len(results) == 1
            assert results[0].source == "Semantic Scholar"
            assert results[0].arxiv_id == "2025.12345"

    def test_handles_none_response(self):
        with patch("scripts.research_comprehensive_parser._http_get_json", return_value=None):
            results = fetch_semantic_scholar("test", "safety", "Безопасность")
            assert results == []

    def test_skips_no_abstract(self):
        mock_data = {
            "data": [
                {"title": "No abstract paper", "authors": [], "abstract": None, "url": "", "year": 2025, "citationCount": 0, "externalIds": {}, "openAccessPdf": None},
                {"title": "Has abstract", "authors": [], "abstract": "Good paper", "url": "", "year": 2025, "citationCount": 0, "externalIds": {}, "openAccessPdf": None},
            ]
        }
        with patch("scripts.research_comprehensive_parser._http_get_json", return_value=mock_data):
            results = fetch_semantic_scholar("test", "testing", "Тестирование")
            assert len(results) == 1


class TestFetchArxiv:
    """Tests for arXiv fetcher."""

    SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2025.99999v1</id>
        <title>Test: Speculative Decoding for LLMs</title>
        <summary>We propose speculative decoding with draft models.</summary>
        <published>2025-06-01T00:00:00Z</published>
        <author><name>Bob Smith</name></author>
        <author><name>Alice Jones</name></author>
      </entry>
    </feed>"""

    def test_parses_xml(self):
        with patch("scripts.research_comprehensive_parser._http_get_text", return_value=self.SAMPLE_XML):
            results = fetch_arxiv("test", "performance", "Производительность")
            assert len(results) == 1
            assert "Speculative Decoding" in results[0].title
            assert results[0].source == "arXiv"
            assert len(results[0].authors) == 2

    def test_handles_none(self):
        with patch("scripts.research_comprehensive_parser._http_get_text", return_value=None):
            assert fetch_arxiv("test", "safety", "Безопасность") == []

    def test_handles_bad_xml(self):
        with patch("scripts.research_comprehensive_parser._http_get_text", return_value="not xml"):
            assert fetch_arxiv("test", "testing", "Тестирование") == []


class TestFetchPapersWithCode:
    """Tests for Papers With Code fetcher."""

    def test_returns_articles(self):
        mock_data = {
            "results": [
                {
                    "title": "Memory-Augmented LLM",
                    "authors": "Alice, Bob",
                    "abstract": "Memory systems for long-term context.",
                    "url_abs": "https://example.com/paper1",
                    "arxiv_id": "2025.11111",
                    "published": "2025-05",
                    "proceeding": "",
                }
            ]
        }
        with patch("scripts.research_comprehensive_parser._http_get_json", return_value=mock_data):
            results = fetch_papers_with_code("test", "memory_systems", "Память")
            assert len(results) == 1
            assert results[0].source == "Papers With Code"

    def test_handles_none(self):
        with patch("scripts.research_comprehensive_parser._http_get_json", return_value=None):
            assert fetch_papers_with_code("test", "pipelines", "Пайплайны") == []


class TestFetchHuggingface:
    """Tests for HuggingFace Papers fetcher."""

    def test_filters_by_topic(self):
        mock_data = [
            {
                "paper": {
                    "title": "GRPO Training for Code Generation",
                    "summary": "Training language models with reinforcement learning",
                    "authors": [{"name": "Researcher"}],
                    "id": "2025.55555",
                    "publishedAt": "2025-06-01T00:00:00Z",
                }
            },
            {
                "paper": {
                    "title": "Unrelated Biology Paper",
                    "summary": "Protein folding",
                    "authors": [{"name": "Biologist"}],
                    "id": "2025.66666",
                    "publishedAt": "2025-06-01T00:00:00Z",
                }
            },
        ]
        with patch("scripts.research_comprehensive_parser._http_get_json", return_value=mock_data):
            results = fetch_huggingface_papers("GRPO training language", "model_training", "Обучение")
            assert len(results) == 1
            assert "GRPO" in results[0].title


# ============================================================
# Integration tests
# ============================================================

class TestParseAllCategories:
    """Tests for the main parse_all_categories function."""

    def test_dry_run_returns_empty(self):
        result = parse_all_categories(limit_per_source=1, dry_run=True)
        assert len(result) == 10
        for articles in result.values():
            assert articles == []

    def test_returns_all_category_keys(self):
        result = parse_all_categories(limit_per_source=1, dry_run=True)
        assert set(result.keys()) == set(RESEARCH_CATEGORIES.keys())


class TestSaveResults:
    """Tests for save_results function."""

    def test_saves_to_directory(self, tmp_path):
        articles = {
            "safety": [
                ResearchArticle(
                    title="Test Safety Paper",
                    authors=["Alice"],
                    abstract="Test abstract about hallucination detection",
                    url="https://example.com",
                    source="arXiv",
                    category="safety",
                    category_ru="Безопасность",
                    published="2025",
                    relevance_score=8.0,
                    improvement_summary="Test improvement",
                ),
            ],
        }
        # Add empty categories
        for k in RESEARCH_CATEGORIES:
            if k not in articles:
                articles[k] = []

        total, path = save_results(articles, str(tmp_path), limit_per_category=30)
        assert total == 1
        assert os.path.exists(path)

        # Check category dir created
        safety_dir = tmp_path / "safety"
        assert safety_dir.exists()
        assert (safety_dir / "README.md").exists()
        assert (safety_dir / "articles.json").exists()

        # Check JSON content
        with open(safety_dir / "articles.json") as f:
            data = json.load(f)
            assert len(data) == 1
            assert data[0]["title"] == "Test Safety Paper"

    def test_master_index_created(self, tmp_path):
        articles = {k: [] for k in RESEARCH_CATEGORIES}
        articles["model_training"] = [
            ResearchArticle(
                title="Training Paper",
                authors=["Bob"],
                abstract="GRPO training",
                url="https://example.com",
                source="Semantic Scholar",
                category="model_training",
                category_ru="Обучение моделей",
                published="2025",
                relevance_score=7.0,
            ),
        ]
        total, path = save_results(articles, str(tmp_path))
        assert total == 1

        readme = tmp_path / "README.md"
        assert readme.exists()
        content = readme.read_text()
        assert "OpenClaw" in content
        assert "huggingface/trl" in content  # GitHub repos should be listed


# ============================================================
# Keyword coverage tests
# ============================================================

class TestKeywordCoverage:
    """Tests ensuring keyword dictionaries are comprehensive."""

    def test_all_categories_have_keywords(self):
        for key in RESEARCH_CATEGORIES:
            assert key in CATEGORY_KEYWORDS
            assert len(CATEGORY_KEYWORDS[key]) >= 5

    def test_universal_keywords_exist(self):
        assert len(UNIVERSAL_KEYWORDS) >= 3

    def test_no_empty_keywords(self):
        for cat, kws in CATEGORY_KEYWORDS.items():
            for kw, weight in kws.items():
                assert len(kw) > 0, f"Empty keyword in {cat}"
                assert weight > 0, f"Zero weight for '{kw}' in {cat}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
