"""
Tests for MultiModelTrainer — multi-model training pipeline.

Tests the complete multi-model training:
1. All models are discovered and configured
2. Model-specific scenarios are generated
3. RLVR rewards computed per model
4. ExGRPO buffers filled per model
5. GRPO training run per model
6. Benefits computed per model
7. Full report generated
"""

import asyncio
import json
import os
import shutil
import tempfile

import pytest

from src.multi_model_trainer import (
    ALL_MODELS,
    CODING_LIGHT_SCENARIOS,
    MEMORY_GC_SCENARIOS,
    RESEARCH_SCENARIOS,
    ModelTrainingResult,
    MultiModelTrainer,
    MultiModelTrainingReport,
)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="multi_model_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def trainer(tmp_dir):
    return MultiModelTrainer(training_dir=tmp_dir, num_epochs=3, seed=42)


# ── Model Registry Tests ───────────────────────────────────────────────

class TestModelRegistry:
    """Test that ALL_MODELS is properly defined."""

    def test_four_models_defined(self):
        assert len(ALL_MODELS) == 4

    def test_qwen_14b_exists(self):
        assert "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ" in ALL_MODELS

    def test_qwen_7b_exists(self):
        assert "Qwen/Qwen2.5-Coder-7B-Instruct" in ALL_MODELS

    def test_deepseek_exists(self):
        assert "casperhansen/deepseek-r1-distill-qwen-14b-awq" in ALL_MODELS

    def test_gemma_exists(self):
        assert "google/gemma-3-12b-it" in ALL_MODELS

    def test_all_models_have_required_fields(self):
        required = {"description", "roles", "brigades", "tasks", "vram_gb", "lora_rank", "batch_size", "strengths"}
        for name, info in ALL_MODELS.items():
            for field in required:
                assert field in info, f"{name} missing '{field}'"

    def test_all_models_have_roles(self):
        for name, info in ALL_MODELS.items():
            assert len(info["roles"]) > 0, f"{name} has no roles"

    def test_all_models_have_brigades(self):
        for name, info in ALL_MODELS.items():
            assert len(info["brigades"]) > 0, f"{name} has no brigades"

    def test_vram_within_16gb(self):
        for name, info in ALL_MODELS.items():
            assert info["vram_gb"] <= 16, f"{name} exceeds 16GB VRAM"


# ── Scenario Data Tests ────────────────────────────────────────────────

class TestScenarioData:
    """Test that model-specific scenarios are well-formed."""

    def test_research_scenarios_count(self):
        assert len(RESEARCH_SCENARIOS) >= 3

    def test_memory_gc_scenarios_count(self):
        assert len(MEMORY_GC_SCENARIOS) >= 3

    def test_coding_light_scenarios_count(self):
        assert len(CODING_LIGHT_SCENARIOS) >= 3

    def test_research_scenarios_have_fields(self):
        for i, s in enumerate(RESEARCH_SCENARIOS):
            assert "role" in s, f"Research scenario {i} missing 'role'"
            assert "prompt" in s, f"Research scenario {i} missing 'prompt'"
            assert "good_action" in s
            assert "bad_action" in s

    def test_memory_gc_scenarios_have_fields(self):
        for i, s in enumerate(MEMORY_GC_SCENARIOS):
            assert "role" in s
            assert "prompt" in s
            assert "good_action" in s
            assert "bad_action" in s

    def test_coding_scenarios_have_fields(self):
        for i, s in enumerate(CODING_LIGHT_SCENARIOS):
            assert "role" in s
            assert "prompt" in s
            assert "good_action" in s
            assert "bad_action" in s

    def test_research_roles_valid(self):
        valid = {"Planner", "Risk_Analyst", "Data_Analyst"}
        for s in RESEARCH_SCENARIOS:
            assert s["role"] in valid

    def test_memory_roles_valid(self):
        valid = {"Archivist", "State_Manager"}
        for s in MEMORY_GC_SCENARIOS:
            assert s["role"] in valid

    def test_coding_roles_valid(self):
        valid = {"Executor_Tools", "Test_Writer", "Debugger"}
        for s in CODING_LIGHT_SCENARIOS:
            assert s["role"] in valid


