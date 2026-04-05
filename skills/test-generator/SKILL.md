---
name: test-generator
description: "Test generation: unit tests, integration tests, mocking, fixtures, coverage targets. Use when: writing tests, setting up test infrastructure, mocking external services."
version: 1.0.0
---

# Test Generator

## Purpose

Generate comprehensive tests: unit, integration, mocking patterns for Python and TypeScript.

## Python (pytest)

### Unit Test Template

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.chat.return_value = {"choices": [{"message": {"content": "ok"}}]}
    return client

class TestPipelineExecutor:
    async def test_execute_basic_task(self, mock_client):
        executor = PipelineExecutor(client=mock_client)
        result = await executor.execute("Analyze this")
        assert result.status == "completed"
        mock_client.chat.assert_called_once()

    async def test_execute_empty_input_raises(self, mock_client):
        executor = PipelineExecutor(client=mock_client)
        with pytest.raises(ValueError, match="empty"):
            await executor.execute("")

    async def test_execute_timeout_retries(self, mock_client):
        mock_client.chat.side_effect = [TimeoutError, {"choices": [{"message": {"content": "ok"}}]}]
        executor = PipelineExecutor(client=mock_client)
        result = await executor.execute("test")
        assert result.status == "completed"
        assert mock_client.chat.call_count == 2
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("", ""),
    ("123", "123"),
    ("ПриВет", "ПРИВЕТ"),
])
def test_uppercase(input, expected):
    assert input.upper() == expected
```

## TypeScript (Vitest)

```typescript
import { describe, it, expect, vi } from "vitest";

describe("ApiClient", () => {
  it("fetches data successfully", async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, json: () => ({ data: [] }) });
    const client = new ApiClient(mockFetch);
    const result = await client.getData();
    expect(result).toEqual({ data: [] });
    expect(mockFetch).toHaveBeenCalledOnce();
  });

  it("throws on network error", async () => {
    const mockFetch = vi.fn().mockRejectedValue(new Error("Network error"));
    const client = new ApiClient(mockFetch);
    await expect(client.getData()).rejects.toThrow("Network error");
  });
});
```

## Coverage Targets

| Metric            | Target |
| ----------------- | ------ |
| Line coverage     | ≥70%   |
| Branch coverage   | ≥70%   |
| Function coverage | ≥70%   |
| Critical paths    | 100%   |

## Rules

1. Test behavior, not implementation
2. One assertion per test (prefer)
3. Use descriptive test names: `test_<what>_<when>_<then>`
4. Mock only external boundaries (APIs, DB, file system)
5. No tests that depend on execution order

---

name: test-generator
description: 'Automated test generation: unit tests, integration tests, property-based testing, mocking strategies. Use when: writing tests, setting up test infrastructure, achieving coverage targets.'
version: 1.0.0

---

# Test Generator

## Purpose

Generate comprehensive tests: unit, integration, property-based. Target 70%+ coverage.

## Python Test Template (pytest)

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture
def mock_openrouter():
    with patch("src.openrouter_client.route_llm", new_callable=AsyncMock) as mock:
        mock.return_value = "mocked LLM response"
        yield mock

class TestPipelineExecutor:
    """Tests for pipeline executor core logic."""

    @pytest.mark.asyncio
    async def test_execute_simple_task(self, mock_openrouter):
        result = await execute_pipeline("test task")
        assert result is not None
        assert result.status == "completed"
        mock_openrouter.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_handles_timeout(self, mock_openrouter):
        mock_openrouter.side_effect = asyncio.TimeoutError()
        with pytest.raises(PipelineError):
            await execute_pipeline("task")

    @pytest.mark.parametrize("input_text,expected", [
        ("", "empty"),
        ("hello", "processed"),
        ("x" * 10000, "truncated"),
    ])
    def test_input_preprocessing(self, input_text, expected):
        result = preprocess(input_text)
        assert result.status == expected
```

## Mocking Strategy

| Layer       | Mock Method                     | Example                       |
| ----------- | ------------------------------- | ----------------------------- |
| LLM API     | `AsyncMock` return_value        | Mock OpenRouter responses     |
| Database    | In-memory SQLite                | `sqlite3.connect(":memory:")` |
| HTTP client | `respx` / `httpx.MockTransport` | Mock external APIs            |
| File system | `tmp_path` fixture              | Pytest built-in               |
| Time        | `freezegun`                     | Deterministic timestamps      |

## Test Naming Convention

```python
def test_{unit}_{scenario}_{expected}():
    """
    test_pipeline_executor_empty_input_returns_error
    test_rate_limiter_burst_blocks_after_threshold
    test_memory_gc_stale_entries_removed
    """
```

## Coverage Targets

| Module         | Target | Priority |
| -------------- | ------ | -------- |
| Pipeline core  | 80%    | P0       |
| LLM gateway    | 75%    | P0       |
| API endpoints  | 70%    | P1       |
| Utilities      | 90%    | P1       |
| Config parsing | 85%    | P2       |

## Rules

1. One assertion per test (prefer)
2. Test behavior, not implementation
3. Use fixtures for shared setup
4. Mock at the boundary (HTTP, DB, FS)
5. Run `pytest --tb=short -q` before each commit
