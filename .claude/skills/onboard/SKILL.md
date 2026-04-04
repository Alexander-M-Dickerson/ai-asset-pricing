---
name: onboard
description: "Agent-driven cold-start onboarding. Use the repo shell entrypoint to find or install Python 3.11+, then run the shared bootstrap audit/plan/apply flow and configure WRDS only if the user has it."
argument-hint: "[wrds-username (optional)]"
---

# User Onboarding

Use the shared repo-local onboarding flow:

1. `tools/onboard.ps1` or `tools/onboard.sh` for the pre-Python cold-start step
2. `tools/onboard_driver.py` for agent orchestration once Python exists
3. `tools/bootstrap.py` as the shared Python-level audit/plan/apply engine

Do not duplicate bootstrap logic here when the repo scripts already handle it.

## Hard Rules

- Print `Scanning your environment...` before discovery.
- Print `Testing WRDS connectivity...` before live `psql` checks.
- Never assume bare `python` or bare `pip` are valid on Windows.
- Prefer `uv pip install --python "<PYTHON>"` when uv is available; fall back to `"<PYTHON>" -m pip install`.
- Prefer `tools/bootstrap.py audit`, the emitted `bootstrap_plan`, and `tools/bootstrap.py apply` over ad hoc local-file generation.
- Treat canonical local state as external to the repo. Repo-root `LOCAL_ENV.md`, `CLAUDE.local.md`, and `.claude/settings.local.json` are compatibility shims only.
- Let `tools/bootstrap.py apply` manage canonical local state. Use `--write-compat-shims` only for private single-user backward compatibility.
- If an install path needs admin privileges or a missing package manager, stop and give exact instructions.
- If a bootstrap-plan command needs approval, request it and continue with that exact command.
- Ask once whether the user has a WRDS account and wants it configured now. If the answer is no, skip WRDS setup and still treat onboarding as complete once the base repo is ready.
- Treat SSH key setup as optional for basic PostgreSQL access.
- Never use `conda install` for system tools (psql, pdflatex, R, git). Use the OS package manager (winget/brew/apt). Conda is for Python packages only.

## Workflow

### 1. Start With The Shell Entry Point

Use the repo-local shell entrypoint, not `tools/bootstrap.py` directly, when the
machine may not have Python yet.

```powershell
powershell -ExecutionPolicy Bypass -File tools/onboard.ps1
```

```bash
bash tools/onboard.sh
```

Those entrypoints should:

- find a usable Python 3.11+ interpreter
- install Miniforge automatically when no acceptable Python exists and a
  supported installer path is available
- hand off to `tools/onboard_driver.py`

If the package manager or installer path is unavailable, stop and give the
exact manual Miniforge command for the current platform.

### 2. Resolve WRDS Scope Once

If the user already answered in chat, pass that through to the driver. If not,
ask once:

- `Do you have a WRDS account and want it configured now?`

Outcomes:

- `yes`: collect username when needed, create WRDS files, and run live WRDS checks
- `no`: skip WRDS setup entirely
- later / declined: also skip WRDS setup entirely

WRDS is optional. Lack of a WRDS account must not make onboarding fail.

### 3. Audit With The Shared Engine

Once Python exists, run the shared audit:

```bash
"<PYTHON>" tools/bootstrap.py audit --json --wrds yes|no
```

Read the audit output and summarize the gaps before changing anything.

### 4. Execute The Bootstrap Plan

Read `bootstrap_plan.steps` from the audit payload and execute each step with
`auto_run=true` for the current shell in order.

The plan is the source of truth for:

- blocking base-repo setup
- optional WRDS setup
- optional writing and R setup
- `tools/bootstrap.py apply`
- the final rerun of `tools/bootstrap.py audit`

If direct command execution is not available because you are running in a plain
local terminal without agent approvals, you may use the best-effort convenience
fallback:

```bash
"<PYTHON>" tools/bootstrap.py repair --write-canonical-state --wrds yes|no
```

### 5. Manual Gaps The Shared Engine Cannot Finish Alone

If the bootstrap plan or fallback repair step cannot install Python packages automatically:

```bash
# With uv (preferred):
uv pip install --no-compile --python "<PYTHON>" pandas psycopg2-binary pyarrow numpy matplotlib statsmodels
# Without uv:
"<PYTHON>" -m pip install --no-compile pandas psycopg2-binary pyarrow numpy matplotlib statsmodels
```

If the bootstrap plan or fallback repair step cannot reinstall repo packages automatically:

```bash
# With uv (preferred):
uv pip install --no-compile --python "<PYTHON>" -e .
cd packages/PyBondLab && uv pip install --no-compile --python "<PYTHON>" -e ".[performance]"
# Without uv:
"<PYTHON>" -m pip install --no-compile -e .
cd packages/PyBondLab && "<PYTHON>" -m pip install --no-compile -e ".[performance]"
```

If `psql` is missing and the user said `no` to WRDS, onboarding can still be
complete. `psql` is only needed for WRDS data extraction.

If the user wants WRDS access later, recommend:

- **Windows**: Download the PostgreSQL zip archive from postgresql.org and extract to `~/tools/pgsql/` (the probe already checks this path).
- **macOS**: `brew install libpq`
- **Linux**: `apt install postgresql-client` or `dnf install postgresql`

Then rerun:

```bash
"<PYTHON>" tools/bootstrap.py audit --wrds yes
```

> **NEVER use conda to install psql, PostgreSQL, LaTeX, or other system tools.**
> Conda's dependency solver hangs on these packages and can corrupt the Python
> environment. Conda is for Python packages only.

If WRDS is enabled and files are missing, create or repair:

1. `~/.pg_service.conf`
2. `~/.pgpass`
3. `~/.ssh/config` entry for `Host wrds` if SSH or TAQ workflows are needed

Use the username from `$ARGUMENTS` if provided, otherwise ask once. If
`~/.pgpass` is missing, ask for the WRDS password and do not echo it back.
Prefer the shared helper:

```bash
AI_ASSET_PRICING_WRDS_PASSWORD="<SECRET>" "<PYTHON>" tools/bootstrap.py wrds-files --username THEIR_USERNAME
```

> **DUO 2FA:** The first `psql service=wrds` connection from a new IP triggers
> a DUO push notification. Tell the user to check their phone and approve it.
> The connection will time out if not approved.

When testing WRDS connectivity, use a date range guaranteed to have data (for
example 2022). Do not use the current year. A query returning 0 rows is not a
valid connectivity confirmation.

Example:

```bash
psql service=wrds -c "SELECT COUNT(*) FROM crsp.dsi WHERE date >= '2022-01-01' AND date < '2023-01-01';"
```

Expected result: about 251 rows.

### 6. Refresh Local Files Only

If you only need to refresh canonical local state after environment changes, run:

```bash
"<PYTHON>" tools/bootstrap.py apply
```

This writes or refreshes canonical external files:

- `local_env.md`
- `claude.local.md`
- `settings.local.json`

### 7. Final Summary

End with a short status table covering:

- base repo
- WRDS
- writing
- R
- Python
- repo packages

If WRDS shows as skipped because the user has no account, say clearly that
onboarding is still complete once the base repo is ready.

Then list the files written and any remaining manual steps.

### Post-Onboard Note

Tools like `psql` may not be on the shell `PATH` even when installed. After
onboarding, always use the absolute paths recorded in canonical local state
(or a repo-root compatibility shim if one was explicitly generated) rather
than bare command names. The bootstrap engine discovers these paths
automatically and writes them to the local files.
