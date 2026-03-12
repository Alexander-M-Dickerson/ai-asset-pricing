---
name: onboard
description: "Thin wrapper over tools/bootstrap.py for first-run local setup. Discover Python, run the shared bootstrap audit plan, execute the required setup commands, and refresh machine-local files."
argument-hint: "[wrds-username (optional)]"
---

# User Onboarding

Use the shared repo-local bootstrap engine in `tools/bootstrap.py`. This skill
is only a wrapper around that flow; do not duplicate bootstrap logic here when
the script already handles it.

## Hard Rules

- Print `Scanning your environment...` before discovery.
- Print `Testing WRDS connectivity...` before live `psql` checks.
- Never assume bare `python` or bare `pip` are valid on Windows.
- Use the discovered absolute Python path and `"<python>" -m pip`.
- Prefer `tools/bootstrap.py audit`, the emitted `bootstrap_plan`, and `tools/bootstrap.py apply` over ad hoc local-file generation.
- Treat `LOCAL_ENV.md` as canonical. `CLAUDE.local.md` is a compatibility output.
- Let `tools/bootstrap.py apply` manage `.claude/settings.local.json`; it preserves non-Bash entries and refreshes the Bash allow rules.
- If an install path needs admin privileges or a missing package manager, stop and give exact instructions.
- If a bootstrap-plan command needs approval, request it and continue with that exact command.
- Treat SSH key setup as optional for basic PostgreSQL access.

## Workflow

### 1. Find Python

Find a working interpreter first:

```bash
OS=$(uname -s 2>/dev/null || echo "unknown")

PYTHON=""
if [[ "$OS" == MINGW* || "$OS" == MSYS* ]]; then
  for p in \
    "$HOME/anaconda3/python.exe" \
    "$HOME/miniforge3/python.exe" \
    "$HOME/miniconda3/python.exe" \
    "/c/ProgramData/anaconda3/python.exe" \
    "/c/ProgramData/miniconda3/python.exe"; do
    if [[ -x "$p" ]]; then
      PYTHON="$p"
      break
    fi
  done
fi

if [[ -z "$PYTHON" ]]; then
  for name in python3 python; do
    CAND=$(which "$name" 2>/dev/null)
    if [[ -n "$CAND" ]] && [[ "$CAND" != *"/WindowsApps/"* ]]; then
      "$CAND" --version >/dev/null 2>&1 && { PYTHON="$CAND"; break; }
    fi
  done
fi

echo "PYTHON=$PYTHON"
[[ -n "$PYTHON" ]] && "$PYTHON" --version 2>&1 | head -1 || true
```

If no interpreter is found, recommend Miniforge, stop, and give the exact
install command for the current platform.

### 2. Audit With The Shared Engine

Run:

```bash
"<PYTHON>" tools/bootstrap.py audit
```

Read the audit output and summarize the gaps before changing anything.

### 3. Execute The Bootstrap Plan

After summarizing the audit output, run:

```bash
"<PYTHON>" tools/bootstrap.py audit --json
```

Read `bootstrap_plan.steps` from the audit payload and execute each required
command for the current shell in order.

The plan is the source of truth for:

- missing Python packages
- missing or external repo package installs
- `tools/bootstrap.py apply`
- the final rerun of `tools/bootstrap.py audit`

If direct command execution is not available because you are running in a plain
local terminal without agent approvals, you may use the best-effort convenience
fallback:

```bash
"<PYTHON>" tools/bootstrap.py repair --write-local-files
```

### 4. Manual Gaps The Shared Engine Cannot Finish Alone

If the bootstrap plan or fallback repair step cannot install Python packages automatically:

```bash
"<PYTHON>" -m pip install --no-compile pandas psycopg2-binary pyarrow numpy matplotlib statsmodels
```

If the bootstrap plan or fallback repair step cannot reinstall repo packages automatically:

```bash
"<PYTHON>" -m pip install --no-compile -e .
cd packages/PyBondLab && "<PYTHON>" -m pip install --no-compile -e ".[performance]"
```

If `psql` is missing, install the PostgreSQL client with the platform-appropriate
package manager, then rerun:

```bash
"<PYTHON>" tools/bootstrap.py audit
```

If WRDS files are missing, create or repair:

1. `~/.pg_service.conf`
2. `~/.pgpass`
3. `~/.ssh/config` entry for `Host wrds` if SSH or TAQ workflows are needed

Use the username from `$ARGUMENTS` if provided, otherwise ask once. If
`~/.pgpass` is missing, ask for the WRDS password and do not echo it back.

> **DUO 2FA:** The first `psql service=wrds` connection from a new IP triggers
> a DUO push notification. **Tell the user to check their phone** and approve it.
> The connection will time out (~60s) if not approved. This is the #1 cause of
> "connection timed out" on first setup.

When testing WRDS connectivity, use a date range guaranteed to have data (e.g., 2022).
Do NOT use the current year — WRDS data loading can lag by months. A query returning
0 rows is NOT a valid connectivity confirmation.

Example: `psql service=wrds -c "SELECT COUNT(*) FROM crsp.dsi WHERE date >= '2022-01-01' AND date < '2023-01-01';"`
Expected: ~251 rows (trading days in 2022).

`~/.pg_service.conf`

```ini
[wrds]
host=wrds-pgdata.wharton.upenn.edu
port=9737
dbname=wrds
user=THEIR_USERNAME
```

`~/.pgpass`

```text
wrds-pgdata.wharton.upenn.edu:9737:wrds:THEIR_USERNAME:THEIR_PASSWORD
```

Then:

```bash
chmod 600 ~/.pgpass
```

On Windows, also copy both files to `$APPDATA/postgresql/` if libpq on that
machine expects them there.

### 5. Refresh Local Files Only

If you only need to refresh `LOCAL_ENV.md`, `CLAUDE.local.md`, or
`.claude/settings.local.json` after environment changes, run:

```bash
"<PYTHON>" tools/bootstrap.py apply
```

This writes or refreshes:

- `LOCAL_ENV.md`
- `CLAUDE.local.md`
- `.claude/settings.local.json`

### 6. Final Summary

End with a short status table covering:

- Python
- Repo packages
- `psql`
- WRDS connection
- LaTeX
- R
- SSH key

Then list the files written and any remaining manual steps.

### Post-Onboard Note

Tools like `psql` may not be on the shell `PATH` even when installed. After
onboarding, always use the absolute paths recorded in `LOCAL_ENV.md` (or
`CLAUDE.local.md`) rather than bare command names. The bootstrap engine
discovers these paths automatically and writes them to the local files.
