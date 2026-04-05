---
name: api-integrator
description: "REST/GraphQL/gRPC API design and integration: authentication, rate limiting, error handling, OpenAPI specs, webhook patterns. Use when: designing APIs, integrating external services, building API clients, handling auth flows."
version: 1.0.0
---

# API Integrator

## Purpose

Expert API design, integration, and client implementation across REST, GraphQL, and gRPC.

## REST API Design

### Endpoint Naming

- Use nouns, not verbs: `GET /users` not `GET /getUsers`
- Use plural: `/users` not `/user`
- Nest for relationships: `GET /users/{id}/orders`
- Use query params for filtering: `GET /users?role=admin&active=true`

### HTTP Methods

| Method | Idempotent | Safe | Use Case        |
| ------ | ---------- | ---- | --------------- |
| GET    | Yes        | Yes  | Read resource   |
| POST   | No         | No   | Create resource |
| PUT    | Yes        | No   | Full replace    |
| PATCH  | No         | No   | Partial update  |
| DELETE | Yes        | No   | Remove resource |

### Status Codes

- `200` Success, `201` Created, `204` No Content
- `400` Bad Request, `401` Unauthorized, `403` Forbidden, `404` Not Found, `409` Conflict, `422` Unprocessable, `429` Too Many Requests
- `500` Server Error, `502` Bad Gateway, `503` Service Unavailable

## Authentication Patterns

```python
# Bearer token with auto-refresh
class APIClient:
    def __init__(self, base_url: str, api_key: str):
        self._base = base_url
        self._session = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    async def request(self, method: str, path: str, **kwargs):
        for attempt in range(3):
            resp = await self._session.request(method, path, **kwargs)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 1))
                await asyncio.sleep(retry_after)
                continue
            resp.raise_for_status()
            return resp.json()
        raise RateLimitExceeded()
```

## Rate Limiting

1. **Always implement exponential backoff**: base \* 2^attempt + jitter
2. **Respect `Retry-After` header**
3. **Track rate limit headers**: `X-RateLimit-Remaining`, `X-RateLimit-Reset`
4. **Use token bucket or sliding window** for client-side limiting

```python
import asyncio, random

async def retry_with_backoff(func, max_retries=5):
    for attempt in range(max_retries):
        try:
            return await func()
        except (httpx.HTTPStatusError, asyncio.TimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            delay = min(2 ** attempt + random.uniform(0, 1), 60)
            await asyncio.sleep(delay)
```

## Error Handling

```python
# Structured error responses
class APIError:
    status: int
    code: str       # machine-readable: "rate_limited"
    message: str    # human-readable: "Too many requests"
    details: dict   # additional context

# Client-side: always handle specific errors
try:
    result = await client.create_order(data)
except httpx.HTTPStatusError as e:
    if e.response.status_code == 409:
        # Conflict — resource already exists
        return await client.get_order(data["id"])
    elif e.response.status_code == 422:
        raise ValidationError(e.response.json())
    raise
```

## Webhook Patterns

1. **HMAC signature verification** on all webhook endpoints
2. **Idempotency keys** to handle duplicate deliveries
3. **Async processing** — return 200 immediately, process in background
4. **Retry queue** with exponential backoff for failed deliveries

## OpenAPI / OpenRouter Integration

```python
# OpenRouter-style API call pattern
async def call_openrouter(messages: list, model: str = "deepseek/deepseek-chat-v3-0324:free"):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                "HTTP-Referer": "https://your-app.com",
            },
            json={"model": model, "messages": messages},
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
```
