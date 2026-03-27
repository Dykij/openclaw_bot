"""Inference optimiser package (SmartModelRouter, Budget, Metrics, BatchScheduler)."""

from src.ai.inference._shared import (
    BatchMetrics,
    InferenceMetrics,
    ModelPerformance,
    ModelProfile,
    RoutingTask,
    TokenBudget,
    VRAM_TOTAL_GB,
)
from src.ai.inference.batch_scheduler import DynamicBatchScheduler
from src.ai.inference.budget import AdaptiveTokenBudget
from src.ai.inference.metrics import InferenceMetricsCollector
from src.ai.inference.router import SmartModelRouter
from src.ai.inference.speculative import (
    ChunkedPrefillConfig,
    PrefixCachingConfig,
    SpeculativeDecodingConfig,
    build_optimized_vllm_args,
)

__all__ = [
    "AdaptiveTokenBudget",
    "BatchMetrics",
    "ChunkedPrefillConfig",
    "DynamicBatchScheduler",
    "InferenceMetrics",
    "InferenceMetricsCollector",
    "ModelPerformance",
    "ModelProfile",
    "PrefixCachingConfig",
    "RoutingTask",
    "SmartModelRouter",
    "SpeculativeDecodingConfig",
    "TokenBudget",
    "VRAM_TOTAL_GB",
    "build_optimized_vllm_args",
]
