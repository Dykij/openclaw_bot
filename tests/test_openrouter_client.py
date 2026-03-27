"""Unit tests for OpenRouter client — circuit breaker, retries, rate limits."""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.openrouter_client import (
    _circuit_breaker,
    _rate_limit_state,
    _is_circuit_open,
    _record_failure,
    _record_success,
    _update_rate_limits,
    get_rate_limit_info,
)
import time as _time


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------
def test_circuit_initially_closed():
    # Reset state
    _circuit_breaker["failures"] = 0
    _circuit_breaker["last_failure"] = 0.0
    _circuit_breaker["open_until"] = 0.0
    assert not _is_circuit_open()
    print("[PASS] circuit breaker initially closed")


def test_circuit_opens_after_threshold():
    _circuit_breaker["failures"] = 0
    _circuit_breaker["last_failure"] = 0.0
    _circuit_breaker["open_until"] = 0.0

    # Record failures up to threshold (5)
    for _ in range(5):
        _record_failure()

    assert _circuit_breaker["failures"] >= 5
    assert _circuit_breaker["open_until"] > _time.time()
    assert _is_circuit_open()
    print("[PASS] circuit opens after threshold")


def test_circuit_recovers_after_cooldown():
    _circuit_breaker["failures"] = 5
    # Set open_until far in the past (beyond cooldown)
    _circuit_breaker["open_until"] = _time.time() - 10
    _circuit_breaker["last_failure"] = _time.time() - 200
    # Circuit should auto-close because open_until is in the past
    assert not _is_circuit_open()
    # _is_circuit_open resets failures when cooldown expired
    assert _circuit_breaker["failures"] == 0
    print("[PASS] circuit recovers after cooldown")


def test_record_success_resets():
    _circuit_breaker["failures"] = 3
    _circuit_breaker["open_until"] = 0.0
    _record_success()
    assert _circuit_breaker["failures"] == 0
    print("[PASS] record_success resets failures")


# ---------------------------------------------------------------------------
# Rate Limit Tracking
# ---------------------------------------------------------------------------
def test_update_rate_limits():
    headers = {
        "x-ratelimit-remaining-requests": "42",
        "x-ratelimit-remaining-tokens": "100000",
    }
    _update_rate_limits(headers)
    assert _rate_limit_state["requests_remaining"] == 42
    assert _rate_limit_state["tokens_remaining"] == 100000
    print("[PASS] rate limit tracking from headers")


def test_rate_limit_info():
    _rate_limit_state["requests_remaining"] = 50
    _rate_limit_state["tokens_remaining"] = 10000
    _circuit_breaker["failures"] = 0
    _circuit_breaker["open_until"] = 0.0
    info = get_rate_limit_info()
    assert info["requests_remaining"] == 50
    assert info["tokens_remaining"] == 10000
    assert info["circuit_open"] is False
    print("[PASS] get_rate_limit_info")


def test_update_rate_limits_missing_headers():
    """Headers without rate limit info should not crash."""
    _rate_limit_state["requests_remaining"] = 999
    _rate_limit_state["tokens_remaining"] = 999999
    _update_rate_limits({"content-type": "application/json"})
    assert _rate_limit_state["requests_remaining"] == 999  # unchanged
    print("[PASS] missing rate limit headers handled")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_circuit_initially_closed()
    test_circuit_opens_after_threshold()
    test_circuit_recovers_after_cooldown()
    test_record_success_resets()
    test_update_rate_limits()
    test_rate_limit_info()
    test_update_rate_limits_missing_headers()
    print("\n✅ All OpenRouter client tests passed!")
