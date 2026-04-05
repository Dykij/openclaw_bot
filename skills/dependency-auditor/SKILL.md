---
name: dependency-auditor
description: "Audit and manage dependencies: security vulnerabilities, license compliance, version pinning, update strategy. Use when: auditing deps, fixing CVEs, updating packages, checking licenses."
version: 1.0.0
---

# Dependency Auditor

## Purpose

Audit dependencies for security, license compliance, and version health.

## Audit Commands

### Python

```bash
# Security audit
pip-audit
pip-audit -r requirements.txt
safety check -r requirements.txt

# Outdated packages
pip list --outdated --format=columns

# License check
pip-licenses --format=markdown
```

### Node.js / pnpm

```bash
# Security audit
pnpm audit
pnpm audit --fix  # Auto-fix if safe

# Outdated
pnpm outdated

# License check
npx license-checker --summary
```

### Rust

```bash
cargo audit
cargo outdated
cargo deny check licenses
```

## Version Pinning Strategy

| Environment       | Strategy                  | Example               |
| ----------------- | ------------------------- | --------------------- |
| Apps (production) | Exact pins + lockfile     | `"express": "4.18.2"` |
| Libraries         | Semver ranges             | `"lodash": "^4.17.0"` |
| Python apps       | Exact in requirements.txt | `httpx==0.27.0`       |
| Dev tools         | Latest minor              | `"vitest": "^2.0.0"`  |

## Update Workflow

1. Run `pnpm outdated` / `pip list --outdated`
2. Group updates: security fixes first, then minor, then major
3. Update one group at a time
4. Run full test suite after each group
5. Check changelog for breaking changes on major bumps

## Security Rules

- Run `pnpm audit` / `pip-audit` in CI — fail on high/critical
- Pin all production dependencies to exact versions
- Review new dependencies before adding (check download stats, last update, maintainers)
- Never use dependencies with known CVEs in production