# ── Scenario Generation Tests ──────────────────────────────────────────

class TestScenarioGeneration:
    """Test model-specific scenario selection."""

    def test_qwen14b_gets_most_scenarios(self, trainer):
        info = ALL_MODELS["Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"]
        scenarios, _ = trainer._get_scenarios_for_model(
            "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ", info
        )
        assert len(scenarios) >= 15  # Largest model, most roles

    def test_qwen7b_gets_coding_scenarios(self, trainer):
        info = ALL_MODELS["Qwen/Qwen2.5-Coder-7B-Instruct"]
        scenarios, _ = trainer._get_scenarios_for_model(
            "Qwen/Qwen2.5-Coder-7B-Instruct", info
        )
        roles = set(s["role"] for s in scenarios)
        assert "Executor_Tools" in roles or "Debugger" in roles or "Test_Writer" in roles

    def test_deepseek_gets_research_scenarios(self, trainer):
        info = ALL_MODELS["casperhansen/deepseek-r1-distill-qwen-14b-awq"]
        scenarios, _ = trainer._get_scenarios_for_model(
            "casperhansen/deepseek-r1-distill-qwen-14b-awq", info
        )
        roles = set(s["role"] for s in scenarios)
        # Should include research roles
        assert "Planner" in roles or "Risk_Analyst" in roles or "Data_Analyst" in roles

    def test_gemma_gets_memory_scenarios(self, trainer):
        info = ALL_MODELS["google/gemma-3-12b-it"]
        scenarios, _ = trainer._get_scenarios_for_model(
            "google/gemma-3-12b-it", info
        )
        roles = set(s["role"] for s in scenarios)
        assert "Archivist" in roles or "State_Manager" in roles

    def test_each_model_gets_at_least_one_scenario(self, trainer):
        for model_name, model_info in ALL_MODELS.items():
            scenarios, _ = trainer._get_scenarios_for_model(model_name, model_info)
            assert len(scenarios) > 0, f"{model_name} got 0 scenarios"


# ── Single Model Training Tests ────────────────────────────────────────

class TestSingleModelTraining:
    """Test training of individual models."""

    @pytest.mark.asyncio
    async def test_train_qwen14b(self, trainer):
        info = ALL_MODELS["Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"]
        result = await trainer.train_single_model(
            "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ", info
        )
        assert result.status == "plan_generated"
        assert result.total_interactions > 0
        assert result.avg_reward > 0
        assert result.buffer_size > 0
        assert result.contrastive_pairs > 0
        assert len(result.benefits) > 0

    @pytest.mark.asyncio
    async def test_train_qwen7b(self, trainer):
        info = ALL_MODELS["Qwen/Qwen2.5-Coder-7B-Instruct"]
        result = await trainer.train_single_model(
            "Qwen/Qwen2.5-Coder-7B-Instruct", info
        )
        assert result.status == "plan_generated"
        assert result.lora_rank == 32  # Higher rank for 7B
        assert result.estimated_vram_gb == 8

    @pytest.mark.asyncio
    async def test_train_deepseek(self, trainer):
        info = ALL_MODELS["casperhansen/deepseek-r1-distill-qwen-14b-awq"]
        result = await trainer.train_single_model(
            "casperhansen/deepseek-r1-distill-qwen-14b-awq", info
        )
        assert result.status == "plan_generated"
        assert result.avg_reward > 0
        assert any("R1-distill" in b for b in result.benefits)

    @pytest.mark.asyncio
    async def test_train_gemma(self, trainer):
        info = ALL_MODELS["google/gemma-3-12b-it"]
        result = await trainer.train_single_model(
            "google/gemma-3-12b-it", info
        )
        assert result.status == "plan_generated"
        assert any("Memory GC" in b or "Gemma" in b for b in result.benefits)

    @pytest.mark.asyncio
    async def test_rewards_in_range(self, trainer):
        for model_name, model_info in ALL_MODELS.items():
            result = await trainer.train_single_model(model_name, model_info)
            assert 0.0 <= result.avg_reward <= 1.0
            assert 0.0 <= result.min_reward <= 1.0
            assert 0.0 <= result.max_reward <= 1.0

    @pytest.mark.asyncio
    async def test_benefits_non_empty(self, trainer):
        for model_name, model_info in ALL_MODELS.items():
            result = await trainer.train_single_model(model_name, model_info)
            assert len(result.benefits) >= 3, f"{model_name} has <3 benefits"


