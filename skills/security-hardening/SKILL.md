---
name: security-hardening
description: "Security best practices: OWASP Top 10, supply chain, secrets management, input validation, dependency audit. Use when: reviewing security, handling credentials, validating input, auditing dependencies."
version: 1.0.0
---

# Security Hardening

## Purpose

Apply security best practices across the codebase: OWASP Top 10, secrets management, supply chain, input validation.

## OWASP Top 10 Checklist

### A01: Broken Access Control

- Deny by default, allow explicitly
- Validate ownership on every resource access
- Rate-limit sensitive endpoints

### A02: Cryptographic Failures

- NEVER hardcode secrets — use environment variables or vault
- Use `crypto.randomBytes(32)` for tokens, not `Math.random()`
- Always use HTTPS/TLS for external calls

### A03: Injection

```python
# SQL — ALWAYS parameterize
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
# NEVER: cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

# Command — NEVER use shell=True with user input
subprocess.run(["ls", "-la", safe_path], shell=False)
```

### A04: Insecure Design

- Validate all input at system boundaries
- Use allowlists over denylists
- Implement rate limiting on all public endpoints

### A05: Security Misconfiguration

- Remove default credentials
- Disable unnecessary features/ports
- Set secure headers: CSP, HSTS, X-Frame-Options

## Secrets Management

```bash
# CORRECT: Environment variable
export OPENROUTER_API_KEY="sk-or-v1-..."

# CORRECT: .env file (NEVER commit)
echo ".env" >> .gitignore

# WRONG: Hardcoded in source
API_KEY = "sk-or-v1-..."  # NEVER DO THIS
```

### Pre-commit Secret Scan

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
```

## Input Validation

```python
from pydantic import BaseModel, Field, validator

class TaskInput(BaseModel):
    task_id: str = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    priority: int = Field(..., ge=1, le=10)
    content: str = Field(..., max_length=10000)

    @validator("content")
    def no_injection(cls, v):
        dangerous = ["<script", "javascript:", "data:text/html"]
        if any(d in v.lower() for d in dangerous):
            raise ValueError("Potentially unsafe content")
        return v
```

## Dependency Audit

```bash
# NPM/pnpm
pnpm audit
pnpm audit --fix

# Python
pip-audit
safety check -r requirements.txt

# Rust
cargo audit
```

## API Security

1. **Always validate JWT** before processing
2. **Use short-lived tokens** (15 min access, 7 day refresh)
3. **Implement CORS properly** — no wildcards in production
4. **Log all auth failures** with source IP and timestamp
5. **Rate limit by IP and by user** — compound limiting
