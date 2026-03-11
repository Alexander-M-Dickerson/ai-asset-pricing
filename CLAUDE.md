## Project Scope

This is a broad empirical asset pricing research environment. Work may include
WRDS extraction, factor construction, PyBondLab package development, event
studies, regressions, and academic writing.

For repo-wide rules shared with Codex, treat `docs/ai/` as the source of truth.
This file is the Claude adapter, not the canonical home for cross-tool policy.

## Local Environment

`LOCAL_ENV.md` is the canonical machine-local environment note. Claude may also
maintain `CLAUDE.local.md` as a compatibility mirror.

When running Python, `psql`, LaTeX, R, or other tools, check `LOCAL_ENV.md`
for the correct paths on this machine.

Never commit:

- `LOCAL_ENV.md`
- `CLAUDE.local.md`
- `.claude/settings.local.json`

New users should run `/onboard`, which wraps the shared `tools/bootstrap.py`
flow to discover the environment, execute the required bootstrap-plan commands,
and create the local files Claude needs.

## Shared Python Package

Reusable Python code lives in `fintools/` at the project root.

Install once with the interpreter from `LOCAL_ENV.md`:

```bash
<python-from-LOCAL_ENV.md> -m pip install --no-compile -e .
```

Import in scripts with `from fintools import ...`.

## PyBondLab

PyBondLab lives in `packages/PyBondLab/`.

Install once with the interpreter from `LOCAL_ENV.md`:

```bash
cd packages/PyBondLab && <python-from-LOCAL_ENV.md> -m pip install --no-compile -e ".[performance]"
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
- `/write-section`
- `/style-check`
- `/proofread`
- `/build-paper`
- `/build-deck`
- `/respond-to-referee`
- `/latex-doctor`
- `/submission-prep`

### Project Management

- `/new-project` - creates project scaffold, then offers to run `/setup-paper`
- `/create-skill`
- `/rule-create`
- `/create-audit-agent`

## WRDS Rules

- Prefer `psql service=wrds` over SSH whenever PostgreSQL can handle the task.
- Use SSH/SAS only for TAQ or remote file management.
- On Windows, `PGSERVICEFILE` may need to be set explicitly; see `LOCAL_ENV.md`.
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
