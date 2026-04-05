---
name: error-handler-patterns
description: "Error handling patterns: exception hierarchies, Result types, circuit breakers, retry with backoff, structured logging. Use when: designing error handling, implementing retries, building resilient services."
version: 1.0.0
---

# Error Handler Patterns

## Purpose

Implement robust error handling: typed exceptions, retries, circuit breakers, structured error logging.

## Exception Hierarchy (Python)

```python
class AppError(Exception):
    """Base error with structured context."""
    def __init__(self, message: str, *, code: str = "unknown", context: dict | None = None):
        super().__init__(message)
        self.code = code
        self.context = context or {}

class ValidationError(AppError):
    """Invalid input data."""
    def __init__(self, field: str, message: str):
        super().__init__(f"{field}: {message}", code="validation_error", context={"field": field})

class ExternalServiceError(AppError):
    """External API failure."""
    def __init__(self, service: str, status: int, message: str):
        super().__init__(f"{service} returned {status}: {message}", code="service_error",
                         context={"service": service, "status": status})
```

## Retry with Exponential Backoff

```python
import asyncio, random

async def retry(func, max_attempts=3, base_delay=1.0, max_delay=60.0):
    for attempt in range(max_attempts):
        try:
            return await func()
        except (ExternalServiceError, asyncio.TimeoutError) as e:
            if attempt == max_attempts - 1:
                raise
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
            await asyncio.sleep(delay)
```

## Circuit Breaker

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failures = 0
        self.threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = 0
        self.state = "closed"  # closed | open | half-open

    async def call(self, func):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
            else:
                raise CircuitOpenError()
        try:
            result = await func()
            if self.state == "half-open":
                self.state = "closed"
                self.failures = 0
            return result
        except Exception:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.threshold:
                self.state = "open"
            raise
```

## Rules

1. NEVER catch bare `Exception` — catch specific types
2. NEVER silently swallow errors (`except: pass`)
3. ALWAYS log errors with structured context
4. Retry only on transient errors (network, rate limits)
5. Set timeouts on ALL external calls
