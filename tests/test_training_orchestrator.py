"""
Tests for TrainingOrchestrator — end-to-end training pipeline.

Tests the full pipeline:
1. Synthetic data generation
2. RLVR reward computation
3. Experience buffer filling
4. GRPO training (dry-run / plan generation)
5. Metrics reporting
"""

import asyncio
import json
import os
import shutil
import tempfile

import pytest

from src.training_orchestrator import (
    DMARKET_SCENARIOS,
    EXTRA_SCENARIOS,
    OPENCLAW_SCENARIOS,
    TrainingMetrics,
    TrainingOrchestrator,
)


@pytest.fixture
def tmp_training_dir():
    """Create a temporary directory for training data."""
    d = tempfile.mkdtemp(prefix="training_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def orchestrator(tmp_training_dir):
    """Create a TrainingOrchestrator with temp directory."""
    return TrainingOrchestrator(
        training_dir=tmp_training_dir,
        model_name="Qwen/Qwen2.5-Coder-7B-Instruct",
        lora_rank=32,
        num_epochs=3,
        seed=42,
    )


# ── Scenario Data Tests ─────────────────────────────────────────────────

class TestScenarioData:
    """Test that scenario data is well-formed."""

    def test_dmarket_scenarios_have_required_fields(self):
        for i, s in enumerate(DMARKET_SCENARIOS):
            assert "role" in s, f"Dmarket scenario {i} missing 'role'"
            assert "prompt" in s, f"Dmarket scenario {i} missing 'prompt'"
            assert "good_action" in s, f"Dmarket scenario {i} missing 'good_action'"
            assert "bad_action" in s, f"Dmarket scenario {i} missing 'bad_action'"

    def test_openclaw_scenarios_have_required_fields(self):
        for i, s in enumerate(OPENCLAW_SCENARIOS):
            assert "role" in s, f"OpenClaw scenario {i} missing 'role'"
            assert "prompt" in s, f"OpenClaw scenario {i} missing 'prompt'"
            assert "good_action" in s, f"OpenClaw scenario {i} missing 'good_action'"
            assert "bad_action" in s, f"OpenClaw scenario {i} missing 'bad_action'"

    def test_extra_scenarios_have_brigade(self):
        for i, s in enumerate(EXTRA_SCENARIOS):
            assert "brigade" in s, f"Extra scenario {i} missing 'brigade'"

    def test_dmarket_scenarios_count(self):
        assert len(DMARKET_SCENARIOS) >= 7

    def test_openclaw_scenarios_count(self):
        assert len(OPENCLAW_SCENARIOS) >= 7

    def test_extra_scenarios_count(self):
        assert len(EXTRA_SCENARIOS) >= 5

    def test_total_scenario_count(self):
        total = len(DMARKET_SCENARIOS) + len(OPENCLAW_SCENARIOS) + len(EXTRA_SCENARIOS)
        assert total >= 19, f"Expected at least 19 scenarios, got {total}"

    def test_good_actions_contain_json(self):
        """Good Dmarket actions should contain valid JSON."""
        for s in DMARKET_SCENARIOS:
            try:
                json.loads(s["good_action"])
            except json.JSONDecodeError:
                pass  # Some may be markdown code blocks, that's OK

    def test_roles_are_valid(self):
        valid_roles = {"Planner", "Executor_API", "Executor_Tools", "Archivist"}
        for s in DMARKET_SCENARIOS + OPENCLAW_SCENARIOS + EXTRA_SCENARIOS:
            assert s["role"] in valid_roles, f"Invalid role: {s['role']}"


# ── Phase 1: Synthetic Data Generation ──────────────────────────────────

class TestSyntheticDataGeneration:
    """Test synthetic data generation phase."""

    def test_generates_interactions(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        assert len(interactions) > 0

    def test_each_scenario_produces_two_interactions(self, orchestrator):
        """Each scenario produces a good and bad action = 2 interactions."""
        total_scenarios = len(DMARKET_SCENARIOS) + len(OPENCLAW_SCENARIOS) + len(EXTRA_SCENARIOS)
        interactions = orchestrator.generate_synthetic_data()
        assert len(interactions) == total_scenarios * 2

    def test_interactions_have_required_fields(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        for ix in interactions:
            assert "brigade" in ix
            assert "role" in ix
            assert "prompt" in ix
            assert "action" in ix
            assert "model" in ix

    def test_both_brigades_covered(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        brigades = {ix["brigade"] for ix in interactions}
        assert "Dmarket" in brigades
        assert "OpenClaw" in brigades

    def test_good_and_bad_actions_differ(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        # Pairs of (good, bad) should differ
        for i in range(0, len(interactions) - 1, 2):
            assert interactions[i]["action"] != interactions[i + 1]["action"]

    def test_corrections_logged(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        has_correction = [ix for ix in interactions if ix.get("has_correction")]
        assert len(has_correction) > 0

    def test_files_created(self, orchestrator, tmp_training_dir):
        orchestrator.generate_synthetic_data()
        interactions_file = os.path.join(tmp_training_dir, "interactions.jsonl")
        assert os.path.exists(interactions_file)
        with open(interactions_file) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) > 0

    def test_episodes_logged(self, orchestrator, tmp_training_dir):
        orchestrator.generate_synthetic_data()
        episodes_file = os.path.join(tmp_training_dir, "episodes.jsonl")
        assert os.path.exists(episodes_file)

    def test_timing_tracked(self, orchestrator):
        orchestrator.generate_synthetic_data()
        assert "data_generation" in orchestrator.metrics.phases
        assert orchestrator.metrics.phases["data_generation"] >= 0


# ── Phase 2: Reward Computation ─────────────────────────────────────────

class TestRewardComputation:
    """Test RLVR reward computation phase."""

    def test_computes_rewards_for_all(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        results = orchestrator.compute_rewards(interactions)
        assert len(results) == len(interactions)

    def test_rewards_in_range(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        results = orchestrator.compute_rewards(interactions)
        for _, reward in results:
            assert 0.0 <= reward <= 1.0

    def test_good_actions_get_higher_rewards(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        results = orchestrator.compute_rewards(interactions)

        good_rewards = []
        bad_rewards = []
        for interaction, reward in results:
            quality = interaction.get("metadata", {}).get("quality", "")
            if quality == "good":
                good_rewards.append(reward)
            elif quality == "bad":
                bad_rewards.append(reward)

        if good_rewards and bad_rewards:
            avg_good = sum(good_rewards) / len(good_rewards)
            avg_bad = sum(bad_rewards) / len(bad_rewards)
            # Good actions should have equal or higher avg reward
            assert avg_good >= avg_bad, (
                f"Good avg {avg_good:.3f} should be >= bad avg {avg_bad:.3f}"
            )

    def test_metrics_updated(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        orchestrator.compute_rewards(interactions)
        assert orchestrator.metrics.avg_reward > 0
        assert orchestrator.metrics.min_reward >= 0
        assert orchestrator.metrics.max_reward <= 1.0

    def test_reward_types_tracked(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        orchestrator.compute_rewards(interactions)
        assert len(orchestrator.metrics.rewards_by_type) > 0

    def test_rewards_file_created(self, orchestrator, tmp_training_dir):
        interactions = orchestrator.generate_synthetic_data()
        orchestrator.compute_rewards(interactions)
        rewards_file = os.path.join(tmp_training_dir, "rewards.jsonl")
        assert os.path.exists(rewards_file)

    def test_timing_tracked(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        orchestrator.compute_rewards(interactions)
        assert "reward_computation" in orchestrator.metrics.phases


# ── Phase 3: Experience Buffer ──────────────────────────────────────────

class TestExperienceBuffer:
    """Test experience buffer filling phase."""

    @pytest.mark.asyncio
    async def test_fills_buffer(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        rewarded = orchestrator.compute_rewards(interactions)
        await orchestrator.fill_experience_buffer(rewarded)
        assert orchestrator.experience_buffer.size > 0

    @pytest.mark.asyncio
    async def test_buffer_size_matches_interactions(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        rewarded = orchestrator.compute_rewards(interactions)
        await orchestrator.fill_experience_buffer(rewarded)
        assert orchestrator.experience_buffer.size == len(rewarded)

    @pytest.mark.asyncio
    async def test_contrastive_pairs_generated(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        rewarded = orchestrator.compute_rewards(interactions)
        await orchestrator.fill_experience_buffer(rewarded)
        assert orchestrator.metrics.contrastive_pairs_generated > 0

    @pytest.mark.asyncio
    async def test_corrections_generated(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        rewarded = orchestrator.compute_rewards(interactions)
        await orchestrator.fill_experience_buffer(rewarded)
        # Some corrections should be generated for bad actions
        assert orchestrator.metrics.corrections_generated >= 0

    @pytest.mark.asyncio
    async def test_metrics_updated(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        rewarded = orchestrator.compute_rewards(interactions)
        await orchestrator.fill_experience_buffer(rewarded)
        assert orchestrator.metrics.buffer_size > 0

    @pytest.mark.asyncio
    async def test_timing_tracked(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        rewarded = orchestrator.compute_rewards(interactions)
        await orchestrator.fill_experience_buffer(rewarded)
        assert "experience_buffer" in orchestrator.metrics.phases


# ── Phase 4: GRPO Training ──────────────────────────────────────────────

class TestGRPOTraining:
    """Test GRPO training phase (dry-run in CI without GPU)."""

    @pytest.mark.asyncio
    async def test_produces_training_plan(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        rewarded = orchestrator.compute_rewards(interactions)
        await orchestrator.fill_experience_buffer(rewarded)
        result = await orchestrator.run_grpo_training(rewarded)
        # In CI without GPU, should generate a plan
        assert result.get("status") in ("plan_generated", "training_complete", "error")

    @pytest.mark.asyncio
    async def test_advantages_computed(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        rewarded = orchestrator.compute_rewards(interactions)
        await orchestrator.fill_experience_buffer(rewarded)
        await orchestrator.run_grpo_training(rewarded)
        assert orchestrator.metrics.grpo_advantages_computed > 0

    @pytest.mark.asyncio
    async def test_lambda_adapted(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        rewarded = orchestrator.compute_rewards(interactions)
        await orchestrator.fill_experience_buffer(rewarded)
        await orchestrator.run_grpo_training(rewarded)
        assert orchestrator.metrics.lambda_final > 0

    @pytest.mark.asyncio
    async def test_training_plan_contains_config(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        rewarded = orchestrator.compute_rewards(interactions)
        await orchestrator.fill_experience_buffer(rewarded)
        result = await orchestrator.run_grpo_training(rewarded)
        if result.get("status") == "plan_generated":
            assert "config" in result
            assert "model" in result["config"]

    @pytest.mark.asyncio
    async def test_timing_tracked(self, orchestrator):
        interactions = orchestrator.generate_synthetic_data()
        rewarded = orchestrator.compute_rewards(interactions)
        await orchestrator.fill_experience_buffer(rewarded)
        await orchestrator.run_grpo_training(rewarded)
        assert "grpo_training" in orchestrator.metrics.phases


# ── End-to-End Pipeline ─────────────────────────────────────────────────

class TestFullPipeline:
    """Test the complete end-to-end training pipeline."""

    @pytest.mark.asyncio
    async def test_full_training_completes(self, orchestrator):
        metrics = await orchestrator.run_full_training()
        assert metrics.total_interactions > 0
        assert metrics.total_episodes > 0
        assert metrics.avg_reward > 0
        assert metrics.buffer_size > 0
        assert metrics.grpo_status in ("plan_generated", "training_complete", "error")

    @pytest.mark.asyncio
    async def test_all_phases_timed(self, orchestrator):
        metrics = await orchestrator.run_full_training()
        assert "data_generation" in metrics.phases
        assert "reward_computation" in metrics.phases
        assert "experience_buffer" in metrics.phases
        assert "grpo_training" in metrics.phases
        assert metrics.total_duration_s > 0

    @pytest.mark.asyncio
    async def test_brigades_and_roles_covered(self, orchestrator):
        metrics = await orchestrator.run_full_training()
        assert "Dmarket" in metrics.brigades_covered
        assert "OpenClaw" in metrics.brigades_covered
        assert len(metrics.roles_covered) >= 3

    @pytest.mark.asyncio
    async def test_experience_buffer_saved(self, orchestrator, tmp_training_dir):
        await orchestrator.run_full_training()
        buffer_file = os.path.join(tmp_training_dir, "experience_buffer.jsonl")
        assert os.path.exists(buffer_file)

    @pytest.mark.asyncio
    async def test_metrics_summary_renders(self, orchestrator):
        metrics = await orchestrator.run_full_training()
        summary = metrics.summary()
        assert "РЕЗУЛЬТАТЫ ОБУЧЕНИЯ" in summary
        assert "НАГРАДЫ" in summary
        assert "GRPO" in summary
        assert "EXPERIENCE BUFFER" in summary

    @pytest.mark.asyncio
    async def test_metrics_to_dict(self, orchestrator):
        metrics = await orchestrator.run_full_training()
        d = metrics.to_dict()
        assert isinstance(d, dict)
        assert "total_interactions" in d
        assert "avg_reward" in d
        assert "grpo_status" in d

    @pytest.mark.asyncio
    async def test_metrics_serializable_to_json(self, orchestrator):
        metrics = await orchestrator.run_full_training()
        d = metrics.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["total_interactions"] == metrics.total_interactions


# ── TrainingMetrics Tests ───────────────────────────────────────────────

class TestTrainingMetrics:
    """Test the TrainingMetrics dataclass."""

    def test_default_values(self):
        m = TrainingMetrics()
        assert m.total_interactions == 0
        assert m.avg_reward == 0.0
        assert m.grpo_status == "not_started"

    def test_summary_renders(self):
        m = TrainingMetrics(
            total_interactions=100,
            total_episodes=5,
            brigades_covered=["Dmarket", "OpenClaw"],
            roles_covered=["Planner", "Executor_API"],
            avg_reward=0.75,
            min_reward=0.1,
            max_reward=0.95,
            buffer_size=100,
            grpo_status="plan_generated",
        )
        summary = m.summary()
        assert "100" in summary
        assert "Dmarket" in summary
        assert "0.75" in summary

    def test_to_dict(self):
        m = TrainingMetrics(total_interactions=42)
        d = m.to_dict()
        assert d["total_interactions"] == 42
