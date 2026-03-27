"""Inference metrics collector — TPS / TTFT / ITL / Prometheus export."""

import time
from collections import defaultdict, deque
from typing import Dict, Optional

from src.ai.inference._shared import (
    InferenceMetrics,
    ModelPerformance,
    VRAM_TOTAL_GB,
    _HISTORY_WINDOW,
    logger,
)


class _ModelAccumulator:
    __slots__ = ("count", "total_latency_ms", "total_tokens", "successes")

    def __init__(self) -> None:
        self.count: int = 0
        self.total_latency_ms: float = 0.0
        self.total_tokens: int = 0
        self.successes: int = 0


class InferenceMetricsCollector:
    """Collect and expose inference metrics (TPS, TTFT, ITL, cache, VRAM)."""

    def __init__(self) -> None:
        self._total_requests: int = 0
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0

        self._latencies: deque[float] = deque(maxlen=_HISTORY_WINDOW)
        self._tps_values: deque[float] = deque(maxlen=_HISTORY_WINDOW)
        self._ttft_values: deque[float] = deque(maxlen=_HISTORY_WINDOW)

        self._cache_hits: int = 0
        self._cache_misses: int = 0

        self._model_stats: Dict[str, _ModelAccumulator] = defaultdict(_ModelAccumulator)
        self._start_time: float = time.monotonic()

        logger.info("InferenceMetricsCollector initialised")

    def record_inference(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_latency_ms: float,
        first_token_ms: float = 0,
    ) -> None:
        self._total_requests += 1
        self._total_prompt_tokens += prompt_tokens
        self._total_completion_tokens += completion_tokens
        self._latencies.append(total_latency_ms)

        total_tokens = prompt_tokens + completion_tokens
        if total_latency_ms > 0:
            tps = (total_tokens / total_latency_ms) * 1000.0
            self._tps_values.append(tps)

        if first_token_ms > 0:
            self._ttft_values.append(first_token_ms)

        acc = self._model_stats[model]
        acc.count += 1
        acc.total_latency_ms += total_latency_ms
        acc.total_tokens += total_tokens
        acc.successes += 1

    def record_cache_hit(self) -> None:
        self._cache_hits += 1

    def record_cache_miss(self) -> None:
        self._cache_misses += 1

    def record_failure(self, model: str) -> None:
        self._model_stats[model].count += 1

    def get_metrics(self) -> InferenceMetrics:
        total_cache = self._cache_hits + self._cache_misses
        avg_tps = self._avg(self._tps_values)
        vram_est = min(VRAM_TOTAL_GB, 4.0 + avg_tps * 0.01)

        avg_itl = 0.0
        if self._total_completion_tokens > 0 and self._latencies:
            avg_itl = sum(self._latencies) / self._total_completion_tokens

        return InferenceMetrics(
            total_requests=self._total_requests,
            avg_tps=round(avg_tps, 2),
            avg_ttft_ms=round(self._avg(self._ttft_values), 2),
            avg_itl_ms=round(avg_itl, 2),
            cache_hit_rate=round(self._cache_hits / total_cache, 4) if total_cache else 0.0,
            vram_estimate_gb=round(vram_est, 2),
        )

    def get_model_performance(self, model: str) -> Optional[ModelPerformance]:
        acc = self._model_stats.get(model)
        if acc is None or acc.count == 0:
            return None

        avg_lat = acc.total_latency_ms / acc.count
        avg_tps = (acc.total_tokens / acc.total_latency_ms * 1000.0) if acc.total_latency_ms else 0
        success = acc.successes / acc.count if acc.count else 1.0

        return ModelPerformance(
            model=model,
            total_inferences=acc.count,
            avg_tps=round(avg_tps, 2),
            avg_latency_ms=round(avg_lat, 2),
            success_rate=round(success, 4),
        )

    def export_prometheus(self) -> str:
        m = self.get_metrics()
        lines = [
            "# HELP openclaw_inference_total Total inference requests.",
            "# TYPE openclaw_inference_total counter",
            f"openclaw_inference_total {m.total_requests}",
            "",
            "# HELP openclaw_inference_avg_tps Average tokens per second.",
            "# TYPE openclaw_inference_avg_tps gauge",
            f"openclaw_inference_avg_tps {m.avg_tps}",
            "",
            "# HELP openclaw_inference_avg_ttft_ms Average time to first token (ms).",
            "# TYPE openclaw_inference_avg_ttft_ms gauge",
            f"openclaw_inference_avg_ttft_ms {m.avg_ttft_ms}",
            "",
            "# HELP openclaw_inference_avg_itl_ms Average inter-token latency (ms).",
            "# TYPE openclaw_inference_avg_itl_ms gauge",
            f"openclaw_inference_avg_itl_ms {m.avg_itl_ms}",
            "",
            "# HELP openclaw_inference_cache_hit_rate KV-cache hit rate.",
            "# TYPE openclaw_inference_cache_hit_rate gauge",
            f"openclaw_inference_cache_hit_rate {m.cache_hit_rate}",
            "",
            "# HELP openclaw_inference_vram_estimate_gb Estimated VRAM usage (GB).",
            "# TYPE openclaw_inference_vram_estimate_gb gauge",
            f"openclaw_inference_vram_estimate_gb {m.vram_estimate_gb}",
            "",
            "# HELP openclaw_inference_prompt_tokens_total Total prompt tokens processed.",
            "# TYPE openclaw_inference_prompt_tokens_total counter",
            f"openclaw_inference_prompt_tokens_total {self._total_prompt_tokens}",
            "",
            "# HELP openclaw_inference_completion_tokens_total Total completion tokens generated.",
            "# TYPE openclaw_inference_completion_tokens_total counter",
            f"openclaw_inference_completion_tokens_total {self._total_completion_tokens}",
        ]

        for model, acc in self._model_stats.items():
            safe_name = model.replace("/", "_").replace("-", "_").replace(".", "_")
            if acc.count > 0:
                avg_lat = acc.total_latency_ms / acc.count
                lines.extend([
                    "",
                    f"# HELP openclaw_model_avg_latency_ms Average latency for {model}.",
                    "# TYPE openclaw_model_avg_latency_ms gauge",
                    f'openclaw_model_avg_latency_ms{{model="{safe_name}"}} {avg_lat:.2f}',
                    f'openclaw_model_inferences_total{{model="{safe_name}"}} {acc.count}',
                ])

        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _avg(dq: deque[float]) -> float:
        return sum(dq) / len(dq) if dq else 0.0
