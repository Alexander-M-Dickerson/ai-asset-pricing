## Project Scope

This is a broad empirical asset pricing research environment. Work may include
WRDS extraction, factor construction, PyBondLab package development, event
studies, regressions, and academic writing.

For repo-wide rules shared with Codex, treat `docs/ai/` as the source of truth.
This file is the Claude adapter, not the canonical home for cross-tool policy.

## Local Environment

Canonical local state lives outside the repo and is reported by
`tools/bootstrap.py audit`. Repo-root `LOCAL_ENV.md` and `CLAUDE.local.md`
are optional compatibility shims only.

When running Python, `psql`, LaTeX, R, or other tools, use the canonical local
state paths reported by `tools/bootstrap.py audit` for this machine.

Never commit:

- `LOCAL_ENV.md`
- `CLAUDE.local.md`
- `.claude/settings.local.json`

New users should run `/onboard`, which wraps the shared `tools/bootstrap.py`
flow to discover the environment, execute the required bootstrap-plan commands,
and create canonical local state outside the repo.

## Shared Python Package

Reusable Python code lives in `fintools/` at the project root.

Install once using the install command from `tools/bootstrap.py audit` (uses `uv`
when available, falls back to `pip`):

```bash
uv pip install --no-compile --python <python> -e .
# or without uv: <python> -m pip install --no-compile -e .
```

Import in scripts with `from fintools import ...`.

## PyBondLab

PyBondLab lives in `packages/PyBondLab/`.

Install once using the install command from `tools/bootstrap.py audit`:

```bash
cd packages/PyBondLab && uv pip install --no-compile --python <python> -e ".[performance]"
# or without uv: <python> -m pip install --no-compile -e ".[performance]"
```

Import with `import PyBondLab as pbl`.

Use `docs/ai/pybondlab.md` plus `packages/PyBondLab/docs/` for package-level
guidance. Use the `.claude/agents/pybondlab-*.md` files for deeper task routing.

## Shared Cross-Tool References

Read these files before broad repo changes:

- `docs/ai/core.md`
- `docs/ai/onboarding.md`
- `docs/ai/wrds.md`
- `docs/ai/pybondlab.md`
- `docs/ai/writing.md`

## Claude Skills and Rules

### Data and WRDS

- `/onboard` - thin wrapper over `tools/bootstrap.py audit`, the emitted bootstrap plan commands, `tools/bootstrap.py apply`, and a final `audit`
- `/wrds-psql` - PostgreSQL query to Parquet plus `metadata.json`
- `/wrds-schema` - preload WRDS schema knowledge
- `/wrds-ssh` - SSH, SAS jobs, and WRDS file transfer

### PyBondLab

- `/run` - fast known PyBondLab workflows
- `bond-data` - WRDS to PyBondLab column mapping and bond-data conventions
- `pybondlab-report` - report generation after PyBondLab runs
- `pybondlab` - PyBondLab API rules and fast-path constraints
- `pybondlab-timing` - output timing convention
- `pybondlab-workflow` - routing between `/run` and orchestration

### Writing and LaTeX

- `/setup-paper` - scaffold a new paper from `boilerplate/template_main.tex` with [REMOVE]-tagged exemplar content
- `/build-context` - generate `guidance/paper-context.md` from user-provided .tex/.md/.pdf files
- `/write-section` - write a new section following academic writing rules
- `/edit-section` - revise an existing section for style, clarity, and correctness
- `/extract-section` - extract a section by key name using `%% BEGIN/END` markers
- `/style-check` - analyze LaTeX text for style violations
- `/proofread` - mechanical error scan (typos, formatting, punctuation)
- `/build-paper` - compile LaTeX to PDF
- `/build-deck` - create Beamer presentations
- `/respond-to-referee` - draft response letters and LaTeX edits for referee points
- `/latex-doctor` - clean and fix .tex files
- `/submission-prep` - pre-submission checklist for target journals

### Auditing

- `/audit-section` - deep audit of a single section (style, facts, citations, flow)
- `/audit-captions` - audit all table/figure captions for consistency
- `/audit-math` - adversarial audit of proofs and formal environments
- `/full-paper-audit` - audit entire paper (cross-section consistency, all citations, all style)
- `/check-consistency` - fast cross-section consistency scan for numbers, terminology, references
- `/outline` - analyze paper structure (section balance, word counts, Cochrane compliance)
- `/compare-versions` - show diff between old and new text with change rationale
- `/verify-citations` - verify citation keys exist in .bib and match claims
- `/research` - search for academic papers using Perplexity MCP
- `/split-pdf` - split a PDF into sections or page ranges

### Project Management

- `/idea` - adversarial research idea generator: literature survey, WRDS feasibility, research plan
- `/new-project` - creates project scaffold, then offers to run `/setup-paper`
- `/sync-context` - detect documentation drift and propose updates to keep context current
- `/create-skill`
- `/rule-create`
- `/create-audit-agent`

## WRDS Rules

- Prefer `psql service=wrds` over SSH whenever PostgreSQL can handle the task.
- Use SSH/SAS only for TAQ or remote file management.
- On Windows, `PGSERVICEFILE` may need to be set explicitly; see the canonical local state from `tools/bootstrap.py audit`.
- Save extracted datasets under `data/` as Parquet plus `metadata.json`.
- Never use the interactive `wrds` Python library in automated workflows.

For deep domain detail, use the specialist references in `.claude/agents/`:

- `crsp-wrds-expert`
- `optionmetrics-wrds-expert`
- `bonds-wrds-expert`
- `taq-wrds-expert`
- `ff-wrds-expert`
- `wrds-query-orchestrator`

## Maintainer Release Check

Before publishing this repo, run:

```bash
<python> tools/release_preflight.py --strict
```

Strict preflight auto-cleans repo temp artifacts and tolerates gitignored
repo-root virtual environments such as `.venv/`, but it still fails on
`.Rhistory` and repo-root compatibility shims.
