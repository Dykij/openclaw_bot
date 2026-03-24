"""
Tests for src.agent_personas module.

Covers:
- Frontmatter parsing
- Persona loading from Markdown files
- AgentRegistry lookup and listing
- Keyword-based routing
- Prompt building
- AgentPersonaManager lifecycle (activate / deactivate / augment)
"""

import os
import tempfile
import textwrap

import pytest

from src.agent_personas import (
    AgentPersona,
    AgentPersonaManager,
    AgentRegistry,
    _parse_frontmatter,
    build_persona_prompt,
    load_all_personas,
    load_persona_from_file,
    route_to_persona,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_MD = textwrap.dedent("""\
    ---
    name: "Test Agent"
    division: "engineering"
    tags: ["python", "testing", "qa"]
    description: "A test persona for unit tests."
    ---

    # Test Agent

    ## Role
    You are a test agent.

    ## Process
    1. Do things.
    2. Test things.

    ## Artifacts
    - Test report

    ## Metrics
    - 100% coverage
""")


def _write_temp_md(directory: str, filename: str, content: str) -> str:
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    def test_parses_name_and_division(self):
        meta, body = _parse_frontmatter(SAMPLE_MD)
        assert meta["name"] == "Test Agent"
        assert meta["division"] == "engineering"

    def test_parses_tag_list(self):
        meta, _ = _parse_frontmatter(SAMPLE_MD)
        assert isinstance(meta["tags"], list)
        assert "python" in meta["tags"]
        assert "testing" in meta["tags"]

    def test_parses_description(self):
        meta, _ = _parse_frontmatter(SAMPLE_MD)
        assert "unit tests" in meta["description"]

    def test_body_is_stripped(self):
        _, body = _parse_frontmatter(SAMPLE_MD)
        assert "## Role" in body
        assert "---" not in body

    def test_no_frontmatter_returns_empty_meta(self):
        text = "# Just a heading\n\nSome text."
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert "Just a heading" in body


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class TestLoadPersonaFromFile:
    def test_loads_valid_file(self, tmp_path):
        fp = _write_temp_md(str(tmp_path), "test-agent.md", SAMPLE_MD)
        persona = load_persona_from_file(fp)
        assert persona is not None
        assert persona.name == "Test Agent"
        assert persona.division == "engineering"
        assert persona.slug == "test-agent"
        assert "python" in persona.tags

    def test_slug_is_kebab_case(self, tmp_path):
        md = SAMPLE_MD.replace('"Test Agent"', '"My Super Agent"')
        fp = _write_temp_md(str(tmp_path), "my-super-agent.md", md)
        persona = load_persona_from_file(fp)
        assert persona is not None
        assert persona.slug == "my-super-agent"

    def test_missing_name_returns_none(self, tmp_path):
        bad_md = "---\ndivision: engineering\n---\n# No name"
        fp = _write_temp_md(str(tmp_path), "bad.md", bad_md)
        persona = load_persona_from_file(fp)
        assert persona is None

    def test_nonexistent_file_returns_none(self):
        persona = load_persona_from_file("/nonexistent/path/file.md")
        assert persona is None

    def test_body_included(self, tmp_path):
        fp = _write_temp_md(str(tmp_path), "test-agent.md", SAMPLE_MD)
        persona = load_persona_from_file(fp)
        assert persona is not None
        assert "## Role" in persona.body

    def test_filepath_stored(self, tmp_path):
        fp = _write_temp_md(str(tmp_path), "test-agent.md", SAMPLE_MD)
        persona = load_persona_from_file(fp)
        assert persona is not None
        assert persona.filepath == fp


class TestLoadAllPersonas:
    def test_loads_from_directory(self, tmp_path):
        sub = tmp_path / "engineering"
        sub.mkdir()
        _write_temp_md(str(sub), "agent-one.md", SAMPLE_MD)
        md2 = SAMPLE_MD.replace('"Test Agent"', '"Agent Two"')
        _write_temp_md(str(sub), "agent-two.md", md2)

        personas = load_all_personas(str(tmp_path))
        assert len(personas) == 2

    def test_ignores_non_md_files(self, tmp_path):
        sub = tmp_path / "engineering"
        sub.mkdir()
        _write_temp_md(str(sub), "agent.md", SAMPLE_MD)
        (sub / "README.txt").write_text("not a persona")

        personas = load_all_personas(str(tmp_path))
        assert len(personas) == 1

    def test_returns_empty_for_missing_dir(self):
        personas = load_all_personas("/nonexistent/agents/dir")
        assert personas == []

    def test_walks_subdirectories(self, tmp_path):
        for div in ("engineering", "design", "testing"):
            sub = tmp_path / div
            sub.mkdir()
            md = SAMPLE_MD.replace('"Test Agent"', f'"{div.title()} Agent"')
            _write_temp_md(str(sub), f"{div}-agent.md", md)

        personas = load_all_personas(str(tmp_path))
        assert len(personas) == 3


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestAgentRegistry:
    def _make_personas(self) -> list:
        return [
            AgentPersona(
                name="Code Reviewer",
                slug="code-reviewer",
                division="engineering",
                tags=["code-review"],
                description="Reviews code",
                body="## Role\nReviewer",
                filepath="/fake/code-reviewer.md",
            ),
            AgentPersona(
                name="QA Specialist",
                slug="qa-specialist",
                division="testing",
                tags=["qa", "testing"],
                description="Tests things",
                body="## Role\nTester",
                filepath="/fake/qa-specialist.md",
            ),
        ]

    def test_get_by_slug(self):
        registry = AgentRegistry(self._make_personas())
        p = registry.get("code-reviewer")
        assert p is not None
        assert p.name == "Code Reviewer"

    def test_get_returns_none_for_unknown(self):
        registry = AgentRegistry(self._make_personas())
        assert registry.get("nonexistent-agent") is None

    def test_list_unique_deduplicates(self):
        personas = self._make_personas()
        registry = AgentRegistry(personas)
        unique = registry.list_unique()
        names = [p.name for p in unique]
        assert len(names) == len(set(names))

    def test_list_by_division(self):
        registry = AgentRegistry(self._make_personas())
        engineering = registry.list_by_division("engineering")
        assert len(engineering) == 1
        assert engineering[0].name == "Code Reviewer"

    def test_divisions_returns_sorted_list(self):
        registry = AgentRegistry(self._make_personas())
        divs = registry.divisions()
        assert "engineering" in divs
        assert "testing" in divs
        assert divs == sorted(divs)

    def test_case_insensitive_get(self):
        registry = AgentRegistry(self._make_personas())
        p = registry.get("CODE-REVIEWER")
        assert p is not None


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class TestRouteToPersona:
    def _registry(self) -> AgentRegistry:
        """Build a minimal registry with the real personas directory."""
        src_dir = os.path.dirname(os.path.dirname(__file__))
        agents_dir = os.path.join(src_dir, "agents")
        personas = load_all_personas(agents_dir)
        return AgentRegistry(personas)

    def test_code_review_routes_to_code_reviewer(self):
        registry = self._registry()
        if not registry.list_unique():
            pytest.skip("No personas loaded — agents/ directory missing")
        result = route_to_persona("Please review this code and check for bugs", registry)
        assert result is not None
        assert result.slug == "code-reviewer"

    def test_test_writing_routes_to_qa(self):
        registry = self._registry()
        if not registry.list_unique():
            pytest.skip("No personas loaded")
        result = route_to_persona("Write tests for this module", registry)
        assert result is not None
        assert result.slug == "qa-specialist"

    def test_deploy_routes_to_devops(self):
        registry = self._registry()
        if not registry.list_unique():
            pytest.skip("No personas loaded")
        result = route_to_persona("Set up a docker deploy pipeline", registry)
        assert result is not None
        assert result.slug == "devops-automator"

    def test_unrelated_message_returns_none(self):
        registry = self._registry()
        result = route_to_persona("Good morning!", registry)
        assert result is None

    def test_russian_keyword_matches(self):
        registry = self._registry()
        if not registry.list_unique():
            pytest.skip("No personas loaded")
        result = route_to_persona("проверь код на ошибки", registry)
        assert result is not None
        assert result.slug == "code-reviewer"


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

class TestBuildPersonaPrompt:
    def _sample_persona(self) -> AgentPersona:
        return AgentPersona(
            name="Code Reviewer",
            slug="code-reviewer",
            division="engineering",
            tags=["review"],
            description="Expert code reviewer",
            body="## Role\nYou review code.\n\n## Process\n1. Read\n2. Comment",
            filepath="/fake/code-reviewer.md",
        )

    def test_contains_persona_name(self):
        prompt = build_persona_prompt(self._sample_persona())
        assert "CODE REVIEWER" in prompt

    def test_contains_division(self):
        prompt = build_persona_prompt(self._sample_persona())
        assert "ENGINEERING" in prompt

    def test_contains_description(self):
        prompt = build_persona_prompt(self._sample_persona())
        assert "Expert code reviewer" in prompt

    def test_contains_body(self):
        prompt = build_persona_prompt(self._sample_persona())
        assert "## Role" in prompt

    def test_contains_end_marker(self):
        prompt = build_persona_prompt(self._sample_persona())
        assert "[END AGENT PERSONA]" in prompt


# ---------------------------------------------------------------------------
# AgentPersonaManager
# ---------------------------------------------------------------------------

class TestAgentPersonaManager:
    def _manager(self, tmp_path) -> AgentPersonaManager:
        sub = tmp_path / "engineering"
        sub.mkdir()
        _write_temp_md(str(sub), "code-reviewer.md", SAMPLE_MD.replace('"Test Agent"', '"Code Reviewer"').replace('"engineering"', '"engineering"'))
        return AgentPersonaManager(agents_dir=str(tmp_path))

    def test_activate_returns_persona(self, tmp_path):
        manager = self._manager(tmp_path)
        # The slug comes from the name "Code Reviewer"
        persona = manager.activate(chat_id=123, slug="code-reviewer")
        assert persona is not None
        assert persona.name == "Code Reviewer"

    def test_activate_unknown_returns_none(self, tmp_path):
        manager = self._manager(tmp_path)
        persona = manager.activate(chat_id=123, slug="nonexistent")
        assert persona is None

    def test_active_persona_returns_set_persona(self, tmp_path):
        manager = self._manager(tmp_path)
        manager.activate(chat_id=42, slug="code-reviewer")
        active = manager.active_persona(42)
        assert active is not None

    def test_deactivate_clears_persona(self, tmp_path):
        manager = self._manager(tmp_path)
        manager.activate(chat_id=42, slug="code-reviewer")
        manager.deactivate(42)
        assert manager.active_persona(42) is None

    def test_get_persona_augmentation_when_active(self, tmp_path):
        manager = self._manager(tmp_path)
        manager.activate(chat_id=1, slug="code-reviewer")
        aug = manager.get_persona_augmentation(1)
        assert aug != ""
        assert "CODE REVIEWER" in aug

    def test_get_persona_augmentation_when_inactive(self, tmp_path):
        manager = self._manager(tmp_path)
        aug = manager.get_persona_augmentation(999)
        assert aug == ""

    def test_different_chats_have_independent_personas(self, tmp_path):
        # Add two personas in separate division directories
        sub1 = tmp_path / "engineering"
        sub1.mkdir()
        _write_temp_md(
            str(sub1), "code-reviewer.md",
            SAMPLE_MD.replace('"Test Agent"', '"Code Reviewer"')
        )
        sub2 = tmp_path / "testing"
        sub2.mkdir()
        qa_md = SAMPLE_MD.replace('"Test Agent"', '"QA Specialist"')
        qa_md = qa_md.replace('"engineering"', '"testing"')
        _write_temp_md(str(sub2), "qa-specialist.md", qa_md)
        manager = AgentPersonaManager(agents_dir=str(tmp_path))
        manager.activate(chat_id=1, slug="code-reviewer")
        manager.activate(chat_id=2, slug="qa-specialist")

        assert manager.active_persona(1).slug == "code-reviewer"
        assert manager.active_persona(2).slug == "qa-specialist"

    def test_format_list_contains_slug(self, tmp_path):
        manager = self._manager(tmp_path)
        listing = manager.format_list()
        assert "code-reviewer" in listing

    def test_format_info_unknown_agent(self, tmp_path):
        manager = self._manager(tmp_path)
        info = manager.format_info("nonexistent-agent")
        assert "не найден" in info

    def test_format_info_known_agent(self, tmp_path):
        manager = self._manager(tmp_path)
        info = manager.format_info("code-reviewer")
        assert "Code Reviewer" in info


# ---------------------------------------------------------------------------
# Integration: load real agents/ directory
# ---------------------------------------------------------------------------

class TestRealAgentsDirectory:
    """
    Validates that all persona files in the agents/ directory parse correctly
    and the registry indexes them properly.
    """

    @pytest.fixture(scope="class")
    def manager(self):
        src_dir = os.path.dirname(os.path.dirname(__file__))
        agents_dir = os.path.join(src_dir, "agents")
        if not os.path.isdir(agents_dir):
            pytest.skip("agents/ directory not found")
        return AgentPersonaManager(agents_dir=agents_dir)

    def test_at_least_one_persona_loaded(self, manager):
        assert len(manager.registry.list_unique()) > 0

    def test_engineering_division_exists(self, manager):
        eng = manager.registry.list_by_division("engineering")
        assert len(eng) > 0

    def test_all_personas_have_required_fields(self, manager):
        for persona in manager.registry.list_unique():
            assert persona.name, f"Empty name in {persona.filepath}"
            assert persona.slug, f"Empty slug in {persona.filepath}"
            assert persona.division, f"Empty division in {persona.filepath}"
            assert persona.description, f"Empty description in {persona.filepath}"
            assert persona.body, f"Empty body in {persona.filepath}"

    def test_slugs_are_unique(self, manager):
        slugs = [p.slug for p in manager.registry.list_unique()]
        assert len(slugs) == len(set(slugs)), "Duplicate slugs found"

    def test_code_reviewer_available(self, manager):
        p = manager.registry.get("code-reviewer")
        assert p is not None

    def test_qa_specialist_available(self, manager):
        p = manager.registry.get("qa-specialist")
        assert p is not None
