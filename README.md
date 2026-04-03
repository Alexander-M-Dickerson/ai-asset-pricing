[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

# ai-asset-pricing

`ai-asset-pricing` is an AI-assisted empirical asset pricing research repo for
WRDS data work, factor-model workflows, PyBondLab package use, automation of
repeated research tasks, and LaTeX paper writing.

The main promise is simple: clone the repo, ask your agent to onboard the repo,
and get to a research-ready workflow without hand-editing machine-specific
config inside the shared tree.

## Clone to Research-Ready

### Claude Code users

Ask Claude Code to onboard the repo. The standard Claude entry point is
`/onboard`.

Under the hood, `/onboard` is a thin wrapper over the shared
`tools/bootstrap.py` engine:

1. `tools/bootstrap.py audit`
2. execute the emitted `bootstrap_plan`
3. `tools/bootstrap.py apply`
4. rerun `tools/bootstrap.py audit`

### Codex and Gemini CLI users

Ask Codex or Gemini CLI in chat to onboard or set up the repo. They should run
the same shared flow for you, but without the Claude slash command wrapper:

1. `tools/bootstrap.py audit`
2. execute the required commands from `bootstrap_plan`
3. run `tools/bootstrap.py apply`
4. rerun `tools/bootstrap.py audit`

Codex starts from `AGENTS.md`. Gemini CLI uses `GEMINI.md`, which imports the
same shared routing layer.

## What It Covers

- WRDS-oriented data extraction and query workflows
- factor-model research setup and reusable automation
- `fintools/` shared utilities
- `packages/PyBondLab/` package install, testing, and research workflows
- LaTeX paper scaffolding, drafting, auditing, and compilation
- shared repo context for Claude Code, Codex, and Gemini CLI

## Repo Layout

```text
AGENTS.md                              # Codex routing and repo rules
CLAUDE.md                              # Claude adapter and commands
GEMINI.md                              # Gemini adapter
.claude/                               # Claude-native rules, skills, agents, hooks
docs/ai/                               # Shared cross-tool context
tools/bootstrap.py                     # Shared onboarding audit/apply engine
tools/onboard_probe.py                 # Shared environment probe implementation
tools/onboarding_smoke_test.py         # Temp-clone onboarding smoke test
tools/context_drift.py                 # Documentation drift detector
tools/release_preflight.py             # Release/readiness checker
fintools/                              # Shared Python utilities
packages/PyBondLab/                    # Portfolio construction package
```

## Prerequisites

- Claude Code, Codex, or Gemini CLI
- Bash on `PATH` for Claude hook automation and Bash bootstrap commands
- Windows Claude users should install Git for Windows / Git Bash and ensure
  `bash` is on `PATH`
- internet access for first-run package installation
- a WRDS account if you need live data access

## Local State and Synced Folders

The canonical local state lives **outside the repo** in a per-user OS-specific
directory reported by `tools/bootstrap.py audit`.

That canonical local state includes tool paths and compatibility files such as:

- `local_env.md`
- `claude.local.md`
- `settings.local.json`

Repo-root compatibility shims may still be generated when explicitly requested:

- `LOCAL_ENV.md`
- `CLAUDE.local.md`
- `.claude/settings.local.json`

Those shims are legacy compatibility files only. In shared Dropbox/OneDrive
working trees, the canonical local state should stay external so machine-local
paths do not sync across users.

## Manual WRDS Files

If onboarding has not created them yet, you still need:

1. `~/.pg_service.conf`
2. `~/.pgpass`
3. `~/.ssh/config` entry for `Host wrds` if you need SSH/TAQ workflows

Minimal `~/.pg_service.conf`:

```ini
[wrds]
host=wrds-pgdata.wharton.upenn.edu
port=9737
dbname=wrds
user=YOUR_WRDS_USERNAME
```

Minimal `~/.pgpass`:

```text
wrds-pgdata.wharton.upenn.edu:9737:wrds:YOUR_WRDS_USERNAME:YOUR_PASSWORD
```

Then set restrictive permissions:

```bash
chmod 600 ~/.pgpass
```

## Without WRDS

The repo is still useful without live WRDS access:

- AI skills, rules, and agents for writing, auditing, and project scaffolding
- `fintools` package work
- `PyBondLab` install/import and bundled-data smoke coverage
- LaTeX boilerplate and paper setup
- local onboarding and release/readiness checks

WRDS is only required for live data extraction, WRDS connectivity checks, and
running research workflows on real WRDS-backed data.

## Tool Entry Points

- Codex: `AGENTS.md`
- Claude Code: `CLAUDE.md`
- Gemini CLI: `GEMINI.md`
- onboarding: `docs/ai/onboarding.md`
- WRDS workflow: `docs/ai/wrds.md`
- PyBondLab workflow: `docs/ai/pybondlab.md`
- writing and LaTeX workflow: `docs/ai/writing.md`

The `.claude/agents/*.md`, `.claude/skills/*.md`, and `.claude/rules/*.md`
files are plain markdown and can be reused across tools.

## Maintainer Preflight

Before publishing shared changes, run:

```bash
<python> tools/release_preflight.py --strict
```

Strict preflight auto-cleans repo temp artifacts such as test temp folders and
`__pycache__`, and it tolerates gitignored repo-root virtual environments such
as `.venv/`. It still fails if the release tree contains `.Rhistory` or
repo-root compatibility shims.

## Acknowledgements

- [Piotr Orlowski](https://github.com/piotrek-orlowski) and the
  [`claude-wrds-public`](https://github.com/piotrek-orlowski/claude-wrds-public/tree/main/agents)
  agent set, which provided the starting point for some WRDS-oriented agent
  materials used here and then heavily augmented for this repo.
- [Scott Cunningham's `MixtapeTools`](https://github.com/scunning1975/MixtapeTools),
  which provided some base rules and skills that were also heavily augmented for
  this workflow.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for
details.
