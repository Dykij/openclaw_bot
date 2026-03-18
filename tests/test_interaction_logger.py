"""
Tests for InteractionLogger — Structured JSONL logging for training data.
"""

import json
import os
import tempfile

import pytest

from src.interaction_logger import InteractionLogger


@pytest.fixture
def logger_dir():
    """Create a temporary directory for test logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def interaction_logger(logger_dir):
    """Create an InteractionLogger instance."""
    return InteractionLogger(log_dir=logger_dir)


class TestInteractionLogger:
    def test_init_creates_directory(self, logger_dir):
        """Logger creates the log directory on init."""
        sub = os.path.join(logger_dir, "subdir")
        logger = InteractionLogger(log_dir=sub)
        assert os.path.isdir(sub)

    def test_log_interaction_creates_file(self, interaction_logger: InteractionLogger):
        """Logging an interaction creates the JSONL file."""
        interaction_logger.log_interaction(
            brigade="OpenClaw",
            role="Planner",
            model="Qwen2.5-14B",
            prompt="Plan a task",
            action="Step 1: ...",
        )
        assert interaction_logger.interactions_path.exists()

    def test_log_interaction_writes_valid_jsonl(self, interaction_logger: InteractionLogger):
        """Each log line is valid JSON."""
        interaction_logger.log_interaction(
            brigade="Dmarket",
            role="Executor_API",
            model="Qwen-Coder-7B",
            prompt="Fetch price data",
            action='{"items": []}',
            next_state="HTTP 200",
            metadata={"latency_ms": 150},
        )

        with open(interaction_logger.interactions_path, "r") as f:
            line = f.readline()
            record = json.loads(line)

        assert record["brigade"] == "Dmarket"
        assert record["role"] == "Executor_API"
        assert record["model"] == "Qwen-Coder-7B"
        assert record["prompt"] == "Fetch price data"
        assert record["action"] == '{"items": []}'
        assert record["next_state"] == "HTTP 200"
        assert record["metadata"]["latency_ms"] == 150
        assert record["has_correction"] is False

    def test_log_interaction_with_correction(self, interaction_logger: InteractionLogger):
        """Corrections are tracked correctly."""
        record = interaction_logger.log_interaction(
            brigade="OpenClaw",
            role="Planner",
            model="Qwen2.5-14B",
            prompt="What should I do?",
            action="Bad answer",
            user_correction="Better answer",
        )
        assert record["has_correction"] is True
        assert record["user_correction"] == "Better answer"

    def test_episode_lifecycle(self, interaction_logger: InteractionLogger):
        """Start → log → end episode lifecycle works."""
        ep_id = interaction_logger.start_episode("OpenClaw", "Test task")
        assert ep_id.startswith("ep_")

        interaction_logger.log_interaction(
            brigade="OpenClaw",
            role="Planner",
            model="Qwen2.5-14B",
            prompt="Plan",
            action="Plan output",
        )
        interaction_logger.log_interaction(
            brigade="OpenClaw",
            role="Executor_Tools",
            model="Qwen-Coder-7B",
            prompt="Execute",
            action="Done",
        )

        summary = interaction_logger.end_episode(
            success=True,
            final_reward=0.85,
            summary="Task completed",
        )

        assert summary["episode_id"] == ep_id
        assert summary["num_steps"] == 2
        assert summary["success"] is True
        assert summary["final_reward"] == 0.85
        assert "Planner" in summary["roles_used"]
        assert "Executor_Tools" in summary["roles_used"]

    def test_log_reward(self, interaction_logger: InteractionLogger):
        """Rewards are logged correctly."""
        record = interaction_logger.log_reward(
            episode_id="ep_123",
            step_index=0,
            reward_type="json_valid",
            reward_value=1.0,
            details={"json_found": True},
        )
        assert record["reward_value"] == 1.0
        assert record["reward_type"] == "json_valid"

    def test_reward_clamped_to_range(self, interaction_logger: InteractionLogger):
        """Rewards are clamped to [0.0, 1.0]."""
        r1 = interaction_logger.log_reward("ep", 0, "test", 1.5)
        r2 = interaction_logger.log_reward("ep", 0, "test", -0.5)
        assert r1["reward_value"] == 1.0
        assert r2["reward_value"] == 0.0

    def test_get_stats(self, interaction_logger: InteractionLogger):
        """Stats are tracked correctly."""
        interaction_logger.log_interaction(
            brigade="OpenClaw", role="Planner", model="m", prompt="p", action="a"
        )
        stats = interaction_logger.get_stats()
        assert stats["total_interactions"] == 1
        assert stats["total_episodes"] == 0

    def test_load_interactions_empty(self, interaction_logger: InteractionLogger):
        """Loading from non-existent file returns empty list."""
        result = interaction_logger.load_interactions()
        assert result == []

    def test_load_interactions_with_filter(self, interaction_logger: InteractionLogger):
        """Loading with brigade filter works."""
        interaction_logger.log_interaction(
            brigade="Dmarket", role="Planner", model="m", prompt="p1", action="a1"
        )
        interaction_logger.log_interaction(
            brigade="OpenClaw", role="Planner", model="m", prompt="p2", action="a2"
        )

        dmarket = interaction_logger.load_interactions(brigade="Dmarket")
        assert len(dmarket) == 1
        assert dmarket[0]["brigade"] == "Dmarket"

    def test_load_episodes_success_filter(self, interaction_logger: InteractionLogger):
        """Loading episodes with success_only filter."""
        # Episode 1: success
        interaction_logger.start_episode("OpenClaw", "Good task")
        interaction_logger.log_interaction(
            brigade="OpenClaw", role="Planner", model="m", prompt="p", action="a"
        )
        interaction_logger.end_episode(success=True, final_reward=0.9)

        # Episode 2: failure
        interaction_logger.start_episode("OpenClaw", "Bad task")
        interaction_logger.log_interaction(
            brigade="OpenClaw", role="Planner", model="m", prompt="p", action="a"
        )
        interaction_logger.end_episode(success=False, final_reward=0.2)

        all_eps = interaction_logger.load_episodes()
        assert len(all_eps) == 2

        success_only = interaction_logger.load_episodes(success_only=True)
        assert len(success_only) == 1
        assert success_only[0]["success"] is True

    def test_end_episode_without_start(self, interaction_logger: InteractionLogger):
        """Ending episode without starting returns empty dict."""
        result = interaction_logger.end_episode()
        assert result == {}