# ── Full Multi-Model Pipeline ──────────────────────────────────────────

class TestFullMultiModelPipeline:
    """Test the complete multi-model training pipeline."""

    @pytest.mark.asyncio
    async def test_trains_all_four_models(self, trainer):
        report = await trainer.train_all_models()
        assert report.total_models == 4

    @pytest.mark.asyncio
    async def test_total_interactions(self, trainer):
        report = await trainer.train_all_models()
        assert report.total_interactions >= 80  # 4 models × ~20 interactions

    @pytest.mark.asyncio
    async def test_total_scenarios(self, trainer):
        report = await trainer.train_all_models()
        assert report.total_scenarios >= 30

    @pytest.mark.asyncio
    async def test_overall_avg_reward(self, trainer):
        report = await trainer.train_all_models()
        assert 0.5 <= report.overall_avg_reward <= 1.0

    @pytest.mark.asyncio
    async def test_all_models_have_results(self, trainer):
        report = await trainer.train_all_models()
        model_names = [r.model_name for r in report.model_results]
        for expected in ALL_MODELS:
            assert expected in model_names

    @pytest.mark.asyncio
    async def test_report_summary_renders(self, trainer):
        report = await trainer.train_all_models()
        summary = report.summary()
        assert "РЕЗУЛЬТАТЫ ОБУЧЕНИЯ ВСЕХ МОДЕЛЕЙ" in summary
        assert "ИТОГИ" in summary
        assert "Qwen2.5-Coder-14B" in summary
        assert "deepseek" in summary
        assert "gemma" in summary

    @pytest.mark.asyncio
    async def test_report_to_dict(self, trainer):
        report = await trainer.train_all_models()
        d = report.to_dict()
        assert isinstance(d, dict)
        assert d["total_models"] == 4
        assert len(d["model_results"]) == 4

    @pytest.mark.asyncio
    async def test_report_serializable_to_json(self, trainer):
        report = await trainer.train_all_models()
        d = report.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["total_models"] == 4

    @pytest.mark.asyncio
    async def test_contrastive_pairs_total(self, trainer):
        report = await trainer.train_all_models()
        assert report.total_contrastive_pairs >= 30


# ── Data Class Tests ───────────────────────────────────────────────────

class TestDataClasses:
    """Test dataclass defaults and serialization."""

    def test_model_training_result_defaults(self):
        r = ModelTrainingResult()
        assert r.status == "not_started"
        assert r.avg_reward == 0.0
        assert r.benefits == []

    def test_model_training_result_to_dict(self):
        r = ModelTrainingResult(model_name="test", avg_reward=0.85)
        d = r.to_dict()
        assert d["model_name"] == "test"
        assert d["avg_reward"] == 0.85

    def test_multi_model_report_defaults(self):
        r = MultiModelTrainingReport()
        assert r.total_models == 0
        assert r.model_results == []

    def test_multi_model_report_summary_empty(self):
        r = MultiModelTrainingReport()
        summary = r.summary()
        assert "РЕЗУЛЬТАТЫ ОБУЧЕНИЯ ВСЕХ МОДЕЛЕЙ" in summary

    def test_multi_model_report_to_dict(self):
        r = MultiModelTrainingReport(total_models=4)
        d = r.to_dict()
        assert d["total_models"] == 4
