"""
Tests for DevOps Research Parser — containerization, orchestration, security, skills.

Validates:
  - DEVOPS_IMPROVEMENTS list has exactly 20 items
  - All 4 categories represented (5 each)
  - compute_devops_relevance scoring
  - Markdown generation
  - JSON generation
  - DEVOPS_TOPICS list covers all 4 areas
"""

import json
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from research_devops_parser import (
    DEVOPS_IMPROVEMENTS,
    DEVOPS_KEYWORDS,
    DEVOPS_TOPICS,
    compute_devops_relevance,
    generate_improvements_json,
    generate_improvements_markdown,
)

# Also verify base parser imports work
from research_paper_parser import Paper


# ── Improvements list structure ──────────────────────────────

class TestImprovementsList:
    """Verify the 20 improvements list structure and content."""

    def test_exactly_20_improvements(self):
        assert len(DEVOPS_IMPROVEMENTS) == 20

    def test_unique_ids(self):
        ids = [imp["id"] for imp in DEVOPS_IMPROVEMENTS]
        assert len(set(ids)) == 20
        assert ids == list(range(1, 21))

    def test_all_required_fields(self):
        required = {"id", "category", "title", "source", "description", "benefit"}
        for imp in DEVOPS_IMPROVEMENTS:
            missing = required - set(imp.keys())
            assert not missing, f"Improvement #{imp['id']} missing: {missing}"

    def test_four_categories(self):
        categories = {imp["category"] for imp in DEVOPS_IMPROVEMENTS}
        expected = {"Контейнеризация", "Оркестрация", "Безопасность", "Новые скиллы"}
        assert categories == expected

    def test_five_per_category(self):
        counts = {}
        for imp in DEVOPS_IMPROVEMENTS:
            counts[imp["category"]] = counts.get(imp["category"], 0) + 1
        for cat, count in counts.items():
            assert count == 5, f"{cat}: expected 5, got {count}"

    def test_containerization_ids(self):
        cat_ids = [imp["id"] for imp in DEVOPS_IMPROVEMENTS if imp["category"] == "Контейнеризация"]
        assert cat_ids == [1, 2, 3, 4, 5]

    def test_orchestration_ids(self):
        cat_ids = [imp["id"] for imp in DEVOPS_IMPROVEMENTS if imp["category"] == "Оркестрация"]
        assert cat_ids == [6, 7, 8, 9, 10]

    def test_security_ids(self):
        cat_ids = [imp["id"] for imp in DEVOPS_IMPROVEMENTS if imp["category"] == "Безопасность"]
        assert cat_ids == [11, 12, 13, 14, 15]

    def test_skills_ids(self):
        cat_ids = [imp["id"] for imp in DEVOPS_IMPROVEMENTS if imp["category"] == "Новые скиллы"]
        assert cat_ids == [16, 17, 18, 19, 20]

    def test_all_have_sources(self):
        for imp in DEVOPS_IMPROVEMENTS:
            assert len(imp["source"]) > 10, f"#{imp['id']}: source too short"

    def test_descriptions_not_empty(self):
        for imp in DEVOPS_IMPROVEMENTS:
            assert len(imp["description"]) > 50, f"#{imp['id']}: description too short"
            assert len(imp["benefit"]) > 30, f"#{imp['id']}: benefit too short"

    def test_titles_unique(self):
        titles = [imp["title"] for imp in DEVOPS_IMPROVEMENTS]
        assert len(set(titles)) == 20


# ── Topics ──────────────────────────────────────

class TestDevOpsTopics:
    """Verify topic coverage."""

    def test_topics_count(self):
        assert len(DEVOPS_TOPICS) == 20

    def test_containerization_topics(self):
        container_topics = [t for t in DEVOPS_TOPICS if any(
            w in t.lower() for w in ["container", "docker", "distroless", "oci", "wasm"]
        )]
        assert len(container_topics) >= 4

    def test_orchestration_topics(self):
        orch_topics = [t for t in DEVOPS_TOPICS if any(
            w in t.lower() for w in ["kubernetes", "gitops", "orchestrat", "service mesh", "scheduling"]
        )]
        assert len(orch_topics) >= 4

    def test_security_topics(self):
        sec_topics = [t for t in DEVOPS_TOPICS if any(
            w in t.lower() for w in ["security", "injection", "zero trust", "vulnerability", "secrets"]
        )]
        assert len(sec_topics) >= 4

    def test_skills_topics(self):
        skill_topics = [t for t in DEVOPS_TOPICS if any(
            w in t.lower() for w in ["agent", "tool", "skill", "mcp", "multi-agent", "browsing"]
        )]
        assert len(skill_topics) >= 4


# ── Relevance scoring ──────────────────────────────────────

