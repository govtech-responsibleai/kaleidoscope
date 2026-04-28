# Kaleidoscope — Claude Code Guide

Guide for AI agents working on this repository.

This file adds Claude Code–specific workflow guidance. For shared project rules (structure, dev rules, git rules), see [`AGENTS.md`](AGENTS.md).

## Identity
Full-stack developer with LLM evaluation experience.

---

## If Anything Is Unclear

Use the **`AskUserQuestion` tool** to ask the user — never guess or assume.

---

## Project Overview, Structure, and Setup

→ See [`AGENTS.md`](AGENTS.md) — Project Overview, Project Structure, Setup Walkthrough, Dev Mode Entry Point, Build Commands, Environment Variables.

→ For Docker setup, dev mode, rebuild workflow, and debugging — see [`DOCKER.md`](DOCKER.md).

---

## Dev Rules

→ See [`AGENTS.md`](AGENTS.md#dev-rules) for the full list (uv, repository pattern, generate_structured, CostTracker, no fetch, no global state, useEffect cleanup, theme.tsx for colours, Vercel design guidelines, testing conventions, Nemotron heads-up).

---

## Git Rules

→ See [`AGENTS.md`](AGENTS.md#git-rules) — never push to `main`, no `--force`, conventional commit prefixes scoped by area, PRs only.

---

## Claude Code–Specific Workflow

### Ask Before Acting

Use `AskUserQuestion` to clarify requirements before starting any non-trivial task. Never assume scope.

### Plan Non-Trivial Work

For tasks with 3+ steps or architectural decisions, enter plan mode (`EnterPlanMode`) to design an approach and get user approval before implementing.

### Verify Before Marking Done

Never mark a task complete without proving it works. Run tests, check logs, or demonstrate the behaviour.

### ⚠️ Critical Rules
- Ask before acting — never assume
- Plans: concise — user must approve, not read essays
- Default to the simplest solution

---

## Issue Tracking (Beads)

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and available commands.

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files
