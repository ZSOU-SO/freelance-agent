# Freelance Agent Stable Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare the completed phase-one MVP for a safe, reproducible first stable Git commit without configuring credentials or starting phase-two development.

**Architecture:** Keep application behavior unchanged. Harden repository exclusions, turn the root README into the single operational guide, verify both application stacks, and create one intentionally scoped release commit. If no GitHub remote exists, stop before network operations and provide manual repository setup commands.

**Tech Stack:** Git, Markdown, Python 3.11+, pytest, Node.js 20+, Vue 3, Vitest, Vite

## Global Constraints

- Do not configure or disclose a real `OPENAI_API_KEY`.
- Do not start phase-two development.
- Do not create or push to a GitHub repository when no remote is configured.
- Use commit message `feat: complete freelance analysis agent MVP`.
- Keep `.env.example` files tracked with empty or non-secret values.

---

### Task 1: Repository safety audit

**Files:**
- Inspect: `.gitignore`
- Inspect: `.env.example`
- Inspect: `frontend/.env.example`
- Inspect: tracked files and Git remote configuration

- [ ] Check the current branch, working tree, tracked files, commit history, and remotes.
- [ ] Search tracked and untracked source files for secret-shaped OpenAI API keys without printing secret values.
- [ ] Confirm that only safe environment-variable examples are tracked.

### Task 2: Release documentation and exclusions

**Files:**
- Modify: `.gitignore`
- Modify: `README.md`

- [ ] Add exclusions for environment overrides, SQLite files, Python caches/builds, Node dependencies/builds, coverage, and local editor files.
- [ ] Preserve explicit exceptions for the two safe `.env.example` templates.
- [ ] Document the project, features, pipeline, fallback semantics, stack, directory layout, setup, variables, tests, example request/response, security notes, limitations, and future roadmap.
- [ ] Ensure every credential shown in documentation is empty or clearly fake.

### Task 3: Verification and stable commit

**Files:**
- Verify: all intended release files

- [ ] Review `git diff --check`, the complete diff, ignored-file behavior, and secret scan results.
- [ ] Run `OPENAI_API_KEY='' .venv/Scripts/python.exe -m pytest backend/tests -ra` (PowerShell equivalent on Windows); expect all backend tests to pass without an API call.
- [ ] Run `npm.cmd --prefix frontend test -- --run`; expect all frontend tests to pass.
- [ ] Run `npm.cmd --prefix frontend run build`; expect type checking and the production build to succeed.
- [ ] Stage only `.gitignore`, `README.md`, and this plan, then commit with `feat: complete freelance analysis agent MVP`.
- [ ] Confirm the final branch, commit, clean working tree, and remote state. Do not push when no remote exists.
