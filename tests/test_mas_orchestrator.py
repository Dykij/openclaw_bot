"""Unit tests for MAS Orchestrator."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.mas.orchestrator import (
    AgentOrchestrator,
    AgentDefinition,
    AgentState,
    TaskResult,
)


# ---------------------------------------------------------------------------
# AgentDefinition
# ---------------------------------------------------------------------------
def test_agent_definition_defaults():
    agent = AgentDefinition(
        agent_id="test-1",
        name="Test Agent",
        role="executor",
        system_prompt="You are a test agent.",
        capabilities=["coding", "analysis"],
    )
    assert agent.agent_id == "test-1"
    assert agent.model_tier == "balanced"
    assert agent.timeout_sec == 120
    assert agent.brigade == "OpenClaw"
    assert "coding" in agent.capabilities
    print("[PASS] AgentDefinition defaults")


def test_agent_definition_custom():
    agent = AgentDefinition(
        agent_id="test-2",
        name="Custom Agent",
        role="planner",
        system_prompt="Plan stuff",
        capabilities=["planning"],
        model_tier="premium",
        timeout_sec=300,
        brigade="openclaw",
    )
    assert agent.model_tier == "premium"
    assert agent.timeout_sec == 300
    assert agent.brigade == "openclaw"
    print("[PASS] AgentDefinition custom")


# ---------------------------------------------------------------------------
# AgentState enum
# ---------------------------------------------------------------------------
def test_agent_state_values():
    assert AgentState.IDLE.value == "idle"
    assert AgentState.RUNNING.value == "running"
    assert AgentState.ERROR.value == "error"
    assert AgentState.STOPPED.value == "stopped"
    print("[PASS] AgentState values")


# ---------------------------------------------------------------------------
# TaskResult
# ---------------------------------------------------------------------------
def test_task_result():
    result = TaskResult(
        task_id="task-1",
        agent_id="agent-1",
        status="success",
        output="Done",
        duration_sec=1.5,
    )
    assert result.task_id == "task-1"
    assert result.error == ""
    assert result.duration_sec == 1.5
    print("[PASS] TaskResult")


# ---------------------------------------------------------------------------
# AgentOrchestrator
# ---------------------------------------------------------------------------
def test_orchestrator_register():
    orch = AgentOrchestrator(config={})
    agent = AgentDefinition(
        agent_id="a1",
        name="Agent One",
        role="executor",
        system_prompt="Do things",
        capabilities=["coding"],
    )
    orch.register_agent(agent)
    assert "a1" in orch._agents
    assert orch._agents["a1"].state == AgentState.IDLE
    print("[PASS] register_agent")


def test_orchestrator_unregister():
    orch = AgentOrchestrator(config={})
    agent = AgentDefinition(
        agent_id="a2",
        name="Agent Two",
        role="executor",
        system_prompt="Do more",
        capabilities=["analysis"],
    )
    orch.register_agent(agent)
    orch.unregister_agent("a2")
    assert "a2" not in orch._agents
    print("[PASS] unregister_agent")


def test_orchestrator_select_agent():
    orch = AgentOrchestrator(config={})
    agent_a = AgentDefinition(
        agent_id="coder",
        name="Coder",
        role="executor",
        system_prompt="Code",
        capabilities=["coding", "debugging"],
    )
    agent_b = AgentDefinition(
        agent_id="analyst",
        name="Analyst",
        role="executor",
        system_prompt="Analyze",
        capabilities=["analysis", "reporting"],
    )
    orch.register_agent(agent_a)
    orch.register_agent(agent_b)

    selected = orch._select_agent("coding")
    assert selected is not None
    assert selected.definition.agent_id == "coder"

    selected2 = orch._select_agent("reporting")
    assert selected2 is not None
    assert selected2.definition.agent_id == "analyst"

    # Capability not registered
    selected3 = orch._select_agent("nonexistent_capability")
    # Should fallback to first available agent
    assert selected3 is not None
    print("[PASS] _select_agent")


def test_orchestrator_dispatch_no_agents():
    orch = AgentOrchestrator(config={})
    result = asyncio.run(orch.dispatch("coding", "Write a test"))
    assert result.status == "failed"
    assert "No" in (result.error or "") and "agent" in (result.error or "").lower()
    print("[PASS] dispatch no agents")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_agent_definition_defaults()
    test_agent_definition_custom()
    test_agent_state_values()
    test_task_result()
    test_orchestrator_register()
    test_orchestrator_unregister()
    test_orchestrator_select_agent()
    test_orchestrator_dispatch_no_agents()
    print("\n✅ All MAS orchestrator tests passed!")
