"""Rust FFI Hooks — High-performance Python bridge to openclaw_rust_core.

Provides a Python-friendly API on top of the Rust JSON-RPC parser
compiled via PyO3 (maturin). Falls back to pure-Python implementation
when the compiled extension is unavailable.

Usage:
    from src.infra.performance import parse_jsonrpc, build_response
    result = parse_jsonrpc('{"jsonrpc":"2.0","method":"tools/call","id":1}')
    if result.valid:
        print(result.method)

Build the Rust extension:
    cd rust_core && maturin develop --release
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

import structlog

logger = structlog.get_logger("RustFFI")

# ---------------------------------------------------------------------------
# Try importing the Rust extension; fall back to pure Python
# ---------------------------------------------------------------------------

_RUST_AVAILABLE = False

try:
    import openclaw_rust_core as _rust  # type: ignore[import-untyped]
    _RUST_AVAILABLE = True
    logger.info("Rust FFI loaded: openclaw_rust_core (PyO3)")
except ImportError:
    _rust = None
    logger.info("Rust FFI not available — using pure-Python fallback")


# ---------------------------------------------------------------------------
# Shared data class (mirrors Rust's ParseResult)
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    """Result of parsing a JSON-RPC 2.0 message."""
    valid: bool
    method: str
    params_json: str
    id_value: str
    error: str
    is_batch: bool
    batch_size: int


# ---------------------------------------------------------------------------
# Pure-Python fallback parser
# ---------------------------------------------------------------------------

def _py_parse_jsonrpc(raw: str) -> ParseResult:
    """Pure-Python JSON-RPC 2.0 parser (fallback)."""
    trimmed = raw.strip()

    # Batch detection
    if trimmed.startswith("["):
        try:
            arr = json.loads(trimmed)
        except json.JSONDecodeError as e:
            return ParseResult(
                valid=False, method="", params_json="", id_value="",
                error=f"Batch parse error: {e}", is_batch=True, batch_size=0,
            )
        if not arr:
            return ParseResult(
                valid=False, method="", params_json="", id_value="",
                error="Empty batch", is_batch=True, batch_size=0,
            )
        first = _py_parse_single(json.dumps(arr[0]))
        return ParseResult(
            valid=first.valid, method=first.method,
            params_json=first.params_json, id_value=first.id_value,
            error=first.error, is_batch=True, batch_size=len(arr),
        )

    return _py_parse_single(trimmed)


def _py_parse_single(raw: str) -> ParseResult:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        return ParseResult(
            valid=False, method="", params_json="", id_value="",
            error=f"JSON parse error: {e}", is_batch=False, batch_size=0,
        )

    if not isinstance(obj, dict):
        return ParseResult(
            valid=False, method="", params_json="", id_value="",
            error="Expected JSON object", is_batch=False, batch_size=0,
        )

    if obj.get("jsonrpc") != "2.0":
        return ParseResult(
            valid=False, method="", params_json="", id_value="",
            error='Missing or invalid "jsonrpc" field (must be "2.0")',
            is_batch=False, batch_size=0,
        )

    method = obj.get("method", "")
    if not method or not isinstance(method, str):
        return ParseResult(
            valid=False, method="", params_json="", id_value="",
            error="Missing 'method' field", is_batch=False, batch_size=0,
        )

    params_json = json.dumps(obj.get("params")) if "params" in obj else ""
    id_value = json.dumps(obj.get("id")) if "id" in obj else ""

    return ParseResult(
        valid=True, method=method, params_json=params_json,
        id_value=id_value, error="", is_batch=False, batch_size=1,
    )


# ---------------------------------------------------------------------------
# Public API — auto-selects Rust or Python
# ---------------------------------------------------------------------------

def parse_jsonrpc(raw: str) -> ParseResult:
    """Parse a JSON-RPC 2.0 message (Rust-accelerated when available)."""
    if _RUST_AVAILABLE and _rust is not None:
        r = _rust.parse_jsonrpc(raw)
        return ParseResult(
            valid=r.valid,
            method=r.method,
            params_json=r.params_json,
            id_value=r.id_value,
            error=r.error,
            is_batch=r.is_batch,
            batch_size=r.batch_size,
        )
    return _py_parse_jsonrpc(raw)


def build_response(id_value: str, result_json: str) -> str:
    """Build a JSON-RPC 2.0 success response."""
    if _RUST_AVAILABLE and _rust is not None:
        return _rust.build_response(id_value, result_json)
    id_obj = json.loads(id_value) if id_value else None
    result_obj = json.loads(result_json) if result_json else None
    return json.dumps({"jsonrpc": "2.0", "result": result_obj, "id": id_obj})


def build_error_response(id_value: str, code: int, message: str) -> str:
    """Build a JSON-RPC 2.0 error response."""
    if _RUST_AVAILABLE and _rust is not None:
        return _rust.build_error_response(id_value, code, message)
    id_obj = json.loads(id_value) if id_value else None
    return json.dumps({
        "jsonrpc": "2.0",
        "error": {"code": code, "message": message},
        "id": id_obj,
    })


def is_rust_available() -> bool:
    """Check if the Rust FFI extension is loaded."""
    return _RUST_AVAILABLE


# ---------------------------------------------------------------------------
# Benchmark utility
# ---------------------------------------------------------------------------

def benchmark_parser(iterations: int = 10000) -> dict:
    """Benchmark Rust vs Python parser performance."""
    test_msg = '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"read_file","arguments":{"path":"/src/main.py"}},"id":42}'

    # Python
    start = time.perf_counter()
    for _ in range(iterations):
        _py_parse_jsonrpc(test_msg)
    py_elapsed = time.perf_counter() - start

    result = {
        "iterations": iterations,
        "python_sec": round(py_elapsed, 4),
        "python_ops_per_sec": round(iterations / py_elapsed),
        "rust_available": _RUST_AVAILABLE,
    }

    if _RUST_AVAILABLE and _rust is not None:
        start = time.perf_counter()
        for _ in range(iterations):
            _rust.parse_jsonrpc(test_msg)
        rust_elapsed = time.perf_counter() - start
        result["rust_sec"] = round(rust_elapsed, 4)
        result["rust_ops_per_sec"] = round(iterations / rust_elapsed)
        result["speedup"] = round(py_elapsed / rust_elapsed, 1) if rust_elapsed > 0 else 0

    return result
