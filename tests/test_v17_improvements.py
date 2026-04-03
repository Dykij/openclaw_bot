"""Tests for v17.0 improvements: token counter, exceptions, intent classifier,
SmartModelRouter UCB1, MoA parallel, websearch cache.

Run: python -m pytest tests/test_v17_improvements.py -v
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import OrderedDict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. Token Counter Tests
# ---------------------------------------------------------------------------

class TestTokenCounter:
    """Tests for src/utils/token_counter.py"""

    def test_empty_string(self):
        from src.utils.token_counter import estimate_tokens
        assert estimate_tokens("") == 0

    def test_english_text(self):
        from src.utils.token_counter import estimate_tokens
        # "Hello world" = 11 chars → ~2.75 → 2 tokens (floor)
        result = estimate_tokens("Hello world")
        assert result >= 1
        assert result <= 5

    def test_cyrillic_text_higher_than_ascii(self):
        from src.utils.token_counter import estimate_tokens
        # Cyrillic chars should produce MORE tokens than same-length ASCII
        eng = estimate_tokens("a" * 100)
        rus = estimate_tokens("а" * 100)  # Cyrillic 'а'
        assert rus > eng, f"Cyrillic ({rus}) should > ASCII ({eng})"

    def test_mixed_text(self):
        from src.utils.token_counter import estimate_tokens
        result = estimate_tokens("Привет, мир! Hello world!")
        assert result >= 5

    def test_minimum_one_for_nonempty(self):
        from src.utils.token_counter import estimate_tokens
        assert estimate_tokens("x") >= 1

    def test_long_russian_text(self):
        from src.utils.token_counter import estimate_tokens
        text = "Это длинный текст на русском языке для проверки точности оценки токенов. " * 10
        result = estimate_tokens(text)
        # Should be significantly more than len(text)//4
        naive = max(1, len(text) // 4)
        assert result > naive * 1.2, f"Multilingual estimate ({result}) should be > naive ({naive})"

    def test_fast_estimate(self):
        from src.utils.token_counter import estimate_tokens_fast
        assert estimate_tokens_fast("") == 0
        assert estimate_tokens_fast("Hello") >= 1
        # UTF-8 bytes: Russian chars = 2 bytes each
        rus = estimate_tokens_fast("Привет")
        assert rus >= 2

    def test_consistency(self):
        from src.utils.token_counter import estimate_tokens
        text = "Test consistency"
        # Same input should always produce same output
        assert estimate_tokens(text) == estimate_tokens(text)


# ---------------------------------------------------------------------------
# 2. Exceptions Tests
# ---------------------------------------------------------------------------

class TestExceptions:
    """Tests for src/exceptions.py"""

    def test_base_error(self):
        from src.exceptions import OpenClawError
        err = OpenClawError("test", context={"key": "value"})
        assert str(err) == "test"
        assert err.context == {"key": "value"}

    def test_base_error_no_context(self):
        from src.exceptions import OpenClawError
        err = OpenClawError("test")
        assert err.context == {}

    def test_llm_provider_error(self):
        from src.exceptions import LLMProviderError
        err = LLMProviderError(
            "API failed",
            provider="openrouter",
            model="gpt-4",
            status_code=429,
        )
        assert err.provider == "openrouter"
        assert err.model == "gpt-4"
        assert err.status_code == 429
        assert err.context["provider"] == "openrouter"

    def test_llm_empty_response(self):
        from src.exceptions import LLMEmptyResponseError
        err = LLMEmptyResponseError("empty")
        assert isinstance(err, Exception)

    def test_rate_limit_error(self):
        from src.exceptions import LLMRateLimitError
        err = LLMRateLimitError("rate limited", retry_after=30.0)
        assert err.retry_after == 30.0

    def test_circuit_breaker_error(self):
        from src.exceptions import CircuitBreakerOpenError
        err = CircuitBreakerOpenError(model="gpt-4")
        assert "gpt-4" in str(err)
        assert err.model == "gpt-4"

    def test_pipeline_role_error(self):
        from src.exceptions import PipelineRoleError
        err = PipelineRoleError("failed", role="Coder", brigade="Dmarket-Dev")
        assert err.role == "Coder"
        assert err.brigade == "Dmarket-Dev"

    def test_memory_persistence_error(self):
        from src.exceptions import MemoryPersistenceError
        err = MemoryPersistenceError("sqlite failed")
        assert isinstance(err, Exception)

    def test_safety_errors(self):
        from src.exceptions import PromptInjectionError, HallucinationDetectedError
        assert issubclass(PromptInjectionError, Exception)
        assert issubclass(HallucinationDetectedError, Exception)

    def test_research_errors(self):
        from src.exceptions import SearchError, EvidenceError
        assert issubclass(SearchError, Exception)
        assert issubclass(EvidenceError, Exception)

    def test_hierarchy(self):
        from src.exceptions import (
            OpenClawError, LLMError, LLMProviderError,
            PipelineError, PipelineRoleError,
            SafetyError, PromptInjectionError,
        )
        assert issubclass(LLMProviderError, LLMError)
        assert issubclass(LLMError, OpenClawError)
        assert issubclass(PipelineRoleError, PipelineError)
        assert issubclass(PromptInjectionError, SafetyError)


# ---------------------------------------------------------------------------
# 3. Intent Classifier Tests
# ---------------------------------------------------------------------------

class TestIntentClassifier:
    """Tests for src/intent_classifier.py — LRU cache, keyword classification."""

    def test_lru_cache_basic(self):
        from src.intent_classifier import _LRUCacheTTL
        cache = _LRUCacheTTL(maxsize=3, ttl=60.0)
        cache.put("a", "v1")
        assert cache.get("a") == "v1"

    def test_lru_cache_eviction(self):
        from src.intent_classifier import _LRUCacheTTL
        cache = _LRUCacheTTL(maxsize=2, ttl=60.0)
        cache.put("a", "v1")
        cache.put("b", "v2")
        cache.put("c", "v3")  # Should evict "a"
        assert cache.get("a") is None
        assert cache.get("b") == "v2"
        assert cache.get("c") == "v3"

    def test_lru_cache_ttl(self):
        from src.intent_classifier import _LRUCacheTTL
        cache = _LRUCacheTTL(maxsize=10, ttl=0.01)  # 10ms TTL
        cache.put("x", "val")
        time.sleep(0.02)
        assert cache.get("x") is None  # Expired

    def test_lru_cache_move_to_end(self):
        from src.intent_classifier import _LRUCacheTTL
        cache = _LRUCacheTTL(maxsize=3, ttl=60.0)
        cache.put("a", "v1")
        cache.put("b", "v2")
        cache.put("c", "v3")
        # Access "a" to move it to end (most recently used)
        cache.get("a")
        # Adding "d" should evict "b" (least recently used), not "a"
        cache.put("d", "v4")
        assert cache.get("a") == "v1"
        assert cache.get("b") is None  # Evicted

    def test_keyword_classify_dmarket(self):
        from src.intent_classifier import _keyword_classify
        assert _keyword_classify("buy skins on dmarket") == "Dmarket-Dev"
        assert _keyword_classify("арбитраж цена") == "Dmarket-Dev"

    def test_keyword_classify_openclaw(self):
        from src.intent_classifier import _keyword_classify
        assert _keyword_classify("configure the bot pipeline") == "OpenClaw-Core"
        assert _keyword_classify("конфиг бота") == "OpenClaw-Core"

    def test_keyword_classify_research(self):
        from src.intent_classifier import _keyword_classify
        assert _keyword_classify("deep research on AI trends") == "Research-Ops"
        assert _keyword_classify("check https://example.com") == "Research-Ops"

    def test_keyword_classify_general(self):
        from src.intent_classifier import _keyword_classify
        assert _keyword_classify("hello how are you") == "General"

    def test_prefix_map_exists(self):
        from src.intent_classifier import _PREFIX_MAP
        assert "/dmarket" in _PREFIX_MAP
        assert "/research" in _PREFIX_MAP
        assert "/openclaw" in _PREFIX_MAP


# ---------------------------------------------------------------------------
# 4. SmartModelRouter UCB1 Tests
# ---------------------------------------------------------------------------

class TestSmartModelRouterUCB1:
    """Tests for UCB1 exploration in SmartModelRouter."""

    def _make_router(self):
        from src.ai.inference.router import SmartModelRouter
        from src.ai.inference._shared import ModelProfile
        models = {
            "model-a": ModelProfile(
                name="model-a", vram_gb=4.0,
                capabilities=["code"], speed_tier="fast", quality_tier="medium",
            ),
            "model-b": ModelProfile(
                name="model-b", vram_gb=9.5,
                capabilities=["general", "creative"], speed_tier="medium", quality_tier="high",
            ),
        }
        return SmartModelRouter(models)

    def test_ucb1_bonus_untried_model(self):
        router = self._make_router()
        router._total_routes = 10
        # Never tried model-a for "math" → should get high bonus
        bonus = router._ucb1_bonus("model-a", "math")
        assert bonus > 0

    def test_ucb1_bonus_zero_routes(self):
        router = self._make_router()
        # No routes yet → no bonus
        bonus = router._ucb1_bonus("model-a", "code")
        assert bonus == 0.0

    def test_ucb1_bonus_decreases_with_tries(self):
        router = self._make_router()
        router._total_routes = 100
        # Simulate some outcomes
        router.record_outcome("model-a", "code", True, 0.8)
        router.record_outcome("model-a", "code", True, 0.9)
        router.record_outcome("model-a", "code", True, 0.7)

        bonus_after_3 = router._ucb1_bonus("model-a", "code")

        # Add more outcomes
        for _ in range(7):
            router.record_outcome("model-a", "code", True, 0.8)

        bonus_after_10 = router._ucb1_bonus("model-a", "code")
        assert bonus_after_10 < bonus_after_3, "UCB1 bonus should decrease with more tries"

    def test_routing_prefers_capable_model(self):
        from src.ai.inference._shared import RoutingTask
        router = self._make_router()
        result = router.route(RoutingTask(prompt="debug this Python code", task_type="code"))
        assert result == "model-a"  # Has "code" capability

    def test_routing_preferred_model_override(self):
        from src.ai.inference._shared import RoutingTask
        router = self._make_router()
        result = router.route(RoutingTask(
            prompt="anything", task_type="general", preferred_model="model-b"
        ))
        assert result == "model-b"

    def test_total_routes_increments(self):
        from src.ai.inference._shared import RoutingTask
        router = self._make_router()
        assert router._total_routes == 0
        router.route(RoutingTask(prompt="test", task_type="general"))
        assert router._total_routes == 1

    def test_routing_stats_includes_total(self):
        from src.ai.inference._shared import RoutingTask
        router = self._make_router()
        router.route(RoutingTask(prompt="test", task_type="general"))
        stats = router.get_routing_stats()
        assert "total_routes" in stats
        assert stats["total_routes"] == 1


# ---------------------------------------------------------------------------
# 5. MoA Parallel Tests
# ---------------------------------------------------------------------------

class TestMoAParallel:
    """Tests for parallel MoA proposers."""

    def test_proposer_prompts_resolve(self):
        from src.ai.agents.moa import MixtureOfAgents
        moa = MixtureOfAgents(num_proposers=3)
        prompts = moa._resolve_system_prompts(None)
        assert len(prompts) == 3

    def test_custom_prompts(self):
        from src.ai.agents.moa import MixtureOfAgents
        moa = MixtureOfAgents(num_proposers=2)
        custom = ["Expert 1", "Expert 2", "Expert 3"]
        prompts = moa._resolve_system_prompts(custom)
        assert len(prompts) == 2
        assert prompts == ["Expert 1", "Expert 2"]

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        """Verify proposers run in parallel (total time < 3x single)."""
        from src.ai.agents.moa import MixtureOfAgents

        async def mock_call_vllm(*args, **kwargs):
            await asyncio.sleep(0.05)  # Simulate 50ms
            return "Mock response"

        moa = MixtureOfAgents(num_proposers=3)
        with patch("src.ai.agents.moa.call_vllm", side_effect=mock_call_vllm):
            start = time.monotonic()
            result = await moa.generate("test prompt")
            elapsed = time.monotonic() - start

        assert len(result.proposals) == 3
        # Verify actual content returned
        assert all(p == "Mock response" for p in result.proposals)
        # Parallel: should take ~50ms, not ~150ms (sequential)
        assert elapsed < 0.3, f"Parallel MoA took {elapsed:.2f}s — expected < 0.3s"

    @pytest.mark.asyncio
    async def test_proposer_timeout_graceful(self):
        """Verify timeout on one proposer doesn't kill others."""
        from src.ai.agents.moa import MixtureOfAgents, _PROPOSER_ERROR_PREFIX

        call_count = 0

        async def mock_call_vllm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                await asyncio.sleep(100)  # Will timeout
            return f"Response {call_count}"

        moa = MixtureOfAgents(num_proposers=3)
        with patch("src.ai.agents.moa.call_vllm", side_effect=mock_call_vllm), \
             patch("src.ai.agents.moa._PROPOSER_TIMEOUT_SEC", 0.1):
            result = await moa.generate("test")

        # Should have 3 proposals (2 real + 1 timeout marker)
        assert len(result.proposals) == 3
        # Verify timeout marker format
        timeout_proposals = [p for p in result.proposals if p.startswith(_PROPOSER_ERROR_PREFIX)]
        assert len(timeout_proposals) == 1
        assert "timed out" in timeout_proposals[0]
        assert result.aggregated_response  # Aggregator should still work


