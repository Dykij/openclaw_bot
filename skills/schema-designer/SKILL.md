---
name: schema-designer
description: "Database schema design: PostgreSQL, SQLite, Redis data modeling, migrations, indexing strategy. Use when: designing tables, writing migrations, optimizing queries, choosing data models."
version: 1.0.0
---

# Schema Designer

## Purpose

Design efficient database schemas: normalization, indexing, migrations, query optimization.

## PostgreSQL Schema Template

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    priority INT NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- Indexes for common query patterns
CREATE INDEX idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX idx_tasks_created ON tasks(created_at DESC);
CREATE INDEX idx_tasks_payload ON tasks USING GIN(payload);
```

## Indexing Strategy

| Query Pattern                 | Index Type          |
| ----------------------------- | ------------------- |
| Exact match (WHERE x = ?)     | B-tree (default)    |
| Range (WHERE x > ? AND x < ?) | B-tree              |
| Full-text search              | GIN with tsvector   |
| JSON field queries            | GIN on JSONB column |
| Geospatial                    | GiST                |
| Array containment             | GIN                 |

## Migration Best Practices

1. ALWAYS write reversible migrations (up + down)
2. NEVER drop columns in production without a deprecation period
3. Add new columns as NULLABLE, backfill, then add NOT NULL
4. Create indexes CONCURRENTLY in production
5. Test migrations on a copy of production data

## ChromaDB / Vector Store

```python
# For SuperMemory / RAG integration
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(
    name="memories",
    metadata={"hnsw:space": "cosine"},
)
collection.add(
    documents=["fact 1", "fact 2"],
    ids=["id1", "id2"],
    metadatas=[{"source": "user"}, {"source": "system"}],
)
results = collection.query(query_texts=["search query"], n_results=5)
```
