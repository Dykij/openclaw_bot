"""Smoke test: verify critical imports resolve without errors."""


def test_critical_imports():
    from src.openrouter_client import call_openrouter, check_openrouter
    from src.core.agent_personas import AgentPersonaManager
    from src.pipeline._core import PipelineExecutor
    from src.bot_commands import cmd_agents, cmd_agent, cmd_openrouter_test
    from src.pipeline_schemas import ROLE_GUARDRAILS, ROLE_TOKEN_BUDGET
    from src.core.intent_classifier import classify_intent
    from src.pipeline_utils import clean_response_for_user

    assert callable(call_openrouter)
    assert callable(check_openrouter)
    assert AgentPersonaManager is not None
    assert PipelineExecutor is not None
    assert callable(cmd_agents)
    assert callable(cmd_agent)
    assert callable(cmd_openrouter_test)
    assert isinstance(ROLE_GUARDRAILS, dict)
    assert isinstance(ROLE_TOKEN_BUDGET, dict)
    assert callable(classify_intent)
    assert callable(clean_response_for_user)
