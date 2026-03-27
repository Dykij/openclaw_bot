"""Speculative decoding, chunked prefill, and prefix caching configs.

References:
- vLLM: Efficient Memory Management for LLM Serving (arXiv:2309.06180)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SpeculativeDecodingConfig:
    """Configuration for speculative decoding (vLLM paper).

    Two modes:
    - N-gram (``use_ngram=True``, default): no extra VRAM.
    - Draft-model (``use_ngram=False``): small draft model verifies in batch.
    """

    enabled: bool = False
    use_ngram: bool = True
    ngram_prompt_lookup_max: int = 8
    ngram_prompt_lookup_min: int = 1
    draft_model: str = "Qwen/Qwen2.5-0.5B-Instruct"
    num_speculative_tokens: int = 8

    def to_vllm_args(self) -> List[str]:
        if not self.enabled:
            return []
        import json as _json

        if self.use_ngram:
            cfg = {
                "method": "ngram",
                "num_speculative_tokens": self.num_speculative_tokens,
                "ngram_prompt_lookup_max": self.ngram_prompt_lookup_max,
                "ngram_prompt_lookup_min": self.ngram_prompt_lookup_min,
            }
        else:
            cfg = {
                "method": "draft_model",
                "draft_model": self.draft_model,
                "num_speculative_tokens": self.num_speculative_tokens,
            }
        return ["--speculative-config", _json.dumps(cfg)]

    def estimated_vram_overhead_gb(self) -> float:
        if not self.enabled:
            return 0.0
        return 0.0 if self.use_ngram else 1.0


@dataclass
class ChunkedPrefillConfig:
    """Chunked prefill — break long prompts to reduce TTFT."""

    enabled: bool = False
    max_num_batched_tokens: int = 4096

    def to_vllm_args(self) -> List[str]:
        if not self.enabled:
            return []
        return [
            "--enable-chunked-prefill",
            "--max-num-batched-tokens",
            str(self.max_num_batched_tokens),
        ]


@dataclass
class PrefixCachingConfig:
    """Automatic KV-cache reuse for shared prompt prefixes."""

    enabled: bool = False

    def to_vllm_args(self) -> List[str]:
        if not self.enabled:
            return []
        return ["--enable-prefix-caching"]


def build_optimized_vllm_args(
    speculative: Optional[SpeculativeDecodingConfig] = None,
    chunked_prefill: Optional[ChunkedPrefillConfig] = None,
    prefix_caching: Optional[PrefixCachingConfig] = None,
) -> List[str]:
    """Merge all optimisation configs into a single vLLM CLI argument list."""
    result: List[str] = []
    if speculative is not None:
        result.extend(speculative.to_vllm_args())
    if chunked_prefill is not None:
        result.extend(chunked_prefill.to_vllm_args())
    if prefix_caching is not None:
        result.extend(prefix_caching.to_vllm_args())
    return result
