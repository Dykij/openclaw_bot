---
name: refactor-engine
description: "Code refactoring: extract methods, eliminate duplication, simplify conditionals, improve naming, modularize large files. Use when: reducing complexity, splitting large files, improving code structure."
version: 1.0.0
---

# Refactor Engine

## Purpose

Systematic refactoring: reduce complexity, eliminate duplication, improve structure.

## Refactoring Catalog

### Extract Method

```python
# BEFORE: Long function with inline logic
def process_order(order):
    # validate
    if not order.items:
        raise ValueError("Empty order")
    if order.total < 0:
        raise ValueError("Negative total")
    # calculate
    subtotal = sum(i.price * i.qty for i in order.items)
    tax = subtotal * 0.2
    total = subtotal + tax
    return total

# AFTER: Extracted validation and calculation
def _validate_order(order):
    if not order.items:
        raise ValueError("Empty order")
    if order.total < 0:
        raise ValueError("Negative total")

def _calculate_total(items, tax_rate=0.2):
    subtotal = sum(i.price * i.qty for i in items)
    return subtotal * (1 + tax_rate)

def process_order(order):
    _validate_order(order)
    return _calculate_total(order.items)
```

### Replace Conditionals with Polymorphism

```python
# BEFORE: Big if/elif chain
def calculate_price(item_type, base):
    if item_type == "book": return base * 0.9
    elif item_type == "electronics": return base * 1.1
    elif item_type == "food": return base * 0.95
    else: return base

# AFTER: Strategy pattern via dict
PRICE_MULTIPLIERS = {"book": 0.9, "electronics": 1.1, "food": 0.95}

def calculate_price(item_type, base):
    return base * PRICE_MULTIPLIERS.get(item_type, 1.0)
```

### Split Large Files (>500 LOC)

1. Identify cohesive groups of functions/classes
2. Extract to focused modules: `_validation.py`, `_processing.py`, `_formatting.py`
3. Create `__init__.py` that re-exports public API
4. Update all imports
5. Run tests after each extraction

## Refactoring Workflow

1. **Ensure tests pass** before any change
2. Make ONE refactoring at a time
3. Run tests after EACH change
4. Commit after EACH successful refactoring
5. If tests break → revert → try smaller step

## Code Smells → Refactoring

| Smell                    | Refactoring                 |
| ------------------------ | --------------------------- |
| Long method (>30 lines)  | Extract method              |
| Duplicate code           | Extract shared helper       |
| Deep nesting (>3 levels) | Guard clauses, early return |
| God class (>500 LOC)     | Split into focused classes  |
| Feature envy             | Move method to data's class |
| Primitive obsession      | Create value object         |
