---
name: docs-architect
description: "Technical documentation: architecture diagrams (Mermaid), API docs, runbooks, ADRs, README templates. Use when: writing docs, creating diagrams, structuring documentation, writing ADRs or runbooks."
version: 1.0.0
---

# Documentation Architect

## Purpose

Create and maintain high-quality technical documentation: architecture diagrams, API docs, runbooks, and ADRs.

## Document Types & Templates

### README Template (for any project)

```markdown
# Project Name

One-line description.

## Quick Start

Three or fewer commands to run the project.

## Architecture

Mermaid diagram or brief description.

## Configuration

Table of environment variables / config keys.

## Development

How to build, test, lint.

## Deployment

How to deploy to production.
```

### Architecture Decision Record (ADR)

```markdown
# ADR-NNN: Decision Title

## Status: Proposed | Accepted | Deprecated | Superseded

## Context

What is the issue or need driving this decision?

## Decision

What has been decided?

## Consequences

What are the trade-offs of this decision?
```

### Runbook Template

```markdown
# Runbook: Service Recovery

## Symptoms

- Metric X drops below threshold
- Error rate exceeds N%

## Diagnosis

1. Check logs: `kubectl logs -l app=service`
2. Check metrics: Grafana dashboard URL

## Resolution Steps

1. Step one with exact command
2. Step two with expected output

## Escalation

Contact: @team-lead, #ops-channel
```

## Mermaid Diagrams (ALWAYS use for architecture)

### System Architecture

```mermaid
graph TB
    Client --> Gateway
    Gateway --> Auth[Auth Service]
    Gateway --> API[API Service]
    API --> DB[(PostgreSQL)]
    API --> Cache[(Redis)]
    API --> Queue[Message Queue]
    Queue --> Worker
    Worker --> DB
```

### Sequence Diagram

```mermaid
sequenceDiagram
    participant C as Client
    participant G as Gateway
    participant A as API
    participant D as Database
    C->>G: POST /api/tasks
    G->>A: Forward request
    A->>D: INSERT task
    D-->>A: task_id
    A-->>G: 201 Created
    G-->>C: { id: task_id }
```

### Data Flow

```mermaid
flowchart LR
    Input --> Parser
    Parser --> Validator
    Validator -->|Valid| Processor
    Validator -->|Invalid| ErrorHandler
    Processor --> Output
    ErrorHandler --> Metrics
```

## Writing Rules

1. **Lead with the action**: "Run `pnpm test`" not "You can run tests by..."
2. **Use tables** for configuration, not paragraphs
3. **Use code blocks** for all commands and file paths
4. **Keep paragraphs to 3 sentences max**
5. **Use numbered lists** for steps, bullets for features
6. **Include expected output** for all commands
7. **Date stamp ADRs** and link to related issues
8. **No passive voice**: "The service handles..." not "Requests are handled by..."
