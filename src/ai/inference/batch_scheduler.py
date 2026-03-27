"""Dynamic batch scheduler — adaptive batch sizing and throttle."""

from collections import deque
from typing import List

from src.ai.inference._shared import BatchMetrics, _HISTORY_WINDOW, logger


class DynamicBatchScheduler:
    """Dynamic batch sizing based on current load and VRAM.

    Monitors queue depth, VRAM usage, latency, and throughput.
    Adjusts ``max_batch_size`` and decides whether to throttle.
    """

    def __init__(
        self,
        target_latency_ms: int = 5000,
        max_vram_gb: float = 15.0,
    ) -> None:
        self._target_latency_ms = target_latency_ms
        self._max_vram_gb = max_vram_gb

        self._latencies: deque[float] = deque(maxlen=_HISTORY_WINDOW)
        self._throughputs: deque[float] = deque(maxlen=_HISTORY_WINDOW)
        self._queue_depth: int = 0
        self._total_tokens_in: int = 0
        self._total_tokens_out: int = 0
        self._total_requests: int = 0

        self._batch_size: int = 1
        self._min_batch: int = 1
        self._max_batch: int = 32
        self._throttled: bool = False

        logger.info(
            "DynamicBatchScheduler initialised",
            target_latency_ms=target_latency_ms,
            max_vram_gb=max_vram_gb,
        )

    def record_request(self, tokens_in: int, tokens_out: int, latency_ms: float) -> None:
        self._total_requests += 1
        self._total_tokens_in += tokens_in
        self._total_tokens_out += tokens_out
        self._latencies.append(latency_ms)

        total_tokens = tokens_in + tokens_out
        if latency_ms > 0:
            tps = (total_tokens / latency_ms) * 1000.0
            self._throughputs.append(tps)

        self._recalculate()

    def get_optimal_batch_size(self) -> int:
        return self._batch_size

    def should_throttle(self) -> bool:
        return self._throttled

    def set_queue_depth(self, depth: int) -> None:
        self._queue_depth = max(0, depth)

    def get_metrics(self) -> BatchMetrics:
        return BatchMetrics(
            queue_depth=self._queue_depth,
            avg_latency_ms=self._avg(self._latencies),
            throughput_tps=self._avg(self._throughputs),
            batch_size=self._batch_size,
            throttled=self._throttled,
        )

    def _recalculate(self) -> None:
        avg_latency = self._avg(self._latencies)

        if avg_latency > 0 and avg_latency < self._target_latency_ms * 0.7:
            if self._queue_depth > self._batch_size:
                self._batch_size = min(self._batch_size + 1, self._max_batch)
        elif avg_latency > self._target_latency_ms:
            self._batch_size = max(self._batch_size - 1, self._min_batch)

        self._throttled = (
            avg_latency > self._target_latency_ms * 2
            or self._queue_depth > self._max_batch * 4
        )

        if self._throttled:
            logger.warning(
                "Throttling enabled",
                avg_latency_ms=round(avg_latency, 1),
                queue_depth=self._queue_depth,
            )

    @staticmethod
    def _avg(dq: deque[float]) -> float:
        return sum(dq) / len(dq) if dq else 0.0
