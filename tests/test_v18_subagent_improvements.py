"""Tests for v18.1 subagent-inspired improvements.

Covers:
- Config: Debugger (Dmarket-Dev) and Doc_Writer (OpenClaw-Core) roles
- Pipeline schemas: validate_doc_writer guardrail, ROLE_GUARDRAILS, TOKEN_BUDGET, TOOL_ELIGIBLE
- AFlow: _BRIGADE_ROLE_SETS, new heuristic chains (debug/docs), _TOOL_CAPABLE_ROLES
- Pipeline utils: _PARALLELIZABLE_ROLES updates
- Agent personas: _ROLE_PERSONA_MAP, get_persona_for_role(), augment_role_prompt()
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest


def _import_aflow():
    """Import _aflow.py directly, bypassing pipeline/__init__.py (needs mcp).

    Uses importlib.util to load _aflow.py and its dependency _lats_search.py
    as standalone modules, mocking the mcp module chain.
    """
    module_name = "src.pipeline._aflow"
    if module_name in sys.modules and hasattr(sys.modules[module_name], "_BRIGADE_ROLE_SETS"):
        return sys.modules[module_name]

    import types

    # Pre-register stub 'mcp' modules if missing
    for m in ["mcp", "mcp.client", "mcp.client.stdio"]:
        if m not in sys.modules:
            mod = types.ModuleType(m)
            if m == "mcp":
                mod.ClientSession = None
                mod.StdioServerParameters = None
            if m == "mcp.client.stdio":
                mod.stdio_client = None
            sys.modules[m] = mod

    # Load _lats_search directly (dependency of _aflow)
    lats_name = "src.pipeline._lats_search"
    if lats_name not in sys.modules:
        lats_path = REPO_ROOT / "src" / "pipeline" / "_lats_search.py"
        spec_lats = importlib.util.spec_from_file_location(lats_name, lats_path)
        lats_mod = importlib.util.module_from_spec(spec_lats)
        sys.modules[lats_name] = lats_mod
        spec_lats.loader.exec_module(lats_mod)

    # Load _aflow directly
    aflow_path = REPO_ROOT / "src" / "pipeline" / "_aflow.py"
    spec = importlib.util.spec_from_file_location(module_name, aflow_path)
    aflow_mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = aflow_mod
    spec.loader.exec_module(aflow_mod)
    return aflow_mod

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "openclaw_config.json"


# ===========================================================================
# Group 1: Config validation
# ===========================================================================

class TestConfigValidation:
    """Verify Debugger and Doc_Writer roles exist in config with correct fields."""

    @pytest.fixture(autouse=True)
    def load_config(self):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            self.config = json.load(f)
        self.brigades = self.config["brigades"]

    def test_config_is_valid_json(self):
        """Config file parses as valid JSON."""
        assert isinstance(self.config, dict)
        assert "brigades" in self.config

    def test_debugger_exists_in_dmarket_dev(self):
        roles = self.brigades["Dmarket-Dev"]["roles"]
        assert "Debugger" in roles

    def test_doc_writer_exists_in_openclaw_core(self):
        roles = self.brigades["OpenClaw-Core"]["roles"]
        assert "Doc_Writer" in roles

    def test_debugger_has_required_fields(self):
        debugger = self.brigades["Dmarket-Dev"]["roles"]["Debugger"]
        for field in ("model", "openrouter_model", "system_prompt", "temperature", "timeout_sec"):
            assert field in debugger, f"Debugger missing field: {field}"

    def test_doc_writer_has_required_fields(self):
        doc_writer = self.brigades["OpenClaw-Core"]["roles"]["Doc_Writer"]
        for field in ("model", "openrouter_model", "system_prompt", "temperature", "timeout_sec"):
            assert field in doc_writer, f"Doc_Writer missing field: {field}"

    def test_debugger_model_is_nemotron(self):
        debugger = self.brigades["Dmarket-Dev"]["roles"]["Debugger"]
        assert "nemotron" in debugger["model"].lower()

    def test_doc_writer_model_is_trinity(self):
        doc_writer = self.brigades["OpenClaw-Core"]["roles"]["Doc_Writer"]
        assert "trinity" in doc_writer["model"].lower()

    def test_debugger_system_prompt_has_domain(self):
        """Debugger prompt should mention debugging domain keywords."""
        prompt = self.brigades["Dmarket-Dev"]["roles"]["Debugger"]["system_prompt"]
        assert any(kw in prompt.lower() for kw in ["debug", "error", "diagnostic", "root_cause"])

    def test_doc_writer_system_prompt_has_domain(self):
        """Doc_Writer prompt should mention documentation domain keywords."""
        prompt = self.brigades["OpenClaw-Core"]["roles"]["Doc_Writer"]["system_prompt"]
        assert any(kw in prompt.lower() for kw in ["readme", "changelog", "doc", "markdown"])


# ===========================================================================
# Group 2: Pipeline schemas
# ===========================================================================

class TestPipelineSchemas:
    """Verify guardrails, token budgets, and tool eligibility for new roles."""

    def test_validate_doc_writer_valid_markdown(self):
        from src.pipeline_schemas import validate_doc_writer
        doc = "## API Reference\n\nThis module provides:\n\n```python\ndef example():\n    pass\n```\n\n- Item 1\n- Item 2"
        ok, msg = validate_doc_writer(doc)
        assert ok is True
        assert msg == ""

    def test_validate_doc_writer_empty_string(self):
        from src.pipeline_schemas import validate_doc_writer
        ok, msg = validate_doc_writer("")
        assert ok is False

    def test_validate_doc_writer_short_string(self):
        from src.pipeline_schemas import validate_doc_writer
        ok, msg = validate_doc_writer("Short text.")
        assert ok is False

    def test_validate_doc_writer_no_doc_markers(self):
        from src.pipeline_schemas import validate_doc_writer
        ok, msg = validate_doc_writer(
            "This is a long enough response but it has no markdown headings or "
            "documentation structure markers at all, just plain text rambling on."
        )
        assert ok is False
        assert "Markdown" in msg or "документац" in msg.lower()

    def test_validate_doc_writer_with_description_keyword(self):
        from src.pipeline_schemas import validate_doc_writer
        ok, msg = validate_doc_writer(
            "Description of the module architecture and its components in detail."
        )
        assert ok is True

    def test_debugger_in_role_guardrails(self):
        from src.pipeline_schemas import ROLE_GUARDRAILS
        assert "Debugger" in ROLE_GUARDRAILS

    def test_doc_writer_in_role_guardrails(self):
        from src.pipeline_schemas import ROLE_GUARDRAILS
        assert "Doc_Writer" in ROLE_GUARDRAILS

    def test_doc_writer_token_budget_is_2048(self):
        from src.pipeline_schemas import ROLE_TOKEN_BUDGET
        assert "Doc_Writer" in ROLE_TOKEN_BUDGET
        assert ROLE_TOKEN_BUDGET["Doc_Writer"] == 2048

    def test_debugger_token_budget_is_2048(self):
        from src.pipeline_schemas import ROLE_TOKEN_BUDGET
        assert "Debugger" in ROLE_TOKEN_BUDGET
        assert ROLE_TOKEN_BUDGET["Debugger"] == 2048

    def test_debugger_in_tool_eligible_roles(self):
        from src.pipeline_schemas import TOOL_ELIGIBLE_ROLES
        assert "Debugger" in TOOL_ELIGIBLE_ROLES

    def test_doc_writer_in_tool_eligible_roles(self):
        from src.pipeline_schemas import TOOL_ELIGIBLE_ROLES
        assert "Doc_Writer" in TOOL_ELIGIBLE_ROLES

    def test_validate_debugger_valid_output(self):
        from src.pipeline_schemas import validate_debugger
        report = "Root cause: asyncio.gather failure. Stack trace shows TimeoutError at line 42. Fix: add return_exceptions=True."
        ok, msg = validate_debugger(report)
        assert ok is True

    def test_validate_debugger_too_short(self):
        from src.pipeline_schemas import validate_debugger
        ok, msg = validate_debugger("OK")
        assert ok is False


# ===========================================================================
# Group 3: AFlow integration
# ===========================================================================

class TestAFlowIntegration:
    """Verify AFlow heuristic chains and brigade role sets include new roles."""

    def test_debugger_in_dmarket_dev_roles(self):
        aflow = _import_aflow()
        assert "Debugger" in aflow._BRIGADE_ROLE_SETS["Dmarket-Dev"]

    def test_doc_writer_in_openclaw_core_roles(self):
        aflow = _import_aflow()
        assert "Doc_Writer" in aflow._BRIGADE_ROLE_SETS["OpenClaw-Core"]

    def test_test_writer_in_openclaw_core_roles(self):
        aflow = _import_aflow()
        assert "Test_Writer" in aflow._BRIGADE_ROLE_SETS["OpenClaw-Core"]

    def test_debugger_in_tool_capable_roles(self):
        aflow = _import_aflow()
        assert "Debugger" in aflow._TOOL_CAPABLE_ROLES

    def test_heuristic_debug_error_prompt(self):
        """Debug-related prompts should match the debug heuristic chain."""
        aflow = _import_aflow()
        prompt = "у меня ошибка в коде, помоги debug"
        matched = False
        for pattern, chain in aflow._HEURISTIC_CHAINS:
            if pattern.search(prompt):
                if "Debugger" in chain:
                    matched = True
                break
        assert matched, "Debug prompt did not match Debugger heuristic chain"

    def test_heuristic_traceback_exception(self):
        """Traceback/exception prompts should match debug chain."""
        aflow = _import_aflow()
        prompt = "traceback exception in my trading bot"
        matched_chain = None
        for pattern, chain in aflow._HEURISTIC_CHAINS:
            if pattern.search(prompt):
                matched_chain = chain
                break
        assert matched_chain is not None
        assert "Debugger" in matched_chain

    def test_heuristic_documentation_readme(self):
        """Documentation prompts should match Doc_Writer chain."""
        aflow = _import_aflow()
        prompt = "обнови документацию readme проекта"
        matched_chain = None
        for pattern, chain in aflow._HEURISTIC_CHAINS:
            if pattern.search(prompt):
                matched_chain = chain
                break
        assert matched_chain is not None
        assert "Doc_Writer" in matched_chain

    def test_heuristic_changelog(self):
        """CHANGELOG prompts should match Doc_Writer chain."""
        aflow = _import_aflow()
        prompt = "write changelog entry for new release"
        matched_chain = None
        for pattern, chain in aflow._HEURISTIC_CHAINS:
            if pattern.search(prompt):
                matched_chain = chain
                break
        assert matched_chain is not None
        assert "Doc_Writer" in matched_chain

    def test_heuristic_trade_still_works(self):
        """Trading prompts should still match the trade chain (no regression)."""
        aflow = _import_aflow()
        prompt = "buy 10 items on dmarket"
        matched_chain = None
        for pattern, chain in aflow._HEURISTIC_CHAINS:
            if pattern.search(prompt):
                matched_chain = chain
                break
        assert matched_chain is not None
        assert "Executor_Tools" in matched_chain

    def test_heuristic_youtube_still_works(self):
        """YouTube URLs should still match Researcher chain (no regression)."""
        aflow = _import_aflow()
        prompt = "summarize https://youtube.com/watch?v=abc123"
        matched_chain = None
        for pattern, chain in aflow._HEURISTIC_CHAINS:
            if pattern.search(prompt):
                matched_chain = chain
                break
        assert matched_chain is not None
        assert "Researcher" in matched_chain

    def test_heuristic_research_still_works(self):
        """Research prompts should still match Researcher chain."""
        aflow = _import_aflow()
        prompt = "найди информацию о Python asyncio"
        matched_chain = None
        for pattern, chain in aflow._HEURISTIC_CHAINS:
            if pattern.search(prompt):
                matched_chain = chain
                break
        assert matched_chain is not None
        assert "Researcher" in matched_chain

    def test_aflow_result_dataclass(self):
        """AFlowResult dataclass can be instantiated."""
        aflow = _import_aflow()
        r = aflow.AFlowResult(chain=["Planner", "Debugger"], source="heuristic", confidence=0.85)
        assert r.chain == ["Planner", "Debugger"]
        assert r.source == "heuristic"
        assert r.confidence == 0.85


# ===========================================================================
# Group 4: Pipeline utils
# ===========================================================================

class TestPipelineUtils:
    """Verify parallelizable roles and cloud chain grouping with new roles."""

    def test_debugger_in_parallelizable_roles(self):
        from src.pipeline_utils import _PARALLELIZABLE_ROLES
        assert "Debugger" in _PARALLELIZABLE_ROLES

    def test_doc_writer_in_parallelizable_roles(self):
        from src.pipeline_utils import _PARALLELIZABLE_ROLES
        assert "Doc_Writer" in _PARALLELIZABLE_ROLES

    def test_summarizer_not_in_parallelizable_roles(self):
        """Summarizer must NOT be parallelized (sequential dependency on Researcher+Analyst)."""
        from src.pipeline_utils import _PARALLELIZABLE_ROLES
        assert "Summarizer" not in _PARALLELIZABLE_ROLES

    def test_group_chain_cloud_debugger_parallel(self):
        """Debugger in a chain should be grouped in a parallel batch."""
        from src.pipeline_utils import group_chain_cloud
        chain = ["Planner", "Debugger", "Coder", "Auditor"]
        groups = group_chain_cloud(chain)
        # Planner solo → (Debugger, Coder) parallel → Auditor solo
        assert groups[0] == ("Planner",)
        assert "Debugger" in groups[1]
        assert "Coder" in groups[1]
        assert groups[-1] == ("Auditor",)

    def test_group_chain_cloud_doc_writer_parallel(self):
        """Doc_Writer in a chain should be grouped in a parallel batch."""
        from src.pipeline_utils import group_chain_cloud
        chain = ["Planner", "Doc_Writer", "Archivist"]
        groups = group_chain_cloud(chain)
        assert groups[0] == ("Planner",)
        # Doc_Writer and Archivist both parallelizable
        assert "Doc_Writer" in groups[1]
        assert "Archivist" in groups[1]

    def test_group_chain_cloud_planner_executor_auditor(self):
        """Classic chain should still group correctly (regression test)."""
        from src.pipeline_utils import group_chain_cloud
        chain = ["Planner", "Executor_Tools", "Executor_Architect", "Auditor"]
        groups = group_chain_cloud(chain)
        assert groups[0] == ("Planner",)
        assert set(groups[1]) == {"Executor_Tools", "Executor_Architect"}
        assert groups[-1] == ("Auditor",)

    def test_group_chain_legacy_executor_grouping(self):
        """Legacy group_chain() should still group Executor_* roles."""
        from src.pipeline_utils import group_chain
        chain = ["Planner", "Executor_Tools", "Executor_Architect", "Auditor"]
        groups = group_chain(chain)
        assert groups[0] == ("Planner",)
        assert set(groups[1]) == {"Executor_Tools", "Executor_Architect"}
        assert groups[-1] == ("Auditor",)


# ===========================================================================
# Group 5: Agent personas integration
# ===========================================================================

class TestAgentPersonas:
    """Verify role-to-persona mapping and prompt augmentation."""

    @pytest.fixture(autouse=True)
    def setup_manager(self):
        from src.agent_personas import AgentPersonaManager
        AgentPersonaManager.reset()
        self.manager = AgentPersonaManager()
        yield
        AgentPersonaManager.reset()

    def test_role_persona_map_has_entries(self):
        from src.agent_personas import _ROLE_PERSONA_MAP
        assert isinstance(_ROLE_PERSONA_MAP, dict)
        assert len(_ROLE_PERSONA_MAP) >= 8

    def test_persona_for_auditor(self):
        persona = self.manager.get_persona_for_role("Auditor")
        assert persona is not None
        assert persona.slug == "security-auditor"

    def test_persona_for_test_writer(self):
        persona = self.manager.get_persona_for_role("Test_Writer")
        assert persona is not None
        assert persona.slug == "qa-engineer"

    def test_persona_for_doc_writer(self):
        persona = self.manager.get_persona_for_role("Doc_Writer")
        assert persona is not None
        assert persona.slug == "technical-writer"

    def test_persona_for_debugger(self):
        persona = self.manager.get_persona_for_role("Debugger")
        assert persona is not None
        assert persona.slug == "code-reviewer"

    def test_persona_for_coder(self):
        persona = self.manager.get_persona_for_role("Coder")
        assert persona is not None
        assert persona.slug == "senior-developer"

    def test_persona_for_unknown_role(self):
        persona = self.manager.get_persona_for_role("UnknownRole")
        assert persona is None

    def test_augment_known_role(self):
        base = "You are a helpful assistant."
        result = self.manager.augment_role_prompt(base, "Auditor")
        assert "[ACTIVE AGENT PERSONA" in result
        assert "security" in result.lower() or "auditor" in result.lower()

    def test_augment_unknown_role_unchanged(self):
        base = "You are a helpful assistant."
        result = self.manager.augment_role_prompt(base, "UnknownRole")
        assert result == base

    def test_singleton_returns_same_instance(self):
        from src.agent_personas import AgentPersonaManager
        m1 = AgentPersonaManager()
        m2 = AgentPersonaManager()
        assert m1 is m2

    def test_reset_clears_singleton(self):
        from src.agent_personas import AgentPersonaManager
        m1 = AgentPersonaManager()
        AgentPersonaManager.reset()
        m2 = AgentPersonaManager()
        # After reset, a new instance is created
        assert m1 is not m2