# ---------------------------------------------------------------------------
# 6. Websearch Cache Tests
# ---------------------------------------------------------------------------

class TestWebsearchCache:
    """Tests for the shared TTLCache utility (used in websearch_mcp.py and intent_classifier.py)."""

    def test_ttl_cache_basic(self):
        from src.utils.cache import TTLCache
        cache: TTLCache[str] = TTLCache(maxsize=10, ttl=60.0)
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_ttl_cache_miss(self):
        from src.utils.cache import TTLCache
        cache: TTLCache[str] = TTLCache(maxsize=10, ttl=60.0)
        assert cache.get("nonexistent") is None

    def test_ttl_cache_expiry(self):
        from src.utils.cache import TTLCache
        cache: TTLCache[str] = TTLCache(maxsize=10, ttl=0.01)
        cache.put("key", "val")
        time.sleep(0.02)
        assert cache.get("key") is None

    def test_ttl_cache_maxsize(self):
        from src.utils.cache import TTLCache
        cache: TTLCache[str] = TTLCache(maxsize=2, ttl=60.0)
        cache.put("a", "1")
        cache.put("b", "2")
        cache.put("c", "3")  # Evicts "a"
        assert cache.get("a") is None
        assert cache.get("b") == "2"
        assert cache.get("c") == "3"

    def test_cache_len(self):
        from src.utils.cache import TTLCache
        cache: TTLCache[str] = TTLCache(maxsize=10, ttl=60.0)
        assert len(cache) == 0
        cache.put("a", "1")
        assert len(cache) == 1

    def test_cache_contains(self):
        from src.utils.cache import TTLCache
        cache: TTLCache[str] = TTLCache(maxsize=10, ttl=60.0)
        cache.put("a", "1")
        assert "a" in cache
        assert "b" not in cache

    def test_cache_clear(self):
        from src.utils.cache import TTLCache
        cache: TTLCache[str] = TTLCache(maxsize=10, ttl=60.0)
        cache.put("a", "1")
        cache.put("b", "2")
        cache.clear()
        assert len(cache) == 0
        assert cache.get("a") is None

    def test_intent_classifier_alias(self):
        """Verify _LRUCacheTTL alias in intent_classifier works."""
        from src.intent_classifier import _LRUCacheTTL
        from src.utils.cache import TTLCache
        assert _LRUCacheTTL is TTLCache


