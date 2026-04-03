"""OpenTelemetry tracing integration for OpenClaw pipeline."""
from __future__ import annotations

import asyncio
import os
import functools
from contextlib import contextmanager
from typing import Any, Optional

_TRACING_ENABLED = os.getenv("OTEL_ENABLED", "").lower() in ("1", "true")

try:
    if _TRACING_ENABLED:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("openclaw")
    else:
        _tracer = None
except ImportError:
    _tracer = None


@contextmanager
def trace_span(name: str, attributes: Optional[dict[str, Any]] = None):
    """Context manager for tracing a span. No-op if tracing disabled."""
    if _tracer is not None:
        with _tracer.start_as_current_span(name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, str(v))
            yield span
    else:
        yield None


def traced(name: Optional[str] = None):
    """Decorator to trace a function call."""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            span_name = name or func.__qualname__
            with trace_span(span_name):
                return await func(*args, **kwargs)
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            span_name = name or func.__qualname__
            with trace_span(span_name):
                return func(*args, **kwargs)
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator
