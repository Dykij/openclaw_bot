---
name: code-review-autopilot
description: "Automated code review: detect anti-patterns, security issues, performance problems, style violations. Use when: reviewing PRs, auditing code quality, finding bugs before merge."
version: 1.0.0
---

# Code Review Autopilot

## Purpose

Systematic code review: security, performance, correctness, style.

## Review Checklist

### Security (P0 — block merge)

- [ ] No hardcoded secrets/keys/tokens
- [ ] All user input validated at boundary
- [ ] SQL queries parameterized
- [ ] No `eval()`, `exec()`, `shell=True` with user data
- [ ] HTTPS for all external calls
- [ ] Auth checks on every endpoint

### Correctness (P1)

- [ ] Error cases handled (not just happy path)
- [ ] Edge cases: empty lists, None, zero, negative numbers
- [ ] Async code: no race conditions, proper cancellation
- [ ] Resource cleanup: files closed, connections released

### Performance (P2)

- [ ] No N+1 queries
- [ ] No unnecessary allocations in hot loops
- [ ] Pagination for large result sets
- [ ] Appropriate caching for expensive operations

### Style (P3)

- [ ] Type annotations on all functions
- [ ] No `Any` type — use specific types
- [ ] Functions under 50 lines
- [ ] Files under 700 LOC

## Common Anti-Patterns

```python
# BAD: catching broad exception
try:
    result = process()
except Exception:
    pass  # Silent failure!

# GOOD: specific exception, logging
try:
    result = process()
except ValueError as e:
    logger.error("Validation failed", error=str(e))
    raise
```

```python
# BAD: mutable default argument
def add_item(item, items=[]):
    items.append(item)
    return items

# GOOD: None sentinel
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

## Review Template

```markdown
### Summary

Brief description of changes.

### Issues Found

- **[P0/Security]** Hardcoded API key in line 42
- **[P1/Bug]** Missing null check for user.email
- **[P2/Perf]** N+1 query in get_user_orders loop

### Suggestions

- Consider extracting helper for repeated validation logic
```