class TestRelevanceScoring:
    """Test DevOps-specific relevance computation."""

    def test_high_relevance_container_paper(self):
        paper = Paper(
            title="Rootless Container Security with gVisor for Kubernetes",
            authors=["Test Author"],
            abstract="Docker container isolation using gVisor sandbox runtime in Kubernetes orchestration",
            url="https://example.com",
            source="test",
            published="2026-01-01",
        )
        score = compute_devops_relevance(paper)
        assert score >= 7.0  # Many keywords match

    def test_low_relevance_unrelated_paper(self):
        paper = Paper(
            title="Protein Folding with AlphaFold",
            authors=["Test Author"],
            abstract="Novel approach to protein structure prediction using deep learning",
            url="https://example.com",
            source="test",
        )
        score = compute_devops_relevance(paper)
        assert score <= 3.0

    def test_recent_paper_bonus(self):
        paper_old = Paper(
            title="Container Security Survey",
            authors=["Test"],
            abstract="Security analysis of container orchestration",
            url="https://example.com",
            source="test",
            published="2023-01-01",
        )
        paper_new = Paper(
            title="Container Security Survey",
            authors=["Test"],
            abstract="Security analysis of container orchestration",
            url="https://example.com",
            source="test",
            published="2026-01-01",
        )
        score_old = compute_devops_relevance(paper_old)
        score_new = compute_devops_relevance(paper_new)
        assert score_new > score_old

    def test_code_url_bonus(self):
        paper_no_code = Paper(
            title="Agent Security",
            authors=["Test"],
            abstract="Security for AI agents",
            url="https://example.com",
            source="test",
        )
        paper_with_code = Paper(
            title="Agent Security",
            authors=["Test"],
            abstract="Security for AI agents",
            url="https://example.com",
            source="test",
            code_url="https://github.com/test/test",
        )
        score_no = compute_devops_relevance(paper_no_code)
        score_yes = compute_devops_relevance(paper_with_code)
        assert score_yes >= score_no

    def test_score_capped_at_10(self):
        paper = Paper(
            title="Container Docker Kubernetes gVisor Rootless Security Sandbox Agent Tool MCP",
            authors=["Test"],
            abstract="orchestration autoscaling service mesh gitops vulnerability supply chain zero trust prompt injection secrets management isolation monitoring deployment scaling llm gpu vram",
            url="https://example.com",
            source="test",
            published="2026-06-01",
            code_url="https://github.com/test",
        )
        score = compute_devops_relevance(paper)
        assert score <= 10.0


# ── Markdown generation ──────────────────────────────────────

class TestMarkdownGeneration:
    """Test improvements document generation."""

    def test_markdown_not_empty(self):
        md = generate_improvements_markdown()
        assert len(md) > 1000

    def test_markdown_has_all_20_titles(self):
        md = generate_improvements_markdown()
        for imp in DEVOPS_IMPROVEMENTS:
            assert imp["title"] in md, f"Missing title: {imp['title']}"

    def test_markdown_has_categories(self):
        md = generate_improvements_markdown()
        for cat in ["Контейнеризация", "Оркестрация", "Безопасность", "Новые скиллы"]:
            assert cat in md

    def test_markdown_has_summary_table(self):
        md = generate_improvements_markdown()
        assert "| Категория |" in md
        assert "| **ИТОГО** | **20** |" in md

    def test_markdown_has_priority_table(self):
        md = generate_improvements_markdown()
        assert "Приоритет внедрения" in md

    def test_markdown_has_roadmap_reference(self):
        md = generate_improvements_markdown()
        assert "ROADMAP_OPENCLAW2026" in md


# ── JSON generation ──────────────────────────────────────

class TestJSONGeneration:
    """Test JSON output."""

    def test_json_serializable(self):
        data = generate_improvements_json()
        json_str = json.dumps(data, ensure_ascii=False)
        assert len(json_str) > 100

    def test_json_roundtrip(self):
        data = generate_improvements_json()
        json_str = json.dumps(data, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert len(parsed) == 20

    def test_json_has_all_fields(self):
        data = generate_improvements_json()
        for item in data:
            assert "id" in item
            assert "category" in item
            assert "title" in item
            assert "description" in item
            assert "benefit" in item


# ── Keywords coverage ──────────────────────────────────────

class TestKeywords:
    """Verify DevOps keywords coverage."""

    def test_container_keywords(self):
        container_kw = [k for k in DEVOPS_KEYWORDS if k in ("container", "docker", "kubernetes", "rootless", "gvisor")]
        assert len(container_kw) >= 4

    def test_security_keywords(self):
        sec_kw = [k for k in DEVOPS_KEYWORDS if k in ("security", "vulnerability", "zero trust", "prompt injection")]
        assert len(sec_kw) >= 3

    def test_all_keywords_have_positive_weight(self):
        for kw, weight in DEVOPS_KEYWORDS.items():
            assert weight > 0, f"Keyword '{kw}' has non-positive weight"
