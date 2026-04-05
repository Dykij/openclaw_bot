"""LLM subsystem — gateway routing, inference, OpenRouter, model management.

Submodules:
  - gateway          : Unified LLM entry point (route_llm, configure, etc.)
  - inference_client : Local vLLM API wrapper (OpenAI-compatible)
  - openrouter       : Cloud LLM API client (circuit breaker + retry)
  - model_manager    : WSL-based GPU model swapping + LoRA support
  - hitl             : Human-in-the-Loop approval gate
  - context_bridge   : 3-layer persistent context transfer for model swaps
"""

from src.llm.gateway import route_llm, configure
from src.llm.hitl import ApprovalRequest

__all__ = ["route_llm", "configure", "ApprovalRequest"]
