"""
Brigade: OpenClaw
Role: Reward Verifier (RLVR — Reinforcement Learning with Verifiable Rewards)

Implements automated reward computation for agent actions using verifiable signals.
Source: DeepSeek-R1 (arXiv:2501.12948) — RLVR concept.

Reward types:
- JSON validity: Is the output valid JSON?
- Tool call success: Did MCP tool calls execute without errors?
- HTTP status: Did API calls return 200?
- SQL result: Did database queries return expected results?
- Lint pass: Did code pass linter checks?
- Latency: Was the response within acceptable time?
- Archivist confidence: Did the Archivist rate the response highly?

Zero VRAM overhead — pure verification logic, no model inference.
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class RewardSignal:
    """A single reward signal from verification."""

    reward_type: str
    value: float  # [0.0, 1.0]
    weight: float  # Importance weight for aggregation
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RewardResult:
    """Aggregate reward result for an action."""

    total_reward: float
    signals: List[RewardSignal]
    brigade: str
    role: str
    details: Dict[str, Any] = field(default_factory=dict)


class RewardVerifier:
    """
    Automated reward computation using verifiable signals (RLVR).

    No human annotation needed — rewards are computed from objective,
    verifiable signals like JSON validity, tool call success, HTTP status, etc.

    Source: DeepSeek-R1 (arXiv:2501.12948) — RLVR concept.
    """

    def __init__(self):
        # Custom reward functions per brigade
        self._brigade_rewards: Dict[str, List[Callable]] = {}
        self._register_default_rewards()

        logger.info("reward_verifier_initialized")

    def _register_default_rewards(self) -> None:
        """Register default reward functions for each brigade."""
        self._brigade_rewards["Dmarket"] = [
            self._reward_json_valid,
            self._reward_http_status,
            self._reward_latency,
            self._reward_has_required_fields,
            self._reward_profit_signal,
        ]
        self._brigade_rewards["OpenClaw"] = [
            self._reward_json_valid,
            self._reward_tool_call_success,
            self._reward_code_quality,
            self._reward_archivist_confidence,
            self._reward_response_completeness,
        ]

    def compute_reward(
        self,
        brigade: str,
        role: str,
        action: str,
        result: Dict[str, Any],
    ) -> RewardResult:
        """
        Compute aggregate reward for an agent action.

        Args:
            brigade: Brigade name (Dmarket, OpenClaw)
            role: Role name (Planner, Executor_API, etc.)
            action: The agent's output/response
            result: Environment feedback dict with metadata

        Returns:
            RewardResult with total_reward and individual signals.
        """
        reward_fns = self._brigade_rewards.get(brigade, self._brigade_rewards.get("OpenClaw", []))
        signals: List[RewardSignal] = []

        for fn in reward_fns:
            try:
                signal = fn(action=action, result=result, role=role)
                if signal is not None:
                    signals.append(signal)
            except Exception as e:
                logger.warning("reward_function_error", fn=fn.__name__, error=str(e))

        # Compute weighted average
        total_weight = sum(s.weight for s in signals)
        total_reward = (
            sum(s.value * s.weight for s in signals) / total_weight
            if total_weight > 0
            else 0.0
        )
        total_reward = max(0.0, min(1.0, total_reward))

        reward_result = RewardResult(
            total_reward=round(total_reward, 4),
            signals=signals,
            brigade=brigade,
            role=role,
            details={
                "num_signals": len(signals),
                "signal_types": [s.reward_type for s in signals],
            },
        )

        logger.debug(
            "reward_computed",
            brigade=brigade,
            role=role,
            total_reward=reward_result.total_reward,
            num_signals=len(signals),
        )

        return reward_result

    # --- Dmarket Brigade Rewards ---

    @staticmethod
    def _reward_json_valid(
        action: str, result: Dict[str, Any], role: str
    ) -> Optional[RewardSignal]:
        """Reward for valid JSON output."""
        try:
            # Try to find JSON in the action
            json_match = re.search(r"\{.*\}", action, re.DOTALL)
            if json_match:
                json.loads(json_match.group())
                return RewardSignal(
                    reward_type="json_valid",
                    value=1.0,
                    weight=0.3,
                    details={"json_found": True},
                )
            # Check if action itself is valid JSON
            json.loads(action)
            return RewardSignal(
                reward_type="json_valid",
                value=1.0,
                weight=0.3,
                details={"json_found": True},
            )
        except (json.JSONDecodeError, ValueError):
            return RewardSignal(
                reward_type="json_valid",
                value=0.0,
                weight=0.3,
                details={"json_found": False},
            )

    @staticmethod
    def _reward_http_status(
        action: str, result: Dict[str, Any], role: str
    ) -> Optional[RewardSignal]:
        """Reward for successful HTTP status in result."""
        status = result.get("http_status")
        if status is None:
            return None
        value = 1.0 if 200 <= status < 300 else 0.0
        return RewardSignal(
            reward_type="http_status",
            value=value,
            weight=0.25,
            details={"status": status},
        )

    @staticmethod
    def _reward_latency(
        action: str, result: Dict[str, Any], role: str
    ) -> Optional[RewardSignal]:
        """Reward for low latency responses (< 2s for Dmarket, < 10s for general)."""
        latency_ms = result.get("latency_ms")
        if latency_ms is None:
            return None

        threshold_ms = 2000 if role.startswith("Executor") else 10000
        if latency_ms <= threshold_ms:
            # Linear reward: 1.0 at 0ms, 0.5 at threshold
            value = max(0.5, 1.0 - (latency_ms / (threshold_ms * 2)))
        else:
            value = max(0.0, 0.5 - (latency_ms - threshold_ms) / (threshold_ms * 4))

        return RewardSignal(
            reward_type="latency",
            value=round(value, 3),
            weight=0.2,
            details={"latency_ms": latency_ms, "threshold_ms": threshold_ms},
        )

    @staticmethod
    def _reward_has_required_fields(
        action: str, result: Dict[str, Any], role: str
    ) -> Optional[RewardSignal]:
        """Reward for having required fields in JSON response."""
        required = result.get("required_fields")
        if not required:
            return None

        try:
            json_match = re.search(r"\{.*\}", action, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                found = sum(1 for f in required if f in parsed)
                value = found / len(required)
                return RewardSignal(
                    reward_type="required_fields",
                    value=round(value, 3),
                    weight=0.25,
                    details={"required": required, "found": found, "total": len(required)},
                )
        except (json.JSONDecodeError, ValueError):
            pass

        return RewardSignal(
            reward_type="required_fields",
            value=0.0,
            weight=0.25,
            details={"required": required, "found": 0},
        )

    @staticmethod
    def _reward_profit_signal(
        action: str, result: Dict[str, Any], role: str
    ) -> Optional[RewardSignal]:
        """Reward for positive profit signal (Dmarket trading)."""
        profit = result.get("profit")
        if profit is None:
            return None
        value = 1.0 if profit > 0 else (0.5 if profit == 0 else 0.0)
        return RewardSignal(
            reward_type="profit_signal",
            value=value,
            weight=0.3,
            details={"profit": profit},
        )

    # --- OpenClaw Brigade Rewards ---

    @staticmethod
    def _reward_tool_call_success(
        action: str, result: Dict[str, Any], role: str
    ) -> Optional[RewardSignal]:
        """Reward for successful tool/MCP calls."""
        tool_results = result.get("tool_results", [])
        if not tool_results:
            return None

        success_count = sum(1 for t in tool_results if t.get("success", False))
        total = len(tool_results)
        value = success_count / total if total > 0 else 0.0

        return RewardSignal(
            reward_type="tool_call_success",
            value=round(value, 3),
            weight=0.4,
            details={"success": success_count, "total": total},
        )

    @staticmethod
    def _reward_code_quality(
        action: str, result: Dict[str, Any], role: str
    ) -> Optional[RewardSignal]:
        """Reward for code quality signals (lint pass, typecheck, tests)."""
        lint = result.get("lint_passed")
        tests = result.get("tests_passed")
        typecheck = result.get("typecheck_passed")

        if lint is None and tests is None and typecheck is None:
            return None

        scores = []
        if lint is not None:
            scores.append(1.0 if lint else 0.0)
        if tests is not None:
            scores.append(1.0 if tests else 0.0)
        if typecheck is not None:
            scores.append(1.0 if typecheck else 0.0)

        value = sum(scores) / len(scores) if scores else 0.0

        return RewardSignal(
            reward_type="code_quality",
            value=round(value, 3),
            weight=0.3,
            details={
                "lint_passed": lint,
                "tests_passed": tests,
                "typecheck_passed": typecheck,
            },
        )

    @staticmethod
    def _reward_archivist_confidence(
        action: str, result: Dict[str, Any], role: str
    ) -> Optional[RewardSignal]:
        """Reward based on Archivist's confidence score."""
        confidence = result.get("archivist_confidence")
        if confidence is None:
            # Try to extract from action text
            match = re.search(r"УВЕРЕННОСТЬ[:\s]*(\d+)/10", action)
            if match:
                confidence = int(match.group(1)) / 10.0

        if confidence is None:
            return None

        return RewardSignal(
            reward_type="archivist_confidence",
            value=round(min(1.0, max(0.0, confidence)), 3),
            weight=0.15,
            details={"confidence": confidence},
        )

    @staticmethod
    def _reward_response_completeness(
        action: str, result: Dict[str, Any], role: str
    ) -> Optional[RewardSignal]:
        """Reward for complete, non-truncated responses."""
        if not action or len(action.strip()) < 10:
            return RewardSignal(
                reward_type="response_completeness",
                value=0.0,
                weight=0.1,
                details={"reason": "too_short"},
            )

        # Check for common truncation indicators
        truncation_markers = ["...", "[truncated]", "[cut off]", "продолжение следует"]
        is_truncated = any(marker in action[-100:] for marker in truncation_markers)

        return RewardSignal(
            reward_type="response_completeness",
            value=0.5 if is_truncated else 1.0,
            weight=0.1,
            details={"truncated": is_truncated, "length": len(action)},
        )

    def register_custom_reward(
        self,
        brigade: str,
        reward_fn: Callable,
    ) -> None:
        """Register a custom reward function for a brigade."""
        if brigade not in self._brigade_rewards:
            self._brigade_rewards[brigade] = []
        self._brigade_rewards[brigade].append(reward_fn)
        logger.info("custom_reward_registered", brigade=brigade, fn=reward_fn.__name__)

    def batch_compute_rewards(
        self,
        interactions: List[Dict[str, Any]],
    ) -> List[RewardResult]:
        """
        Compute rewards for a batch of interactions.

        Args:
            interactions: List of interaction records from InteractionLogger

        Returns:
            List of RewardResult for each interaction.
        """
        results = []
        for interaction in interactions:
            result = self.compute_reward(
                brigade=interaction.get("brigade", "OpenClaw"),
                role=interaction.get("role", "Unknown"),
                action=interaction.get("action", ""),
                result=interaction.get("metadata", {}),
            )
            results.append(result)
        return results
