"""Custom exception hierarchy for OpenClaw Bot.

Provides specific, typed exceptions instead of bare ``Exception`` catches.
Each exception carries structured context for debugging.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class OpenClawError(Exception):
    """Base exception for all OpenClaw Bot errors."""

    def __init__(self, message: str = "", *, context: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.context: Dict[str, Any] = context or {}


# ---------------------------------------------------------------------------
# LLM / Inference errors
# ---------------------------------------------------------------------------

class LLMError(OpenClawError):
    """Base class for LLM inference errors."""
    pass


class LLMProviderError(LLMError):
    """Raised when an LLM provider (OpenRouter, vLLM) returns an error."""

    def __init__(
        self,
        message: str = "",
        *,
        provider: str = "",
        model: str = "",
        status_code: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = context or {}
        ctx.update({"provider": provider, "model": model, "status_code": status_code})
        super().__init__(message, context=ctx)
        self.provider = provider
        self.model = model
        self.status_code = status_code


class LLMEmptyResponseError(LLMError):
    """Raised when an LLM returns an empty or None response."""
    pass


class LLMRateLimitError(LLMError):
    """Raised when hitting API rate limits (HTTP 429)."""

    def __init__(self, message: str = "", *, retry_after: float = 0.0, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class CircuitBreakerOpenError(LLMError):
    """Raised when the circuit breaker is open for a model."""

    def __init__(self, model: str = "", **kwargs: Any) -> None:
        super().__init__(f"Circuit breaker open for model: {model}", **kwargs)
        self.model = model


# ---------------------------------------------------------------------------
# Pipeline errors
# ---------------------------------------------------------------------------

class PipelineError(OpenClawError):
    """Base class for pipeline execution errors."""
    pass


class PipelineChainError(PipelineError):
    """Raised when the entire pipeline chain fails."""
    pass


class PipelineRoleError(PipelineError):
    """Raised when a specific role in the chain fails."""

    def __init__(self, message: str = "", *, role: str = "", brigade: str = "", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.role = role
        self.brigade = brigade


# ---------------------------------------------------------------------------
# Memory errors
# ---------------------------------------------------------------------------

class MemoryError(OpenClawError):
    """Base class for memory system errors."""
    pass


class MemoryPersistenceError(MemoryError):
    """Raised when memory persistence (SQLite/JSON) fails."""
    pass


class MemoryCapacityError(MemoryError):
    """Raised when memory tiers are full and cannot accept new items."""
    pass


# ---------------------------------------------------------------------------
# Safety errors
# ---------------------------------------------------------------------------

class SafetyError(OpenClawError):
    """Base class for safety-related errors."""
    pass


class PromptInjectionError(SafetyError):
    """Raised when a prompt injection attempt is detected."""
    pass


class HallucinationDetectedError(SafetyError):
    """Raised when significant hallucination is detected in output."""
    pass


# ---------------------------------------------------------------------------
# Research errors
# ---------------------------------------------------------------------------

class ResearchError(OpenClawError):
    """Base class for research pipeline errors."""
    pass


class SearchError(ResearchError):
    """Raised when web/academic search fails."""
    pass


class EvidenceError(ResearchError):
    """Raised when evidence scoring or verification fails."""
    pass
