"""
Tests for RewardVerifier — RLVR automated reward computation.
"""

import json

import pytest

from src.reward_verifier import RewardResult, RewardSignal, RewardVerifier


@pytest.fixture
def verifier():
    return RewardVerifier()


class TestRewardSignals:
    def test_json_valid_reward_positive(self, verifier: RewardVerifier):
        """Valid JSON in action gets reward 1.0."""
        result = verifier.compute_reward(
            brigade="Dmarket",
            role="Executor_API",
            action='{"items": [1, 2, 3]}',
            result={},
        )
        json_signals = [s for s in result.signals if s.reward_type == "json_valid"]
        assert len(json_signals) == 1
        assert json_signals[0].value == 1.0

    def test_json_valid_reward_negative(self, verifier: RewardVerifier):
        """Invalid JSON gets reward 0.0."""
        result = verifier.compute_reward(
            brigade="Dmarket",
            role="Executor_API",
            action="not json at all",
            result={},
        )
        json_signals = [s for s in result.signals if s.reward_type == "json_valid"]
        assert len(json_signals) == 1
        assert json_signals[0].value == 0.0

    def test_http_status_200(self, verifier: RewardVerifier):
        """HTTP 200 gets reward 1.0."""
        result = verifier.compute_reward(
            brigade="Dmarket",
            role="Executor_API",
            action="response",
            result={"http_status": 200},
        )
        http_signals = [s for s in result.signals if s.reward_type == "http_status"]
        assert len(http_signals) == 1
        assert http_signals[0].value == 1.0

    def test_http_status_500(self, verifier: RewardVerifier):
        """HTTP 500 gets reward 0.0."""
        result = verifier.compute_reward(
            brigade="Dmarket",
            role="Executor_API",
            action="error",
            result={"http_status": 500},
        )
        http_signals = [s for s in result.signals if s.reward_type == "http_status"]
        assert len(http_signals) == 1
        assert http_signals[0].value == 0.0

    def test_latency_reward_fast(self, verifier: RewardVerifier):
        """Fast response gets high latency reward."""
        result = verifier.compute_reward(
            brigade="Dmarket",
            role="Executor_API",
            action="fast",
            result={"latency_ms": 100},
        )
        latency_signals = [s for s in result.signals if s.reward_type == "latency"]
        assert len(latency_signals) == 1
        assert latency_signals[0].value > 0.9

    def test_latency_reward_slow(self, verifier: RewardVerifier):
        """Very slow response gets low latency reward."""
        result = verifier.compute_reward(
            brigade="Dmarket",
            role="Executor_API",
            action="slow",
            result={"latency_ms": 30000},
        )
        latency_signals = [s for s in result.signals if s.reward_type == "latency"]
        assert len(latency_signals) == 1
        assert latency_signals[0].value < 0.5

    def test_profit_positive(self, verifier: RewardVerifier):
        """Positive profit gets reward 1.0."""
        result = verifier.compute_reward(
            brigade="Dmarket",
            role="Executor_API",
            action="trade",
            result={"profit": 150.0},
        )
        profit_signals = [s for s in result.signals if s.reward_type == "profit_signal"]
        assert len(profit_signals) == 1
        assert profit_signals[0].value == 1.0

    def test_profit_negative(self, verifier: RewardVerifier):
        """Negative profit gets reward 0.0."""
        result = verifier.compute_reward(
            brigade="Dmarket",
            role="Executor_API",
            action="trade",
            result={"profit": -50.0},
        )
        profit_signals = [s for s in result.signals if s.reward_type == "profit_signal"]
        assert len(profit_signals) == 1
        assert profit_signals[0].value == 0.0


