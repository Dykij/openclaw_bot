"""
Brigade: OpenClaw
Role: Experience Buffer for ExGRPO Training

Implements a prioritized experience replay buffer for Experience-augmented
Group Relative Policy Optimization (ExGRPO). Stores past successful and failed
reasoning trajectories for contrastive learning and self-correction training.

Research sources:
- ExGRPO: Learning to Reason from Experience (2026)
- Self-Distillation for RL (2026)
- Training Language Models to Self-Correct via RL (arXiv:2409.12917)

Design principles:
- Zero VRAM overhead: pure CPU/disk, no GPU tensors
- Thread-safe with asyncio lock for concurrent access
- Reservoir sampling to maintain fixed buffer size
- Prioritized replay based on reward variance (high-variance = most informative)
- JSONL persistence for crash recovery and offline analysis

Usage:
    buffer = ExperienceBuffer(max_size=10000)
    await buffer.load()

    # Add experience from training
    await buffer.add_experience(prompt, completion, reward, metadata)

    # Sample for GRPO training
    batch = await buffer.sample_batch(batch_size=16, temperature=1.0)

    # Get contrastive pairs for a prompt
    pairs = await buffer.get_contrastive_pairs(prompt, k=4)

    # Self-correction loop (arXiv:2409.12917)
    correction = await buffer.generate_correction_pair(prompt, response, reward)

    # Persistence
    await buffer.save()
"""

import asyncio
import json
import math
import os
import random
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_BUFFER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "training_data", "experience_buffer.jsonl"
)


