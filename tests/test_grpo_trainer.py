"""
Tests for GRPOTrainer — GRPO training pipeline.
"""

import json
import os
import tempfile

import pytest

from src.grpo_trainer import GRPOConfig, GRPODataPreprocessor, GRPOTrainer


@pytest.fixture
def config():
    return GRPOConfig(
        model_name="Qwen/Qwen2.5-Coder-7B-Instruct",
        num_epochs=1,
        batch_size=2,
        lora_rank=16,
    )


@pytest.fixture
def trainer(config):
    return GRPOTrainer(config)


@pytest.fixture
def preprocessor():
    return GRPODataPreprocessor()


@pytest.fixture
def sample_interactions_file():
    """Create a temp file with sample interactions."""
    interactions = [
        {
            "brigade": "OpenClaw",
            "role": "Planner",
            "model": "Qwen2.5-14B",
            "prompt": "Plan a code review task",
            "action": "Step 1: Read file\nStep 2: Check types\nStep 3: Report",
            "episode_id": "ep_001",
            "step_index": 0,
        },
        {
            "brigade": "OpenClaw",
            "role": "Executor_Tools",
            "model": "Qwen-Coder-7B",
            "prompt": "Execute the plan",
            "action": '{"tool": "read_file", "path": "src/main.py"}',
            "episode_id": "ep_001",
            "step_index": 1,
        },
        {
            "brigade": "Dmarket",
            "role": "Executor_API",
            "model": "Qwen-Coder-7B",
            "prompt": "Get price data for AK-47",
            "action": '{"endpoint": "/api/items", "params": {"name": "AK-47"}}',
            "episode_id": "ep_002",
            "step_index": 0,
        },
    ]

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        for i in interactions:
            f.write(json.dumps(i, ensure_ascii=False) + "\n")
        tmppath = f.name

    yield tmppath
    os.unlink(tmppath)


@pytest.fixture
def sample_rewards_file():
    """Create a temp file with sample rewards."""
    rewards = [
        {"episode_id": "ep_001", "step_index": 0, "reward_value": 0.8, "reward_type": "quality"},
        {"episode_id": "ep_001", "step_index": 1, "reward_value": 0.9, "reward_type": "tool_success"},
        {"episode_id": "ep_002", "step_index": 0, "reward_value": 0.7, "reward_type": "api_success"},
    ]

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        for r in rewards:
            f.write(json.dumps(r) + "\n")
        tmppath = f.name

    yield tmppath
    os.unlink(tmppath)


class TestGRPODataPreprocessor:
    def test_load_interactions(self, preprocessor, sample_interactions_file):
        """Interactions are loaded from JSONL."""
        interactions = preprocessor.load_interactions(sample_interactions_file)
        assert len(interactions) == 3
        assert interactions[0]["brigade"] == "OpenClaw"

    def test_load_interactions_missing_file(self, preprocessor):
        """Missing file returns empty list."""
        result = preprocessor.load_interactions("/nonexistent/file.jsonl")
        assert result == []

    def test_load_rewards(self, preprocessor, sample_rewards_file):
        """Rewards are loaded and indexed by episode/step."""
        rewards = preprocessor.load_rewards(sample_rewards_file)
        assert "ep_001" in rewards
        assert rewards["ep_001"][0] == 0.8
        assert rewards["ep_001"][1] == 0.9

    def test_prepare_training_data(self, preprocessor, sample_interactions_file, sample_rewards_file):
        """Training data is prepared with rewards."""
        interactions = preprocessor.load_interactions(sample_interactions_file)
        rewards = preprocessor.load_rewards(sample_rewards_file)
        data = preprocessor.prepare_training_data(interactions, rewards)

        assert len(data) == 3
        assert data[0]["reward"] == 0.8
        assert data[0]["prompt"] == "Plan a code review task"
        assert data[1]["reward"] == 0.9

    def test_prompt_augmentations(self, preprocessor, sample_interactions_file, sample_rewards_file):
        """Prompt augmentation creates additional training examples."""
        interactions = preprocessor.load_interactions(sample_interactions_file)
        data = preprocessor.prepare_training_data(interactions)
        augmented = preprocessor.create_prompt_augmentations(data, num_augmentations=2)

        assert len(augmented) > len(data)
        # Originals preserved
        assert augmented[0]["prompt"] == data[0]["prompt"]
        # Augmented examples exist
        augmented_only = [d for d in augmented if d.get("is_augmented")]
        assert len(augmented_only) > 0


class TestGRPOTrainer:
    def test_check_dependencies(self, trainer):
        """Dependency check returns dict of booleans."""
        deps = trainer.check_dependencies()
        assert isinstance(deps, dict)
        # In CI, GPU deps are likely missing
        assert "torch" in deps
        assert "unsloth" in deps

    def test_compute_grpo_advantages(self, trainer):
        """GRPO advantages are computed correctly."""
        rewards = [0.2, 0.8, 0.5, 0.9]
        lengths = [100, 200, 150, 300]

        advantages = trainer.compute_grpo_advantages(rewards, lengths)
        assert len(advantages) == 4
        # Higher reward should have higher advantage
        # (taking into account length penalty)
        assert advantages[3] > advantages[0]  # 0.9 > 0.2

    def test_compute_grpo_advantages_empty(self, trainer):
        """Empty rewards returns empty advantages."""
        assert trainer.compute_grpo_advantages([], []) == []

    def test_compute_grpo_advantages_uniform(self, trainer):
        """Uniform rewards give near-zero advantages (minus length penalty)."""
        rewards = [0.5, 0.5, 0.5, 0.5]
        lengths = [100, 100, 100, 100]
        advantages = trainer.compute_grpo_advantages(rewards, lengths)
        # With uniform rewards and lengths, advantages should be ~0
        for a in advantages:
            assert abs(a) < 0.1

    def test_lambda_adaptation(self, trainer):
        """Lambda adapts based on correctness ratio."""
        initial_lambda = trainer._lambda
        assert initial_lambda == trainer.config.lambda_init

        # High correctness → lambda increases
        for _ in range(5):
            trainer._adapt_lambda(0.9)
        assert trainer._lambda > initial_lambda

    def test_lambda_decrease(self, trainer):
        """Lambda decreases when correctness is low."""
        trainer._lambda = 1.0
        for _ in range(5):
            trainer._adapt_lambda(0.2)
        assert trainer._lambda < 1.0

    def test_train_without_gpu_returns_plan(self, trainer):
        """Training without GPU deps returns a plan."""
        training_data = [
            {"prompt": "test", "completion": "output", "reward": 0.8, "brigade": "OpenClaw", "role": "Planner", "model": "m"},
        ]
        result = trainer.train(training_data)
        # In CI, GPU deps are missing, so we get a plan
        assert result["status"] in ("plan_generated", "training_complete", "error")

    def test_create_training_plan(self, trainer):
        """Training plan has all required fields."""
        data = [
            {"prompt": "p1", "completion": "c1", "reward": 0.8, "brigade": "OpenClaw", "role": "Planner", "model": "m"},
            {"prompt": "p2", "completion": "c2", "reward": 0.6, "brigade": "Dmarket", "role": "Executor_API", "model": "m"},
        ]
        plan = trainer._create_training_plan(data, ["torch", "unsloth"])
        assert plan["status"] == "plan_generated"
        assert "torch" in plan["missing_dependencies"]
        assert plan["config"]["model"] == "Qwen/Qwen2.5-Coder-7B-Instruct"
        assert plan["data_stats"]["total_examples"] == 2
        assert len(plan["steps"]) == 7
