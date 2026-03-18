"""
Brigade: OpenClaw
Role: Interaction Logger (Structured JSONL Logging for Training)

Implements Unified Interaction Signals from OpenClaw-RL (arXiv:2603.10165).
Every agent interaction generates a next-state signal that can be used for training:
- (action, next_state, user_correction) tuples in JSONL format
- Evaluative signals (scalar rewards via PRM Judge)
- Directive signals (token-level feedback via OPD)

Zero VRAM overhead — pure logging, no model inference.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

# Default paths
DEFAULT_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "training_data")
DEFAULT_INTERACTIONS_FILE = "interactions.jsonl"
DEFAULT_EPISODES_FILE = "episodes.jsonl"
DEFAULT_REWARDS_FILE = "rewards.jsonl"


class InteractionLogger:
    """
    Structured interaction logger for training data collection.

    Logs every agent interaction as a JSONL record containing:
    - timestamp: ISO 8601
    - brigade: Dmarket | OpenClaw
    - role: Planner, Executor_API, Archivist, etc.
    - model: model name used for inference
    - action: the agent's output/response
    - prompt: the input prompt
    - next_state: environment feedback (tool output, user reply, etc.)
    - user_correction: if user corrected the response (None if no correction)
    - metadata: latency_ms, token_count, tool_calls, etc.

    Source: OpenClaw-RL (arXiv:2603.10165) — Unified Interaction Signals
    """

    def __init__(self, log_dir: Optional[str] = None, max_file_size_mb: int = 100):
        self.log_dir = Path(log_dir or DEFAULT_LOG_DIR)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

        # Current episode tracking
        self._current_episode: List[Dict[str, Any]] = []
        self._episode_id: str = ""
        self._episode_start_time: float = 0.0

        # Stats
        self._total_interactions: int = 0
        self._total_episodes: int = 0

        logger.info(
            "interaction_logger_initialized",
            log_dir=str(self.log_dir),
            max_file_size_mb=max_file_size_mb,
        )

    @property
    def interactions_path(self) -> Path:
        return self.log_dir / DEFAULT_INTERACTIONS_FILE

    @property
    def episodes_path(self) -> Path:
        return self.log_dir / DEFAULT_EPISODES_FILE

    @property
    def rewards_path(self) -> Path:
        return self.log_dir / DEFAULT_REWARDS_FILE

    def _rotate_if_needed(self, filepath: Path) -> None:
        """Rotate log file if it exceeds max size."""
        if filepath.exists() and filepath.stat().st_size > self.max_file_size_bytes:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            rotated = filepath.with_suffix(f".{ts}.jsonl")
            filepath.rename(rotated)
            logger.info("log_file_rotated", original=str(filepath), rotated=str(rotated))

    def log_interaction(
        self,
        brigade: str,
        role: str,
        model: str,
        prompt: str,
        action: str,
        next_state: Optional[str] = None,
        user_correction: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Log a single agent interaction.

        Args:
            brigade: Brigade name (Dmarket, OpenClaw)
            role: Role name (Planner, Executor_API, Archivist, etc.)
            model: Model used for inference
            prompt: Input prompt to the agent
            action: Agent's output/response
            next_state: Environment feedback (tool output, user reply)
            user_correction: User's correction if any
            metadata: Additional info (latency_ms, token_count, tool_calls)

        Returns:
            The logged record as a dict.
        """
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "epoch_ms": int(time.time() * 1000),
            "brigade": brigade,
            "role": role,
            "model": model,
            "prompt": prompt,
            "action": action,
            "next_state": next_state,
            "user_correction": user_correction,
            "has_correction": user_correction is not None,
            "metadata": metadata or {},
        }

        # Add to current episode if one is active
        if self._episode_id:
            record["episode_id"] = self._episode_id
            record["step_index"] = len(self._current_episode)
            self._current_episode.append(record)

        # Write to JSONL file
        self._rotate_if_needed(self.interactions_path)
        with open(self.interactions_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        self._total_interactions += 1

        logger.debug(
            "interaction_logged",
            brigade=brigade,
            role=role,
            model=model,
            has_correction=record["has_correction"],
            total=self._total_interactions,
        )

        return record

    def start_episode(self, brigade: str, task_description: str = "") -> str:
        """
        Start a new episode (a sequence of related interactions).

        Returns:
            Episode ID string.
        """
        self._episode_id = f"ep_{int(time.time() * 1000)}_{brigade}"
        self._episode_start_time = time.time()
        self._current_episode = []

        logger.info(
            "episode_started",
            episode_id=self._episode_id,
            brigade=brigade,
            task=task_description[:200],
        )

        return self._episode_id

    def end_episode(
        self,
        success: bool = True,
        final_reward: float = 0.0,
        summary: str = "",
    ) -> Dict[str, Any]:
        """
        End the current episode and write episode summary.

        Args:
            success: Whether the episode achieved its goal
            final_reward: Aggregate reward for the episode
            summary: Human-readable summary

        Returns:
            Episode summary record.
        """
        if not self._episode_id:
            logger.warning("end_episode_called_without_active_episode")
            return {}

        duration_s = time.time() - self._episode_start_time
        episode_record = {
            "episode_id": self._episode_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "num_steps": len(self._current_episode),
            "duration_s": round(duration_s, 2),
            "success": success,
            "final_reward": final_reward,
            "summary": summary,
            "roles_used": list({s.get("role", "") for s in self._current_episode}),
            "models_used": list({s.get("model", "") for s in self._current_episode}),
            "corrections_count": sum(
                1 for s in self._current_episode if s.get("has_correction")
            ),
        }

        # Write episode summary
        self._rotate_if_needed(self.episodes_path)
        with open(self.episodes_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(episode_record, ensure_ascii=False) + "\n")

        self._total_episodes += 1

        logger.info(
            "episode_ended",
            episode_id=self._episode_id,
            steps=episode_record["num_steps"],
            success=success,
            reward=final_reward,
            duration_s=episode_record["duration_s"],
        )

        # Reset episode state
        old_id = self._episode_id
        self._episode_id = ""
        self._current_episode = []
        self._episode_start_time = 0.0

        return episode_record

    def log_reward(
        self,
        episode_id: str,
        step_index: int,
        reward_type: str,
        reward_value: float,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Log a reward signal for a specific interaction step.

        Args:
            episode_id: Episode this reward belongs to
            step_index: Step index within the episode
            reward_type: Type of reward (json_valid, tool_success, latency, etc.)
            reward_value: Scalar reward value [0.0, 1.0]
            details: Additional reward details

        Returns:
            The reward record.
        """
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "episode_id": episode_id,
            "step_index": step_index,
            "reward_type": reward_type,
            "reward_value": max(0.0, min(1.0, reward_value)),
            "details": details or {},
        }

        self._rotate_if_needed(self.rewards_path)
        with open(self.rewards_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return record

    def get_stats(self) -> Dict[str, Any]:
        """Return logging statistics."""
        return {
            "total_interactions": self._total_interactions,
            "total_episodes": self._total_episodes,
            "log_dir": str(self.log_dir),
            "interactions_file_size_mb": round(
                self.interactions_path.stat().st_size / (1024 * 1024), 2
            )
            if self.interactions_path.exists()
            else 0,
            "active_episode": self._episode_id or None,
        }

    def load_interactions(
        self,
        brigade: Optional[str] = None,
        role: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Load interactions from JSONL file with optional filters.

        Args:
            brigade: Filter by brigade name
            role: Filter by role name
            limit: Maximum number of records to return

        Returns:
            List of interaction records.
        """
        results: List[Dict[str, Any]] = []
        if not self.interactions_path.exists():
            return results

        with open(self.interactions_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if brigade and record.get("brigade") != brigade:
                    continue
                if role and record.get("role") != role:
                    continue

                results.append(record)
                if len(results) >= limit:
                    break

        return results

    def load_episodes(
        self,
        success_only: bool = False,
        min_reward: float = 0.0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Load episode summaries with optional filters.

        Args:
            success_only: Only return successful episodes
            min_reward: Minimum reward threshold
            limit: Maximum episodes to return

        Returns:
            List of episode records.
        """
        results: List[Dict[str, Any]] = []
        if not self.episodes_path.exists():
            return results

        with open(self.episodes_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if success_only and not record.get("success"):
                    continue
                if record.get("final_reward", 0) < min_reward:
                    continue

                results.append(record)
                if len(results) >= limit:
                    break

        return results
