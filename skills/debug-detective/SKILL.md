---
name: debug-detective
description: "Systematic debugging: root cause analysis, binary search isolation, log analysis, memory/CPU profiling, stack trace interpretation. Use when: diagnosing bugs, analyzing crashes, tracing errors."
version: 1.0.0
---

# Debug Detective

## Purpose

Systematic debugging methodology: isolate, reproduce, diagnose, fix, verify.

## Debugging Workflow

1. **Reproduce**: Get a minimal reproduce case
2. **Isolate**: Binary search to find the failing component
3. **Diagnose**: Read logs, traces, analyze state
4. **Fix**: Make minimal change to correct root cause
5. **Verify**: Run tests, confirm fix doesn't break other paths

## Python Debugging

### Stack Trace Analysis

```python
import traceback
try:
    failing_function()
except Exception:
    traceback.print_exc()  # Full stack trace
    # Or: traceback.format_exc() for string
```

### Interactive Debugger

```python
# Insert breakpoint anywhere
breakpoint()  # Drops into pdb

# Conditional breakpoint
if item.price < 0:
    breakpoint()
```

### Memory Profiling

```bash
# Track memory allocations
python -m tracemalloc script.py

# Get top memory consumers
python -c "
import tracemalloc
tracemalloc.start()
# ... run code ...
snapshot = tracemalloc.take_snapshot()
for stat in snapshot.statistics('lineno')[:10]:
    print(stat)
"
```

### CPU Profiling

```bash
python -m cProfile -s cumtime script.py | head -30
# Or: py-spy for live process
py-spy top --pid <PID>
```

## Log Analysis Patterns

```bash
# Find errors in last 100 lines
tail -100 /tmp/app.log | grep -i "error\|exception\|traceback"

# Timeline of events around failure
grep -B5 -A5 "CRITICAL" /tmp/app.log

# Count error types
grep "ERROR" /tmp/app.log | awk '{print $NF}' | sort | uniq -c | sort -rn
```

## Common Root Causes

| Symptom        | Likely Cause                  | Check                     |
| -------------- | ----------------------------- | ------------------------- |
| Timeout        | Network/DNS, slow query       | Check latency, DB explain |
| OOM            | Memory leak, unbounded cache  | tracemalloc, gc stats     |
| Race condition | Missing lock, shared state    | Review async code         |
| Silent failure | Broad except, swallowed error | Search `except Exception` |
| Intermittent   | Timing, resource exhaustion   | Add logging, check limits |
