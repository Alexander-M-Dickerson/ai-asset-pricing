# Shared AI Context Core

This repository supports empirical asset pricing workflows across WRDS data
extraction, PyBondLab factor construction, and academic writing.

## Operating Model

- Shared repo-wide AI guidance lives in `docs/ai/`.
- Claude Code uses `CLAUDE.md` and `.claude/`, but they should point back to this shared layer for repo-wide rules.
- Codex uses `AGENTS.md` plus these shared docs.

## Local State

These files are machine-local and must never be committed:

- `LOCAL_ENV.md` - canonical local environment note for both Codex and Claude
- `CLAUDE.local.md` - Claude compatibility mirror
- `.claude/settings.local.json` - Claude-only local permissions

## Project Structure

- `fintools/` - shared Python utilities used across research code
- `packages/PyBondLab/` - portfolio construction package
- `data/` - extracted datasets, always local/output state
- `boilerplate/` - shared LaTeX paper template and starter bibliography for new papers
- `projects/<name>/guidance/` - per-project paper context and writing guidance, including `paper-context.md`
- `.claude/` - Claude-specific adapters, rules, agents, and skills
- `.claude/hooks/` - Claude Code-only automation hooks such as LaTeX rebuild and pre-commit preflight
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
- When absolute paths matter, use the paths recorded in `LOCAL_ENV.md`.