@dataclass
class Experience:
    """A single experience entry in the buffer.

    Stores a (prompt, completion, reward) tuple along with trajectory metadata
    for prioritized replay and contrastive learning.
    """

    prompt: str
    completion: str
    reward: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Tracking fields
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    was_corrected: bool = False
    correction_of: Optional[str] = None  # ID of the experience this corrects
    experience_id: str = field(default_factory=lambda: f"exp_{uuid.uuid4().hex[:16]}")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSONL storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Experience":
        """Deserialize from dictionary."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class ExperienceBufferConfig:
    """Configuration for the experience buffer."""

    max_size: int = 10000
    buffer_path: str = DEFAULT_BUFFER_PATH
    min_reward_for_positive: float = 0.6
    max_reward_for_negative: float = 0.3
    correction_reward_threshold: float = 0.4
    seed: Optional[int] = None


class ExperienceBuffer:
    """
    Prioritized experience replay buffer for ExGRPO training.

    Stores past reasoning trajectories and supports:
    - Prioritized sampling based on reward variance (high-variance examples
      are most informative for contrastive GRPO learning)
    - Reservoir sampling to maintain a fixed buffer size while giving
      every incoming experience a fair chance of inclusion
    - Temperature-based sampling for exploration control
    - Contrastive pair extraction for GRPO advantage computation
    - Self-correction tracking (arXiv:2409.12917)
    - JSONL disk persistence for crash recovery

    Zero VRAM overhead — all operations are CPU/disk only.
    """

    def __init__(self, config: Optional[ExperienceBufferConfig] = None, **kwargs: Any) -> None:
        if config is not None:
            self._config = config
        else:
            self._config = ExperienceBufferConfig(**kwargs)

        self._buffer: List[Experience] = []
        self._prompt_index: Dict[str, List[int]] = defaultdict(list)
        self._total_seen: int = 0
        self._lock = asyncio.Lock()
        self._rng = random.Random(self._config.seed)
        self._dirty = False

        logger.info(
            "experience_buffer_init",
            max_size=self._config.max_size,
            buffer_path=self._config.buffer_path,
        )

    @property
    def size(self) -> int:
        """Current number of experiences in the buffer."""
        return len(self._buffer)

    @property
    def total_seen(self) -> int:
        """Total number of experiences ever added (including evicted)."""
        return self._total_seen

    # ------------------------------------------------------------------
    # Core: add / sample / contrastive pairs
    # ------------------------------------------------------------------

    async def add_experience(
        self,
        prompt: str,
        completion: str,
        reward: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Experience:
        """Add a new experience to the buffer.

        Uses reservoir sampling (Vitter's Algorithm R) so that when the buffer
        is full, every experience ever seen has an equal probability of being
        retained, regardless of arrival order.
        """
        exp = Experience(
            prompt=prompt,
            completion=completion,
            reward=reward,
            metadata=metadata or {},
        )

        async with self._lock:
            self._total_seen += 1

            if len(self._buffer) < self._config.max_size:
                idx = len(self._buffer)
                self._buffer.append(exp)
                self._prompt_index[prompt].append(idx)
            else:
                # Reservoir sampling: replace a random existing entry
                j = self._rng.randint(0, self._total_seen - 1)
                if j < self._config.max_size:
                    old = self._buffer[j]
                    # Remove old entry from prompt index
                    old_indices = self._prompt_index.get(old.prompt, [])
                    if j in old_indices:
                        old_indices.remove(j)
                    if not old_indices:
                        self._prompt_index.pop(old.prompt, None)

                    self._buffer[j] = exp
                    self._prompt_index[prompt].append(j)

            self._dirty = True

        logger.debug(
            "experience_added",
            experience_id=exp.experience_id,
            reward=reward,
            buffer_size=len(self._buffer),
            total_seen=self._total_seen,
        )
        return exp

    async def sample_batch(
        self,
        batch_size: int,
        temperature: float = 1.0,
    ) -> List[Experience]:
        """Sample a training batch with prioritized replay.

        Priority is based on reward variance per prompt: experiences from
        prompts with high reward variance are the most informative for GRPO
        contrastive learning (they contain both good and bad completions).

        Args:
            batch_size: Number of experiences to sample.
            temperature: Sampling temperature. Higher values increase
                exploration (flatter distribution); lower values concentrate
                on high-priority experiences. At temperature=0 returns top-k.
        """
        async with self._lock:
            if not self._buffer:
                return []

            actual_size = min(batch_size, len(self._buffer))
            priorities = self._compute_priorities()

            if temperature <= 0.0:
                # Greedy: pick highest priority
                top_indices = sorted(
                    range(len(priorities)),
                    key=lambda i: priorities[i],
                    reverse=True,
                )[:actual_size]
                sampled = [self._buffer[i] for i in top_indices]
            else:
                # Temperature-scaled softmax sampling
                weights = self._apply_temperature(priorities, temperature)
                indices = self._weighted_sample_without_replacement(
                    weights, actual_size,
                )
                sampled = [self._buffer[i] for i in indices]

            # Track access
            for exp in sampled:
                exp.access_count += 1

        logger.debug(
            "batch_sampled",
            batch_size=len(sampled),
            temperature=temperature,
        )
        return sampled

    async def get_contrastive_pairs(
        self,
        prompt: str,
        k: int = 4,
    ) -> List[Tuple[Experience, Experience]]:
        """Get best/worst completion pairs for the same prompt.

        Returns up to k pairs of (positive, negative) experiences where
        positive.reward > negative.reward. These contrastive pairs are
        the core training signal for GRPO.

        Args:
            prompt: The prompt to find contrastive pairs for.
            k: Maximum number of pairs to return.
        """
        async with self._lock:
            indices = self._prompt_index.get(prompt, [])
            if len(indices) < 2:
                return []

            experiences = [self._buffer[i] for i in indices]

        # Sort by reward descending
        experiences.sort(key=lambda e: e.reward, reverse=True)

        positives = [
            e for e in experiences
            if e.reward >= self._config.min_reward_for_positive
        ]
        negatives = [
            e for e in experiences
            if e.reward <= self._config.max_reward_for_negative
        ]

        pairs: List[Tuple[Experience, Experience]] = []
        for pos in positives:
            for neg in negatives:
                if len(pairs) >= k:
                    break
                pairs.append((pos, neg))
            if len(pairs) >= k:
                break

        # If strict thresholds yield fewer than k, fall back to top/bottom split
        if len(pairs) < k and len(experiences) >= 2:
            mid = len(experiences) // 2
            top_half = experiences[:mid]
            bottom_half = experiences[mid:]
            for pos in top_half:
                for neg in bottom_half:
                    if len(pairs) >= k:
                        break
                    if (pos, neg) not in pairs:
                        pairs.append((pos, neg))
                if len(pairs) >= k:
                    break

        logger.debug(
            "contrastive_pairs",
            prompt_len=len(prompt),
            num_experiences=len(experiences),
            num_pairs=len(pairs),
        )
        return pairs[:k]

    async def compute_experience_advantages(
        self,
        batch: List[Dict[str, Any]],
    ) -> List[float]:
        """Compute advantages using both current batch and historical rewards.

        Extends standard GRPO advantage computation by incorporating historical
        reward statistics from the buffer. This stabilizes training by providing
        a more robust baseline for normalization.

        The advantage for each example is:
            A_i = (r_i - μ_combined) / σ_combined

        where μ_combined and σ_combined blend current batch stats with buffer
        history using exponential weighting.

        Args:
            batch: List of dicts with at least a "reward" key.

        Returns:
            List of advantage values, one per batch element.
        """
        if not batch:
            return []

        batch_rewards = [item.get("reward", 0.0) for item in batch]

        async with self._lock:
            buffer_rewards = [exp.reward for exp in self._buffer] if self._buffer else []

        # Blend current batch with historical statistics
        if buffer_rewards:
            # Weighted blend: current batch has 70% influence, history 30%
            hist_mean = sum(buffer_rewards) / len(buffer_rewards)
            hist_var = sum((r - hist_mean) ** 2 for r in buffer_rewards) / len(buffer_rewards)

            batch_mean = sum(batch_rewards) / len(batch_rewards)
            batch_var = (
                sum((r - batch_mean) ** 2 for r in batch_rewards) / len(batch_rewards)
            )

            alpha = 0.7  # current batch weight
            combined_mean = alpha * batch_mean + (1 - alpha) * hist_mean
            combined_var = alpha * batch_var + (1 - alpha) * hist_var
        else:
            combined_mean = sum(batch_rewards) / len(batch_rewards)
            combined_var = (
                sum((r - combined_mean) ** 2 for r in batch_rewards) / len(batch_rewards)
            )

        combined_std = math.sqrt(combined_var) + 1e-8

        advantages = [
            round((r - combined_mean) / combined_std, 4)
            for r in batch_rewards
        ]

        logger.debug(
            "experience_advantages",
            batch_size=len(batch),
            combined_mean=round(combined_mean, 4),
            combined_std=round(combined_std, 4),
            buffer_size=len(buffer_rewards),
        )
        return advantages

    # ------------------------------------------------------------------
    # Self-Correction Loop (arXiv:2409.12917)
    # ------------------------------------------------------------------

    async def generate_correction_pair(
        self,
        prompt: str,
        initial_response: str,
        reward: float,
    ) -> Optional[Dict[str, Any]]:
        """Create self-correction training data.

        Implements the correction pair generation from "Training Language Models
        to Self-Correct via RL" (arXiv:2409.12917). When a response has a low
        reward, we look for a higher-reward completion for the same prompt
        and generate a correction training example.

        The correction example teaches the model to:
        1. Recognize its own mistakes
        2. Produce an improved response on the second attempt

        Args:
            prompt: The original prompt.
            initial_response: The initial (low-reward) response.
            reward: The reward for the initial response.

        Returns:
            A correction pair dict, or None if no suitable correction exists.
        """
        if reward >= self._config.correction_reward_threshold:
            return None

        async with self._lock:
            indices = self._prompt_index.get(prompt, [])
            better = [
                self._buffer[i]
                for i in indices
                if self._buffer[i].reward >= self._config.min_reward_for_positive
                and self._buffer[i].completion != initial_response
            ]

        if not better:
            return None

        best = max(better, key=lambda e: e.reward)

        # Record that the original was corrected
        original = Experience(
            prompt=prompt,
            completion=initial_response,
            reward=reward,
            was_corrected=True,
        )
        await self.add_experience(
            prompt=prompt,
            completion=initial_response,
            reward=reward,
            metadata={"was_corrected": True, "corrected_by": best.experience_id},
        )

        correction_pair = {
            "prompt": prompt,
            "initial_response": initial_response,
            "initial_reward": reward,
            "corrected_response": best.completion,
            "corrected_reward": best.reward,
            "correction_source_id": best.experience_id,
            "improvement_delta": round(best.reward - reward, 4),
        }

        logger.info(
            "correction_pair_generated",
            prompt_len=len(prompt),
            initial_reward=reward,
            corrected_reward=best.reward,
            improvement=correction_pair["improvement_delta"],
        )
        return correction_pair

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def save(self) -> None:
        """Save buffer to JSONL file."""
        async with self._lock:
            path = Path(self._config.buffer_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            tmp_path = path.with_suffix(".jsonl.tmp")
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    for exp in self._buffer:
                        f.write(json.dumps(exp.to_dict(), ensure_ascii=False) + "\n")
                tmp_path.replace(path)
                self._dirty = False
            except Exception:
                if tmp_path.exists():
                    tmp_path.unlink()
                raise

        logger.info(
            "buffer_saved",
            path=str(path),
            count=len(self._buffer),
        )

    async def load(self) -> int:
        """Load buffer from JSONL file.

        Returns:
            Number of experiences loaded.
        """
        path = Path(self._config.buffer_path)
        if not path.exists():
            logger.info("buffer_file_not_found", path=str(path))
            return 0

        loaded: List[Experience] = []
        async with self._lock:
            with open(path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        exp = Experience.from_dict(data)
                        loaded.append(exp)
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(
                            "buffer_load_skip_line",
                            line_num=line_num,
                            error=str(e),
                        )
                        continue

            # Respect max_size: keep the most recent entries
            if len(loaded) > self._config.max_size:
                loaded = loaded[-self._config.max_size:]

            self._buffer = loaded
            self._total_seen = len(loaded)
            self._rebuild_prompt_index()
            self._dirty = False

        logger.info(
            "buffer_loaded",
            path=str(path),
            count=len(self._buffer),
        )
        return len(self._buffer)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def get_stats(self) -> Dict[str, Any]:
        """Return buffer statistics for monitoring."""
        async with self._lock:
            if not self._buffer:
                return {
                    "size": 0,
                    "total_seen": self._total_seen,
                    "unique_prompts": 0,
                }

            rewards = [exp.reward for exp in self._buffer]
            mean_reward = sum(rewards) / len(rewards)
            var_reward = sum((r - mean_reward) ** 2 for r in rewards) / len(rewards)
            corrections = sum(1 for exp in self._buffer if exp.was_corrected)

            return {
                "size": len(self._buffer),
                "total_seen": self._total_seen,
                "max_size": self._config.max_size,
                "unique_prompts": len(self._prompt_index),
                "mean_reward": round(mean_reward, 4),
                "std_reward": round(math.sqrt(var_reward), 4),
                "min_reward": round(min(rewards), 4),
                "max_reward": round(max(rewards), 4),
                "corrections_count": corrections,
                "dirty": self._dirty,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rebuild_prompt_index(self) -> None:
        """Rebuild the prompt → buffer-index mapping."""
        self._prompt_index = defaultdict(list)
        for idx, exp in enumerate(self._buffer):
            self._prompt_index[exp.prompt].append(idx)

    def _compute_priorities(self) -> List[float]:
        """Compute sampling priority for each experience.

        Priority is based on per-prompt reward variance: experiences from
        prompts with high variance in their completions are the most
        informative for contrastive learning. A small base priority ensures
        all experiences have a non-zero chance of being sampled.
        """
        # Pre-compute per-prompt reward variance
        prompt_variances: Dict[str, float] = {}
        for prompt, indices in self._prompt_index.items():
            if len(indices) < 2:
                prompt_variances[prompt] = 0.0
                continue
            rewards = [self._buffer[i].reward for i in indices]
            mean = sum(rewards) / len(rewards)
            variance = sum((r - mean) ** 2 for r in rewards) / len(rewards)
            prompt_variances[prompt] = variance

        base_priority = 0.1
        priorities = []
        for exp in self._buffer:
            variance_score = prompt_variances.get(exp.prompt, 0.0)
            # Recency bonus: newer experiences get slight priority
            age = time.time() - exp.timestamp
            recency = 1.0 / (1.0 + age / 86400.0)  # half-life ~1 day
            priority = base_priority + variance_score + 0.1 * recency
            priorities.append(priority)

        return priorities

    @staticmethod
    def _apply_temperature(priorities: List[float], temperature: float) -> List[float]:
        """Apply temperature scaling to priority weights.

        Converts raw priorities into sampling weights via softmax with
        temperature. Higher temperature → flatter distribution (more
        exploration); lower temperature → sharper (more exploitation).
        """
        if not priorities:
            return []

        # Scale by temperature, then softmax for numerical stability
        max_p = max(priorities)
        scaled = [(p - max_p) / temperature for p in priorities]
        exp_vals = [math.exp(s) for s in scaled]
        total = sum(exp_vals)
        if total == 0:
            return [1.0 / len(priorities)] * len(priorities)
        return [v / total for v in exp_vals]

    def _weighted_sample_without_replacement(
        self,
        weights: List[float],
        k: int,
    ) -> List[int]:
        """Sample k indices without replacement using Efraimidis-Spirakis.

        Each index i gets a key: random()^(1/w_i). The top-k keys are
        selected. This is O(n log k) and unbiased for weighted sampling.
        """
        if k >= len(weights):
            return list(range(len(weights)))

        # Generate keys: for each item, key = random^(1/weight)
        keys: List[Tuple[float, int]] = []
        for i, w in enumerate(weights):
            if w <= 0:
                continue
            u = self._rng.random()
            # Avoid log(0)
            if u == 0:
                u = 1e-300
            key = math.log(u) / w  # equivalent ordering to u^(1/w)
            keys.append((key, i))

        # Top-k by key (largest keys)
        keys.sort(reverse=True)
        return [idx for _, idx in keys[:k]]
