---
name: async-patterns
description: "Async/concurrency patterns: Python asyncio TaskGroup, JS Promise.allSettled, Rust tokio, structured concurrency, backpressure, cancellation. Use when: designing concurrent systems, fixing race conditions, implementing async pipelines."
version: 1.0.0
---

# Async Patterns

## Purpose

Apply correct concurrency patterns across Python, TypeScript, and Rust. Avoid common pitfalls.

## Python asyncio (3.11+)

### Structured Concurrency (ALWAYS prefer)

```python
async with asyncio.TaskGroup() as tg:
    results = [tg.create_task(fetch(url)) for url in urls]
# All tasks guaranteed done or cancelled here
```

### Semaphore for Backpressure

```python
sem = asyncio.Semaphore(10)  # Max 10 concurrent

async def limited_fetch(url: str):
    async with sem:
        return await httpx.AsyncClient().get(url)
```

### Cancellation-Safe Pattern

```python
try:
    async with asyncio.timeout(30):
        result = await operation()
except TimeoutError:
    logger.warning("Operation timed out")
    result = fallback_value
```

### Queue-Based Pipeline

```python
queue: asyncio.Queue[WorkItem] = asyncio.Queue(maxsize=100)

async def producer():
    async for item in source():
        await queue.put(item)  # Backpressure when full

async def consumer():
    while True:
        item = await queue.get()
        await process(item)
        queue.task_done()
```

## TypeScript / Node.js

### Promise.allSettled (for partial failure tolerance)

```typescript
const results = await Promise.allSettled(urls.map(fetch));
const successes = results.filter((r) => r.status === "fulfilled").map((r) => r.value);
const failures = results.filter((r) => r.status === "rejected").map((r) => r.reason);
```

### AbortController for Cancellation

```typescript
const controller = new AbortController();
setTimeout(() => controller.abort(), 30_000);
const response = await fetch(url, { signal: controller.signal });
```

## Anti-Patterns (NEVER do)

| Anti-pattern                                    | Fix                                         |
| ----------------------------------------------- | ------------------------------------------- |
| `asyncio.gather(*tasks)` without error handling | Use `TaskGroup` or `return_exceptions=True` |
| Fire-and-forget `asyncio.create_task()`         | Store reference, use TaskGroup              |
| `await` in a loop (sequential)                  | Use `TaskGroup` for parallel                |
| Shared mutable state without lock               | Use `asyncio.Lock()`                        |
| Unbounded queue                                 | Set `maxsize` for backpressure              |