class TestOpenClawRewards:
    def test_tool_call_success(self, verifier: RewardVerifier):
        """Successful tool calls get high reward."""
        result = verifier.compute_reward(
            brigade="OpenClaw",
            role="Executor_Tools",
            action="tool output",
            result={
                "tool_results": [
                    {"name": "read_file", "success": True},
                    {"name": "write_file", "success": True},
                    {"name": "list_directory", "success": False},
                ]
            },
        )
        tool_signals = [s for s in result.signals if s.reward_type == "tool_call_success"]
        assert len(tool_signals) == 1
        assert abs(tool_signals[0].value - 0.667) < 0.01

    def test_code_quality_all_pass(self, verifier: RewardVerifier):
        """All quality checks passing gets reward 1.0."""
        result = verifier.compute_reward(
            brigade="OpenClaw",
            role="Executor_Tools",
            action="code",
            result={
                "lint_passed": True,
                "tests_passed": True,
                "typecheck_passed": True,
            },
        )
        quality_signals = [s for s in result.signals if s.reward_type == "code_quality"]
        assert len(quality_signals) == 1
        assert quality_signals[0].value == 1.0

    def test_code_quality_partial(self, verifier: RewardVerifier):
        """Partial quality checks get proportional reward."""
        result = verifier.compute_reward(
            brigade="OpenClaw",
            role="Executor_Tools",
            action="code",
            result={
                "lint_passed": True,
                "tests_passed": False,
                "typecheck_passed": True,
            },
        )
        quality_signals = [s for s in result.signals if s.reward_type == "code_quality"]
        assert len(quality_signals) == 1
        assert abs(quality_signals[0].value - 0.667) < 0.01

    def test_archivist_confidence_from_text(self, verifier: RewardVerifier):
        """Extract confidence from Russian text."""
        result = verifier.compute_reward(
            brigade="OpenClaw",
            role="Archivist",
            action="Отчёт: ... УВЕРЕННОСТЬ: 8/10",
            result={},
        )
        conf_signals = [s for s in result.signals if s.reward_type == "archivist_confidence"]
        assert len(conf_signals) == 1
        assert conf_signals[0].value == 0.8

    def test_response_completeness_short(self, verifier: RewardVerifier):
        """Too-short responses get 0.0."""
        result = verifier.compute_reward(
            brigade="OpenClaw",
            role="Planner",
            action="ok",
            result={},
        )
        comp_signals = [s for s in result.signals if s.reward_type == "response_completeness"]
        assert len(comp_signals) == 1
        assert comp_signals[0].value == 0.0

    def test_response_completeness_truncated(self, verifier: RewardVerifier):
        """Truncated responses get 0.5."""
        result = verifier.compute_reward(
            brigade="OpenClaw",
            role="Planner",
            action="This is a long response with many details about the task..." + "..." * 10,
            result={},
        )
        comp_signals = [s for s in result.signals if s.reward_type == "response_completeness"]
        assert len(comp_signals) == 1
        assert comp_signals[0].value == 0.5


class TestAggregateReward:
    def test_total_reward_in_range(self, verifier: RewardVerifier):
        """Total reward is always in [0.0, 1.0]."""
        result = verifier.compute_reward(
            brigade="Dmarket",
            role="Executor_API",
            action='{"status": "ok"}',
            result={"http_status": 200, "latency_ms": 100, "profit": 100},
        )
        assert 0.0 <= result.total_reward <= 1.0

    def test_batch_compute(self, verifier: RewardVerifier):
        """Batch computation works for multiple interactions."""
        interactions = [
            {
                "brigade": "Dmarket",
                "role": "Executor_API",
                "action": '{"ok": true}',
                "metadata": {"http_status": 200},
            },
            {
                "brigade": "OpenClaw",
                "role": "Planner",
                "action": "Detailed plan with many steps and considerations for the task at hand",
                "metadata": {},
            },
        ]
        results = verifier.batch_compute_rewards(interactions)
        assert len(results) == 2
        assert all(isinstance(r, RewardResult) for r in results)

    def test_custom_reward_registration(self, verifier: RewardVerifier):
        """Custom reward functions can be registered."""

        def custom_fn(action, result, role):
            return RewardSignal("custom", 0.9, 1.0)

        verifier.register_custom_reward("TestBrigade", custom_fn)
        result = verifier.compute_reward(
            brigade="TestBrigade",
            role="Test",
            action="test",
            result={},
        )
        assert any(s.reward_type == "custom" for s in result.signals)