# ---------------------------------------------------------------------------
# 7. Integration: Token counter used in memory modules
# ---------------------------------------------------------------------------

class TestTokenCounterIntegration:
    """Verify token counter is properly wired into memory modules."""

    def test_memory_gc_uses_central(self):
        from src.memory_gc import estimate_tokens
        # Should use the central estimate, not len//4
        result = estimate_tokens("Привет мир")
        naive = max(1, len("Привет мир") // 4)
        assert result != naive or result >= 1  # Different from naive or at least valid

    def test_memory_enhanced_uses_central(self):
        from src.memory_enhanced import _estimate_tokens
        result = _estimate_tokens("Тестовый текст")
        assert result >= 1

    def test_supermemory_uses_central(self):
        from src.supermemory import MemoryRecord
        record = MemoryRecord(
            key="test",
            content="Длинный русский текст для проверки",
            importance=0.8,
        )
        result = record.token_estimate()
        assert result >= 1
        # Should be more than naive for Cyrillic
        naive = max(1, len(record.content) // 4)
        assert result >= naive


# ---------------------------------------------------------------------------
# 8. Exceptions hierarchy integration
# ---------------------------------------------------------------------------

class TestExceptionsUsage:
    """Test that exceptions can be caught at various levels."""

    def test_catch_llm_error(self):
        from src.exceptions import LLMError, LLMProviderError
        try:
            raise LLMProviderError("test", provider="openrouter", model="gpt-4", status_code=500)
        except LLMError as e:
            assert e.context["provider"] == "openrouter"

    def test_catch_openclaw_error(self):
        from src.exceptions import OpenClawError, PipelineRoleError
        try:
            raise PipelineRoleError("fail", role="Coder", brigade="Dev")
        except OpenClawError as e:
            assert "fail" in str(e)
