# Agent Persona System

The OpenClaw bot includes a curated **agent persona system** that lets you switch the bot between specialised expert roles. Instead of a generic assistant, you get a focused specialist with its own process, artifacts, and quality metrics.

## How it works

Personas are plain Markdown files with YAML frontmatter stored in the `agents/` directory at the repository root. When a persona is activated for a chat, the bot prepends the persona's role definition, process, and constraints to every prompt sent to the LLM — augmenting (not replacing) the base system prompt.

The system is **fully additive**: if no persona is activated, the bot behaves exactly as before.

## Telegram commands

| Command | Description |
|---|---|
| `/agents` | List all available agent personas |
| `/agent <slug>` | Activate a persona (e.g. `/agent code-reviewer`) |
| `/agent info <slug>` | Show detailed info about a persona |
| `/agent reset` | Deactivate the current persona and return to default mode |

## Available personas

### 🔧 Engineering

| Slug | Name | Description |
|---|---|---|
| `ai-engineer` | AI Engineer | AI/ML task specialist: model selection, vLLM tuning, fine-tuning pipelines |
| `code-reviewer` | Code Reviewer | Code review with severity labels (Critical/Warning/Suggestion) |
| `backend-architect` | Backend Architect | System design, API contracts, database modeling, distributed systems |
| `devops-automator` | DevOps Automator | CI/CD pipelines, Docker, Kubernetes, infrastructure automation |
| `security-engineer` | Security Engineer | Threat modeling, vulnerability assessment, OWASP audits |
| `senior-developer` | Senior Developer | General-purpose coding, refactoring, clean code, mentoring |

### 🎨 Design

| Slug | Name | Description |
|---|---|---|
| `ux-architect` | UX Architect | User research, information architecture, wireframes, usability |
| `ui-designer` | UI Designer | Visual design, design systems, CSS/Tailwind specs, component states |
| `image-prompt-engineer` | Image Prompt Engineer | AI image generation prompts (Stable Diffusion, Midjourney, DALL-E, Flux) |

### 📦 Product

| Slug | Name | Description |
|---|---|---|
| `product-manager` | Product Manager | PRDs, user stories, prioritization, roadmaps, go-to-market |
| `product-strategist` | Product Strategist | Market analysis, competitive positioning, OKRs, business model |

### 🧪 Testing

| Slug | Name | Description |
|---|---|---|
| `qa-specialist` | QA Specialist | Test plans, test case design, automation strategy, bug reports |

### 📣 Marketing

| Slug | Name | Description |
|---|---|---|
| `seo-specialist` | SEO Specialist | Keyword research, content briefs, technical SEO, ranking strategy |
| `content-strategist` | Content Strategist | Editorial planning, brand voice, multi-channel content creation |

### 🎧 Support

| Slug | Name | Description |
|---|---|---|
| `technical-support` | Technical Support | Issue triage, troubleshooting runbooks, escalation management |

### 📋 Project Management

| Slug | Name | Description |
|---|---|---|
| `project-manager` | Project Manager | Sprint planning, RAID log, stakeholder communication, delivery tracking |

## Auto-routing

The system includes a keyword-based router that can suggest the best persona for a given message. This is used internally and can be extended.

Examples:
- "review this code" → `code-reviewer`
- "write tests for this module" → `qa-specialist`
- "set up a docker pipeline" → `devops-automator`
- "проверь код" → `code-reviewer` (Russian keywords supported)

## Adding custom personas

1. Create a Markdown file anywhere under `agents/` (subdirectory recommended for organisation)
2. Add YAML frontmatter with required fields:

```markdown
---
name: "My Custom Agent"
division: "engineering"
tags: ["tag1", "tag2"]
description: "Brief description of what this agent specialises in."
---

# My Custom Agent

## Role
Describe the agent's expertise and perspective.

## Process
1. Step one
2. Step two
...

## Artifacts
- Deliverable one
- Deliverable two

## Metrics
- Success metric one
- Success metric two
```

3. Restart the bot — the new persona will be discovered automatically.

The `slug` is derived from the `name` field: lowercase, spaces replaced with hyphens, special characters removed. For `"My Custom Agent"` the slug is `my-custom-agent`.

## Architecture

| Module | Purpose |
|---|---|
| `src/agent_personas.py` | Core module: loader, registry, router, prompt builder, manager |
| `agents/` | Persona Markdown files (organised by division) |
| `src/gateway_commands.py` | Telegram command handlers (`cmd_agents`, `cmd_agent`) |
| `src/main.py` | Command registration + persona augmentation in `_handle_prompt_inner` |
| `tests/test_agent_personas.py` | Unit and integration tests |

## Design principles

- **Non-breaking** — the bot works exactly as before if no persona is active
- **Plugin-friendly** — drop a `.md` file into `agents/` to add a custom role
- **Lightweight** — no new heavy dependencies; uses existing vLLM infrastructure
- **Language-agnostic personas** — Markdown files work with any LLM backend
