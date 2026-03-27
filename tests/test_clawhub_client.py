"""Unit tests for ClawHub client."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.clawhub.client import ClawHubClient, ClawHubTask, ClawHubSkill


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
def test_clawhub_task():
    task = ClawHubTask(
        task_id="t-1",
        title="Test Task",
        description="Do something",
        task_type="coding",
        priority=5,
    )
    assert task.task_id == "t-1"
    assert task.task_type == "coding"
    assert task.priority == 5
    assert task.payload == {}
    print("[PASS] ClawHubTask")


def test_clawhub_skill():
    skill = ClawHubSkill(
        name="code-gen",
        description="Generate code",
        capabilities=["python", "typescript"],
        model_tier="premium",
        max_concurrent=2,
    )
    assert skill.name == "code-gen"
    assert len(skill.capabilities) == 2
    assert skill.max_concurrent == 2
    print("[PASS] ClawHubSkill")


# ---------------------------------------------------------------------------
# Client init (no network)
# ---------------------------------------------------------------------------
def test_client_init_defaults():
    client = ClawHubClient()
    assert not client.is_connected
    status = client.get_status()
    assert status["connected"] is False
    assert status["agent_id"] == "openclaw-bot"
    print("[PASS] ClawHubClient default init")


def test_client_init_custom():
    client = ClawHubClient(
        base_url="https://custom.api.com",
        api_key="test-key-123",
        agent_id="my-agent",
        timeout_sec=60,
        max_retries=5,
    )
    status = client.get_status()
    assert status["agent_id"] == "my-agent"
    assert status["has_api_key"] is True
    assert status["base_url"] == "https://custom.api.com"
    print("[PASS] ClawHubClient custom init")


def test_client_no_key_returns_false():
    """Initialize without API key should return False."""
    client = ClawHubClient(api_key="")
    result = asyncio.run(client.initialize())
    assert result is False
    assert not client.is_connected
    print("[PASS] no API key → initialize returns False")


def test_poll_tasks_not_connected():
    """Polling tasks when not connected returns empty list."""
    client = ClawHubClient()
    tasks = asyncio.run(client.poll_tasks())
    assert tasks == []
    print("[PASS] poll_tasks not connected → empty")


def test_submit_result_not_connected():
    """Submitting result when not connected returns False."""
    client = ClawHubClient()
    result = asyncio.run(client.submit_result("t-1", "done"))
    assert result is False
    print("[PASS] submit_result not connected → False")


def test_heartbeat_not_connected():
    """Heartbeat when not connected returns False."""
    client = ClawHubClient()
    result = asyncio.run(client.send_heartbeat())
    assert result is False
    print("[PASS] heartbeat not connected → False")


def test_register_skills_not_connected():
    """Registering skills when not connected returns False."""
    client = ClawHubClient()
    skills = [ClawHubSkill("s1", "desc", ["cap1"])]
    result = asyncio.run(client.register_skills(skills))
    assert result is False
    print("[PASS] register_skills not connected → False")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_clawhub_task()
    test_clawhub_skill()
    test_client_init_defaults()
    test_client_init_custom()
    test_client_no_key_returns_false()
    test_poll_tasks_not_connected()
    test_submit_result_not_connected()
    test_heartbeat_not_connected()
    test_register_skills_not_connected()
    print("\n✅ All ClawHub client tests passed!")
