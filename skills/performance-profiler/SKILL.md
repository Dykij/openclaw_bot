---
name: performance-profiler
description: "Performance profiling: Python cProfile/py-spy, Node.js --prof, Rust flamegraph, memory profiling, query optimization. Use when: optimizing hot paths, finding bottlenecks, reducing latency."
version: 1.0.0
---

# Performance Profiler

## Purpose

Profile and optimize code performance across Python, TypeScript/Node.js, and Rust.

## Python Profiling

### CPU Profiling

```bash
# cProfile (built-in)
python -m cProfile -s cumtime script.py 2>&1 | head -30

# py-spy (sampling, low overhead — for production)
py-spy record -o profile.svg -- python script.py
py-spy top --pid <PID>  # Live view
```

### Memory Profiling

```bash
# tracemalloc (built-in)
python -c "
import tracemalloc; tracemalloc.start()
# ... your code ...
snapshot = tracemalloc.take_snapshot()
for stat in snapshot.statistics('lineno')[:10]: print(stat)
"

# memray (detailed)
memray run script.py
memray flamegraph output.bin
```

### Async Profiling

```python
import time, asyncio

async def timed(coro, label):
    start = time.perf_counter()
    result = await coro
    elapsed = time.perf_counter() - start
    print(f"{label}: {elapsed:.3f}s")
    return result
```

## Node.js Profiling

```bash
# V8 CPU profiling
node --prof script.js
node --prof-process isolate-*.log > profile.txt

# Clinic.js (comprehensive)
npx clinic doctor -- node server.js
npx clinic flame -- node server.js
```

## Rust Profiling

```bash
# Flamegraph
cargo install flamegraph
cargo flamegraph --bin my-app

# Criterion benchmarks
cargo bench
```

## Optimization Checklist

| Check                           | Impact | Effort |
| ------------------------------- | ------ | ------ |
| Cache expensive computations    | High   | Low    |
| Reduce allocations in hot loops | High   | Medium |
| Use batch DB operations         | High   | Medium |
| Replace O(n²) with O(n log n)   | High   | Medium |
| Use connection pooling          | Medium | Low    |
| Enable gzip compression         | Medium | Low    |
| Lazy-load rarely used modules   | Low    | Low    |

## Rules

1. **Measure BEFORE optimizing** — gut feelings are wrong
2. Profile in **production-like** conditions
3. Optimize the **top 3 bottlenecks** only — 80/20 rule
4. Add **benchmarks** to prevent regressions
