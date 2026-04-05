---
name: typescript-modern
description: "TypeScript 5.4-5.8 expert: strict typing, ESM patterns, Node 22+, Bun compatibility, build tooling. Use when: writing/reviewing TypeScript, configuring tsconfig, designing type-safe APIs, ESM module patterns."
version: 1.0.0
---

# Modern TypeScript (5.4–5.8)

## Purpose

Expert TypeScript development with modern features, strict typing, and ESM-first patterns.

## TypeScript 5.4–5.8 Features (MUST apply)

### 5.4: NoInfer utility type

```typescript
function createSignal<T>(value: T, compare: (a: NoInfer<T>, b: NoInfer<T>) => boolean) { ... }
```

### 5.5: Inferred Type Predicates

```typescript
// TS now infers this as a type guard automatically
const isString = (x: unknown) => typeof x === "string";
// Use: arr.filter(isString) — result is string[]
```

### 5.6: Iterator Helpers & Disallowed Nullish Coalescing

```typescript
const evens = Iterator.from([1, 2, 3, 4]).filter((n) => n % 2 === 0);
```

### 5.7: `--rewriteRelativeImportExtensions`

```json
{ "compilerOptions": { "rewriteRelativeImportExtensions": true } }
```

### 5.8: `--erasableSyntaxOnly` & `require()` of ESM

```json
{ "compilerOptions": { "erasableSyntaxOnly": true } }
```

## ESM Patterns (REQUIRED)

```typescript
// Always use .js extension in imports (ESM)
import { helper } from "./utils.js";
import type { Config } from "./types.js";

// Use import type for type-only imports
import type { Request, Response } from "express";

// Use import attributes (ES2025)
import data from "./config.json" with { type: "json" };
```

## Strict Typing Rules

1. **NEVER use `any`** — use `unknown` and narrow, or `object`
2. **NEVER use `@ts-nocheck`** — fix root causes
3. **ALWAYS use `satisfies`** for type validation without widening:

```typescript
const config = { port: 3000, host: "localhost" } satisfies ServerConfig;
```

4. **Use `const` assertions** for literal types:

```typescript
const ROUTES = ["home", "about", "contact"] as const;
type Route = (typeof ROUTES)[number]; // "home" | "about" | "contact"
```

5. **Use discriminated unions** over optional properties:

```typescript
type Result<T> = { ok: true; value: T } | { ok: false; error: Error };
```

## Node 22+ / Bun Compatibility

- Use `node:` prefix for built-in modules: `import { readFile } from "node:fs/promises"`
- Use `structuredClone()` for deep copy
- Use `using` keyword for explicit resource management (TC39 Stage 3)
- Prefer `fetch()` (global) over `node-fetch`
- Use `crypto.randomUUID()` for UUIDs

## Build Configuration

```json
{
  "compilerOptions": {
    "target": "ES2024",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "isolatedDeclarations": true,
    "erasableSyntaxOnly": true,
    "skipLibCheck": true
  }
}
```
