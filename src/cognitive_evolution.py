"""Cognitive Evolution Engine — closed-loop prompt evolution for OpenClaw Bot.

Reference: AutoAgent (arXiv:2603.09716) — evolving cognition at prompt-level.

Implements:
1. Execution outcome tracking (intended → observed → delta)
2. Role prompt versioning with performance history
3. Automatic prompt tuning based on accumulated experience
4. Skill discovery from execution patterns
5. Integration with ObsidianBridge for persistent storage

No retraining required — all evolution happens at the prompt level.

v1 (2026-04-06): Initial implementation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

from src.llm.gateway import route_llm

logger = structlog.get_logger("CognitiveEvolution")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ExecutionOutcome:
    """Records the result of a pipeline execution for learning."""

    task_id: str
    task_description: str
    role: str
    intended_action: str
    observed_result: str
    success: bool
    quality_score: float  # 0.0-1.0
    duration_sec: float
    model_used: str
    timestamp: float = field(default_factory=time.time)
    error: str = ""
    suggestions: List[str] = field(default_factory=list)


@dataclass
class RolePromptVersion:
    """Versioned role prompt with performance tracking."""

    role: str
    version: int
    prompt_text: str
    created_at: float
    total_invocations: int = 0
    success_count: int = 0
    avg_quality: float = 0.0
    is_active: bool = True

    @property
    def success_rate(self) -> float:
        if self.total_invocations == 0:
            return 0.0
        return self.success_count / self.total_invocations


@dataclass
class DiscoveredSkill:
    """A skill pattern discovered from repeated successful executions."""

    name: str
    description: str
    pattern: str  # regex or keyword pattern for trigger
    usage_count: int = 0
    success_rate: float = 0.0
    discovered_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Cognitive Evolution Engine
# ---------------------------------------------------------------------------

class CognitiveEvolutionEngine:
    """Closed-loop prompt evolution engine.

    Tracks execution outcomes, evolves role prompts, discovers skills,
    and persists everything to Obsidian vault for long-term memory.

    Usage:
        engine = CognitiveEvolutionEngine(vault_bridge=bridge)
        # After each pipeline step:
        engine.record_outcome(ExecutionOutcome(...))
        # Periodically:
        engine.evolve_prompts()
        engine.discover_skills()
        # Get evolved prompt for a role:
        prompt = engine.get_prompt("Planner")
    """

    def __init__(
        self,
        vault_bridge: Any = None,
        prompts_dir: str | None = None,
        min_outcomes_for_evolution: int = 5,
        evolution_threshold: float = 0.6,  # evolve if success_rate < this
    ):
        self._vault = vault_bridge
        self._prompts_dir = Path(prompts_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "cognitive_evolution",
        ))
        self._prompts_dir.mkdir(parents=True, exist_ok=True)

        self._min_outcomes = min_outcomes_for_evolution
        self._evolution_threshold = evolution_threshold

        # In-memory state (persisted to vault/disk periodically)
        self._outcomes: List[ExecutionOutcome] = []
        self._role_prompts: Dict[str, RolePromptVersion] = {}
        self._discovered_skills: Dict[str, DiscoveredSkill] = {}
        self._outcome_history: Dict[str, List[ExecutionOutcome]] = {}  # role → outcomes

        self._load_state()
        logger.info("CognitiveEvolutionEngine initialized")

    # ------------------------------------------------------------------
    # Outcome tracking
    # ------------------------------------------------------------------

    def record_outcome(self, outcome: ExecutionOutcome) -> None:
        """Record an execution outcome for learning."""
        self._outcomes.append(outcome)

        # Track per-role history
        role = outcome.role
        if role not in self._outcome_history:
            self._outcome_history[role] = []
        self._outcome_history[role].append(outcome)

        # Update active prompt stats
        if role in self._role_prompts:
            prompt = self._role_prompts[role]
            prompt.total_invocations += 1
            if outcome.success:
                prompt.success_count += 1
            # Running average of quality
            n = prompt.total_invocations
            prompt.avg_quality = (
                prompt.avg_quality * (n - 1) + outcome.quality_score
            ) / n

        # Log to vault
        if self._vault:
            self._vault.save_learning_log(
                task=f"{role}: {outcome.task_description[:60]}",
                outcome="success" if outcome.success else "failure",
                lessons=outcome.suggestions or [
                    f"Quality: {outcome.quality_score:.2f}",
                    f"Duration: {outcome.duration_sec:.1f}s",
                ],
                context=f"Task ID: {outcome.task_id}\nModel: {outcome.model_used}",
            )

        logger.info(
            "Outcome recorded",
            role=role,
            success=outcome.success,
            quality=f"{outcome.quality_score:.2f}",
        )

    # ------------------------------------------------------------------
    # Prompt evolution
    # ------------------------------------------------------------------

    async def evolve_prompts(self) -> Dict[str, str]:
        """Analyze outcomes and evolve underperforming role prompts.

        Returns dict of {role: evolution_summary} for roles that were updated.
        """
        evolutions: Dict[str, str] = {}

        for role, outcomes in self._outcome_history.items():
            if len(outcomes) < self._min_outcomes:
                continue

            # Calculate recent performance (last N outcomes)
            recent = outcomes[-self._min_outcomes:]
            success_rate = sum(1 for o in recent if o.success) / len(recent)
            avg_quality = sum(o.quality_score for o in recent) / len(recent)

            if success_rate >= self._evolution_threshold and avg_quality >= 0.6:
                continue  # performing well, no evolution needed

            logger.info(
                "Evolving prompt",
                role=role,
                success_rate=f"{success_rate:.0%}",
                avg_quality=f"{avg_quality:.2f}",
            )

            # Gather failure patterns
            failures = [o for o in recent if not o.success]
            failure_descriptions = [
                f"- Task: {o.task_description[:100]}\n  Error: {o.error[:200]}"
                for o in failures[:5]
            ]

            # Get current prompt
            current_prompt = self.get_prompt(role)
            if not current_prompt:
                continue

            # Ask LLM to evolve the prompt based on failure patterns
            new_prompt = await self._generate_evolved_prompt(
                role, current_prompt, failure_descriptions, success_rate, avg_quality,
            )

            if new_prompt and len(new_prompt) > 50:
                old_version = self._role_prompts.get(role)
                new_version_num = (old_version.version + 1) if old_version else 1

                self._role_prompts[role] = RolePromptVersion(
                    role=role,
                    version=new_version_num,
                    prompt_text=new_prompt,
                    created_at=time.time(),
                )

                evolutions[role] = (
                    f"v{new_version_num}: success_rate {success_rate:.0%} → evolved. "
                    f"Addressed {len(failures)} failure patterns."
                )

                # Save to vault
                if self._vault:
                    self._vault.save_note(
                        f"Knowledge/Agents/{role}_prompt_v{new_version_num}.md",
                        f"# {role} — Prompt v{new_version_num}\n\n"
                        f"*Evolved at {datetime.now(timezone.utc).isoformat()}*\n"
                        f"*Previous success rate: {success_rate:.0%}*\n\n"
                        f"## Prompt\n\n```\n{new_prompt}\n```\n\n"
                        f"## Evolution Reason\n\n"
                        f"{''.join(failure_descriptions)}\n\n"
                        f"#agent-prompt #evolved #v{new_version_num}",
                        frontmatter={
                            "type": "agent-prompt",
                            "role": role,
                            "version": str(new_version_num),
                            "success_rate_before": f"{success_rate:.2f}",
                        },
                    )

        self._save_state()
        return evolutions

    async def _generate_evolved_prompt(
        self,
        role: str,
        current_prompt: str,
        failure_descriptions: List[str],
        success_rate: float,
        avg_quality: float,
    ) -> str:
        """Use LLM to generate an improved version of a role prompt."""
        failures_text = "\n".join(failure_descriptions)

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Ты — эксперт по оптимизации промптов для AI-агентов. "
                        "Твоя задача — улучшить системный промпт роли на основе "
                        "анализа провалов. Сохрани ядро промпта, но добавь/измени "
                        "инструкции чтобы предотвратить обнаруженные провалы. "
                        "Ответь ТОЛЬКО новым промптом, без объяснений."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"РОЛЬ: {role}\n"
                        f"ТЕКУЩИЙ ПРОМПТ:\n{current_prompt[:2000]}\n\n"
                        f"SUCCESS RATE: {success_rate:.0%}\n"
                        f"AVG QUALITY: {avg_quality:.2f}\n\n"
                        f"ТИПИЧНЫЕ ПРОВАЛЫ:\n{failures_text}\n\n"
                        f"Создай улучшенную версию промпта."
                    ),
                },
            ]

            result = await route_llm(
                "",
                messages=messages,
                task_type="meta",
                max_tokens=2048,
                temperature=0.3,
            )
            return result.strip() if result else ""
        except Exception as e:
            logger.warning("Prompt evolution LLM call failed", role=role, error=str(e))
            return ""

    def get_prompt(self, role: str) -> str:
        """Get the current (possibly evolved) prompt for a role."""
        if role in self._role_prompts and self._role_prompts[role].is_active:
            return self._role_prompts[role].prompt_text
        return ""

    def register_baseline_prompt(self, role: str, prompt: str) -> None:
        """Register a baseline prompt for a role (version 0)."""
        if role not in self._role_prompts:
            self._role_prompts[role] = RolePromptVersion(
                role=role,
                version=0,
                prompt_text=prompt,
                created_at=time.time(),
            )

    # ------------------------------------------------------------------
    # Skill discovery
    # ------------------------------------------------------------------

    async def discover_skills(self) -> List[DiscoveredSkill]:
        """Analyze successful outcomes to discover reusable skill patterns.

        Looks for repeated task patterns in successful executions and
        formalizes them as named skills.
        """
        if len(self._outcomes) < 10:
            return []

        successful = [o for o in self._outcomes if o.success and o.quality_score >= 0.7]
        if len(successful) < 5:
            return []

        # Group by task patterns (simple keyword clustering)
        task_clusters: Dict[str, List[ExecutionOutcome]] = {}
        for outcome in successful:
            # Normalize task description to find clusters
            key_words = set(outcome.task_description.lower().split())
            # Use first 3 significant words as cluster key
            sig_words = sorted(
                [w for w in key_words if len(w) > 3],
                key=lambda w: len(w),
                reverse=True,
            )[:3]
            cluster_key = "_".join(sig_words) if sig_words else "general"

            if cluster_key not in task_clusters:
                task_clusters[cluster_key] = []
            task_clusters[cluster_key].append(outcome)

        # Skills = clusters with 3+ successful instances
        new_skills: List[DiscoveredSkill] = []
        for cluster_key, outcomes in task_clusters.items():
            if len(outcomes) < 3:
                continue

            # Check if already discovered
            if cluster_key in self._discovered_skills:
                continue

            skill = DiscoveredSkill(
                name=cluster_key,
                description=f"Pattern from {len(outcomes)} successful executions",
                pattern="|".join(cluster_key.split("_")),
                usage_count=len(outcomes),
                success_rate=sum(1 for o in outcomes if o.success) / len(outcomes),
            )
            new_skills.append(skill)

            # Save to vault
            if self._vault:
                examples = [o.task_description[:100] for o in outcomes[:3]]
                self._vault.save_skill_note(
                    skill_name=cluster_key,
                    description=skill.description,
                    usage_pattern=skill.pattern,
                    success_rate=skill.success_rate,
                    examples=examples,
                )

        for skill in new_skills:
            self._discovered_skills[skill.name] = skill

        logger.info("Skill discovery complete", new_skills=len(new_skills))
        return new_skills

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_state(self) -> None:
        """Save engine state to disk."""
        state = {
            "prompts": {
                role: {
                    "role": p.role,
                    "version": p.version,
                    "prompt_text": p.prompt_text,
                    "created_at": p.created_at,
                    "total_invocations": p.total_invocations,
                    "success_count": p.success_count,
                    "avg_quality": p.avg_quality,
                    "is_active": p.is_active,
                }
                for role, p in self._role_prompts.items()
            },
            "outcome_counts": {
                role: len(outcomes)
                for role, outcomes in self._outcome_history.items()
            },
            "total_outcomes": len(self._outcomes),
            "saved_at": time.time(),
        }
        try:
            state_file = self._prompts_dir / "evolution_state.json"
            state_file.write_text(
                json.dumps(state, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Failed to save evolution state", error=str(e))

    def _load_state(self) -> None:
        """Load engine state from disk."""
        state_file = self._prompts_dir / "evolution_state.json"
        if not state_file.exists():
            return
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            for role, pdata in state.get("prompts", {}).items():
                self._role_prompts[role] = RolePromptVersion(
                    role=pdata["role"],
                    version=pdata["version"],
                    prompt_text=pdata["prompt_text"],
                    created_at=pdata["created_at"],
                    total_invocations=pdata.get("total_invocations", 0),
                    success_count=pdata.get("success_count", 0),
                    avg_quality=pdata.get("avg_quality", 0.0),
                    is_active=pdata.get("is_active", True),
                )
            logger.info("Evolution state loaded", roles=len(self._role_prompts))
        except Exception as e:
            logger.warning("Failed to load evolution state", error=str(e))

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def get_evolution_report(self) -> Dict[str, Any]:
        """Get a summary of the cognitive evolution state."""
        return {
            "total_outcomes": len(self._outcomes),
            "roles_tracked": list(self._outcome_history.keys()),
            "evolved_prompts": {
                role: {
                    "version": p.version,
                    "success_rate": f"{p.success_rate:.0%}",
                    "avg_quality": f"{p.avg_quality:.2f}",
                    "invocations": p.total_invocations,
                }
                for role, p in self._role_prompts.items()
                if p.version > 0
            },
            "discovered_skills": len(self._discovered_skills),
        }
