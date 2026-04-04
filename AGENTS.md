# Empirical Finance Agent Guide

This repository is designed to work well with Codex, Claude Code, and Gemini CLI.

For Codex, this file is the primary routing layer. For Claude, the `.claude/`
surface remains active, but the shared source of truth for repo-wide behavior
should live in `docs/ai/`. Gemini CLI uses `GEMINI.md` which imports this file.

## Core Contract

- Read `docs/ai/core.md` before making cross-cutting repo decisions.
- When machine-specific paths or tools matter, use the canonical local state reported by `tools/bootstrap.py audit`.
- Treat canonical local state as external to the repo by default.
- Treat repo-root `LOCAL_ENV.md` / `CLAUDE.local.md` as optional compatibility shims, not the source of truth.
- Never commit `LOCAL_ENV.md`, `CLAUDE.local.md`, or `.claude/settings.local.json`.
- Run `tools/release_preflight.py --strict` before a shared release.
- Strict preflight auto-cleans repo temp artifacts and tolerates gitignored repo-root local artifacts such as `.venv/`, `venv/`, and `.Rhistory`, but repo-root compatibility shims still block a release-ready tree.
- Gemini CLI uses `GEMINI.md` which imports this file. See `GEMINI.md` for Gemini-specific notes.

## Task Routing

- Setup, onboarding, tool paths, or first-run issues:
  - Read `docs/ai/onboarding.md`
  - Prefer `tools/onboard.ps1` or `tools/onboard.sh` for true cold-start onboarding
  - Use `tools/onboard_driver.py` after Python exists
  - Use `tools/bootstrap.py audit`
  - Execute the required commands from the audit report's `bootstrap_plan`
  - Use `tools/bootstrap.py apply`
  - Treat `tools/bootstrap.py repair --write-canonical-state` as a direct-terminal fallback, not the primary Codex path
  - Treat `tools/onboard_probe.py` as the shared probe implementation, not the user-facing entry point
  - Ask once whether the user has WRDS and wants it configured now; WRDS is optional and onboarding can still succeed without it
  - Use repo-root compatibility shims only if they were explicitly generated for a private single-user working copy
- WRDS, data extraction, or query pipelines:
  - Read `docs/ai/wrds.md`
  - CRSP v2 is the default for all new work — see `docs/ai/wrds.md` "CRSP Version Policy"
  - Then read the relevant `.claude/agents/*.md` file for deep domain detail
- PyBondLab package work:
  - Read `docs/ai/pybondlab.md`
  - Then read `packages/PyBondLab/AGENTS.md`
- Research ideation, brainstorming, or developing new paper ideas:
  - Read `.claude/skills/idea/SKILL.md`
  - The skill creates lightweight `projects/{mnemonic}_idea/` workspaces with `musings.md` (adversarial dialogue log), `literature.md` (verified references), and `research_plan.md` (evolvable paper skeleton)
  - Conventions for `*_idea/` folders are in `.claude/rules/idea-workspace.md`
  - When an idea graduates to a full project, use `docs/ai/onboarding.md` patterns to create the `projects/{mnemonic}/` scaffold via `/new-project`
  - The `research_plan.md` output is designed to feed into `.claude/skills/build-context/SKILL.md` and `.claude/skills/write-section/SKILL.md` downstream
- Writing, LaTeX, referee responses, or decks:
  - Read `docs/ai/writing.md`
  - For new papers, start from `boilerplate/template_main.tex` and `boilerplate/template_references.bib`
  - Use `.claude/skills/setup-paper/SKILL.md` to scaffold a project's `latex/` folder from that boilerplate
  - For paper-aware editing or audits, check `guidance/paper-context.md` in the active project if it exists, or generate it via `.claude/skills/build-context/SKILL.md`
  - Auditing workflows live in `.claude/skills/audit-section/SKILL.md`, `.claude/skills/full-paper-audit/SKILL.md`, `.claude/skills/check-consistency/SKILL.md`, `.claude/skills/audit-captions/SKILL.md`, `.claude/skills/audit-math/SKILL.md`, and `.claude/skills/outline/SKILL.md`
  - Writing rules include `.claude/rules/academic-writing.md`, `.claude/rules/latex-conventions.md`, `.claude/rules/latex-citations.md`, `.claude/rules/banned-words.md`, `.claude/rules/grammar-punctuation.md`, and `.claude/rules/referee-reply.md`
  - Then read the relevant `.claude/skills/*.md` file for the concrete workflow
- Context maintenance:
  - Run `tools/context_drift.py` to detect stale documentation
  - Use `/sync-context` (Claude Code) to review and apply targeted doc updates
- Editing `.claude/` files:
  - Keep `docs/ai/` authoritative for shared rules
  - Do not duplicate repo-wide guidance if a shared doc already covers it

## Repo Rules

- Use direct PostgreSQL access for WRDS whenever `psql` can handle the task.
- Use SSH/SAS only for TAQ or remote file-management workflows.
- Save extracted data under `data/<source>_<short_description>/` as Parquet plus `metadata.json`.
- In Claude Code sessions, `.claude/hooks/` already handles LaTeX auto-recompile and pre-commit preflight; Codex should stay compatible with those hooks rather than recreate them.
- Keep machine-local state out of the shared tree.
- Shared Dropbox/OneDrive working trees require canonical local state to stay external; do not assume sync tools provide safe concurrent-edit semantics for code.
- Keep project-specific conventions inside each project's own `CLAUDE.md`.
