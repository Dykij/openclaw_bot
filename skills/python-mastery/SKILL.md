---
name: python-mastery
description: "Advanced Python expertise: 3.14 features, async patterns, type system, performance optimization, packaging. Use when: writing/reviewing Python code, solving complex async problems, optimizing performance, applying modern Python patterns (PEP 649/734/750/758/765/768/784)."
version: 1.0.0
---

# Python Mastery

## Purpose

Expert-level Python development with focus on modern standards (3.14+), type safety, and performance.

## Core Knowledge

### Python 3.14 Features (MUST apply when writing new code)

1. **PEP 649 — Deferred Evaluation of Annotations**: Use `from __future__ import annotations` is no longer needed; annotations are lazily evaluated by default.
2. **PEP 734 — Multiple Interpreters in the Stdlib**: `concurrent.interpreters` for true parallelism without GIL contention.
3. **PEP 750 — Template Strings (t-strings)**: `t"Hello {name}"` for safe string interpolation with processing hooks.
4. **PEP 758 — Allow `except` and `except*` without parens**: `except ValueError, TypeError:` syntax.
5. **PEP 765 — Disallow return/break/continue that exit a finally block**.
6. **PEP 768 — Safe External Debugger Interface**: New low-level C API for debugger attach.
7. **PEP 784 — Adding Zstandard to the Standard Library**: `import compression.zstd`.

### Async Patterns (ALWAYS use for I/O)

```python
# Correct: structured concurrency
async with asyncio.TaskGroup() as tg:
    task1 = tg.create_task(fetch_data())
    task2 = tg.create_task(process_data())

# Correct: timeout handling
async with asyncio.timeout(30):
    result = await long_operation()

# Correct: cancellation-safe cleanup
try:
    await risky_operation()
except asyncio.CancelledError:
    await cleanup()
    raise
```

### Type System Best Practices

```python
# Use modern generics (PEP 695)
type Vector[T] = list[T]
def first[T](items: list[T]) -> T: ...

# Use TypeGuard for narrowing
from typing import TypeGuard
def is_valid_config(obj: object) -> TypeGuard[Config]: ...

# Use Protocol over ABC for structural subtyping
from typing import Protocol
class Renderable(Protocol):
    def render(self) -> str: ...
```

### Performance Patterns

1. **Use `__slots__`** for data-heavy classes
2. **Use `functools.cache`** over manual memoization
3. **Use `collections.deque`** for O(1) append/pop from both ends
4. **Use generator expressions** over list comprehensions when iterating once
5. **Use `asyncio.TaskGroup`** for concurrent I/O (not `gather`)
6. **Profile before optimizing**: `python -m cProfile -s cumtime script.py`

### Error Handling

```python
# Use ExceptionGroup for parallel errors (PEP 654)
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(op1())
        tg.create_task(op2())
except* ValueError as eg:
    for exc in eg.exceptions:
        log.error(f"Validation: {exc}")
except* IOError as eg:
    for exc in eg.exceptions:
        log.error(f"IO: {exc}")
```

## Rules

1. ALWAYS use type hints on function signatures
2. NEVER use `Any` — find the actual type or use `object`
3. ALWAYS use `pathlib.Path` over `os.path`
4. ALWAYS use `subprocess.run(shell=False)` — never `os.system`
5. PREFER `dataclasses` or `attrs` over plain dicts for structured data
6. Use `logging` module — never `print()` in production code
7. Use `ruff` for linting and formatting
