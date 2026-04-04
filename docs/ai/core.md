# Shared AI Context Core

This repository supports empirical asset pricing workflows across WRDS data
extraction, PyBondLab factor construction, and academic writing.

## Operating Model

- Shared repo-wide AI guidance lives in `docs/ai/`.
- Claude Code uses `CLAUDE.md` and `.claude/`, but they should point back to this shared layer for repo-wide rules.
- Codex uses `AGENTS.md` plus these shared docs.
- Gemini CLI uses `GEMINI.md` (which imports `AGENTS.md`) plus these shared docs. Skills and agents in `.claude/` are plain markdown and can be read directly by any tool.

## Local State

Canonical local state is machine-local and should live outside the repo:

- `local_env.md` - canonical external local environment note for both Codex and Claude
- `claude.local.md` - canonical external Claude compatibility mirror
- `settings.local.json` - canonical external Claude-only local permissions

These repo-root files are optional compatibility shims and must never be committed:

- `LOCAL_ENV.md`
- `CLAUDE.local.md`
- `.claude/settings.local.json`

## Project Structure

- `fintools/` - shared Python utilities used across research code
- `packages/PyBondLab/` - portfolio construction package
- `data/` - extracted datasets, always local/output state
- `boilerplate/` - shared LaTeX paper template and starter bibliography for new papers
- `projects/<name>/guidance/` - per-project paper context and writing guidance, including `paper-context.md`
- `.claude/` - CLI adapters, rules, agents, and skills (Claude-native; readable by any tool as plain markdown)
- `.claude/hooks/` - Claude Code-only automation hooks such as LaTeX rebuild and pre-commit preflight
- `.claude/hooks/common.sh` - shared Bash helper for hook-local tool resolution and canonical state-dir lookup
- `tools/` - probe and release-preflight utilities

Research projects should live under `projects/<name>/` with production code,
tests/investigations, results, and writing artifacts separated cleanly.

## Project Context Folder

Projects may include `projects/<name>/context/` for operational learnings
that persist across sessions (data pull gotchas, session notes, what broke).
This is distinct from `guidance/` (paper context, literature) and
`.claude/rules/` (repo-wide conventions). Read `context/session_learnings.md`
at the start of every session if it exists.

## Parallel Bash Behavior

When Claude Code runs multiple Bash calls in parallel, if one call fails,
all remaining parallel calls in the same batch are automatically cancelled.
Their output is lost. Never run exploratory or untested queries in parallel —
only parallelize operations known to succeed.

## Shared Conventions

- Prefer Parquet plus `metadata.json` for extracted datasets.
- Use short lowercase data folder names such as `crsp_monthly_sp500`.
- Keep data global and project code local; do not copy datasets into project folders.
- Use `tools/release_preflight.py --strict` before publishing shared changes.
- Strict preflight auto-cleans repo temp artifacts and tolerates gitignored repo-root local artifacts such as `.venv/`, `venv/`, and `.Rhistory`, but it still fails on repo-root compatibility shims.
- When absolute paths matter, use the canonical local state reported by `tools/bootstrap.py audit`.
- Run `tools/context_drift.py` to detect stale documentation after code changes.
- A `SessionStart` hook injects recent activity and drift warnings into every Claude Code session.
- Use `/sync-context` to review and apply targeted documentation updates.
