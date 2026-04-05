---
name: api-architect
description: "Design and validate API schemas (OpenAPI 3.1, JSON Schema, Pydantic), generate SDK stubs, plan contract-first development. Use when: designing new APIs, validating schemas, generating API clients, planning microservice contracts."
version: 1.0.0
---

# API Architect

## Purpose

Design contract-first APIs: OpenAPI 3.1 specs, JSON Schema validation, Pydantic models, SDK generation.

## Contract-First Workflow

1. **Define OpenAPI spec** (YAML) before writing any handler code
2. **Validate spec** via `redocly lint openapi.yaml`
3. **Generate server stubs** from the spec
4. **Generate client SDKs** for consumers
5. **Keep spec and code in sync** via CI check

## OpenAPI 3.1 Template

```yaml
openapi: "3.1.0"
info:
  title: Service API
  version: "1.0.0"
paths:
  /items:
    get:
      operationId: listItems
      summary: List all items
      parameters:
        - name: limit
          in: query
          schema: { type: integer, minimum: 1, maximum: 100, default: 20 }
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: array
                items: { $ref: "#/components/schemas/Item" }
components:
  schemas:
    Item:
      type: object
      required: [id, name]
      properties:
        id: { type: string, format: uuid }
        name: { type: string, minLength: 1, maxLength: 255 }
        created_at: { type: string, format: date-time }
```

## Pydantic Models from Schema

```python
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

class Item(BaseModel):
    id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    created_at: datetime | None = None
```

## Validation Rules

- All endpoints MUST have `operationId`
- All request bodies MUST have validation (`minLength`, `maximum`, `pattern`)
- All 4xx/5xx responses MUST have error schema
- Use `$ref` for shared schemas — never inline complex types
- Pagination: use `limit`/`offset` or cursor-based

## SDK Generation

```bash
# TypeScript client
npx openapi-typescript openapi.yaml -o src/api-types.ts

# Python client
openapi-python-client generate --path openapi.yaml
```
