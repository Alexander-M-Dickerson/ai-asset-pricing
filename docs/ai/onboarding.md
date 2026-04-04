# Shared Onboarding

This repo has one shared Python-level onboarding engine for Claude Code,
Codex, and Gemini CLI: `tools/bootstrap.py`.

For cold-start machines, the repo-local shell entrypoints are:

- `tools/onboard.ps1`
- `tools/onboard.sh`

Those shell entrypoints should find or install Python 3.11+, then hand off to
`tools/onboard_driver.py`, which runs the shared `tools/bootstrap.py` flow.

## Canonical Local State

Canonical local state lives outside the repo in a per-user OS-specific path
reported by `tools/bootstrap.py audit`. The canonical `local_env.md` should contain:

- platform and shell
- Python path and version
- bash path and version
- canonical install command (`uv pip` when available, `python -m pip` as fallback)
- `psql` path and version
- WRDS config status
- any platform-specific notes

`tools/bootstrap.py apply` writes or refreshes canonical external files:

- `local_env.md`
- `claude.local.md`
- `settings.local.json`

Repo-root `LOCAL_ENV.md`, `CLAUDE.local.md`, and `.claude/settings.local.json`
are legacy compatibility shims only. Generate them only when you explicitly need
single-user backward compatibility inside a private working copy.

## Shared Bootstrap Flow

For normal agent use, the user should not need to type these commands by hand.
They should ask the agent to onboard or set up the repo, and the agent should
run this shared flow on their behalf.

1. Find or install a working Python 3.11+ interpreter.
2. Ask once whether the user has WRDS and wants it configured now.
3. Run `<python> tools/bootstrap.py audit --json`.
4. Execute the emitted `bootstrap_plan.steps` for the current shell.
5. Run `<python> tools/bootstrap.py apply`.
6. Re-run `<python> tools/bootstrap.py audit`.
7. Treat `<python> tools/bootstrap.py repair --write-canonical-state` as an optional convenience for direct local terminals, not the primary agent path.

On Windows, if bare `python` hits the Store shim or the wrong install, use the
exact interpreter path reported by `tools/bootstrap.py audit`. `py` is optional,
not required.

## Tool-Specific Entry Points

- Claude Code users: clone the repo, ask Claude to onboard the repo, and let `/onboard` wrap the cold-start shell entrypoint plus the shared bootstrap `audit` -> execute bootstrap plan -> `apply` -> `audit` flow.
- Codex users: clone the repo, ask Codex in chat to onboard or set up the repo, and have it run the same cold-start shell entrypoint plus shared bootstrap flow.
- Gemini CLI users: clone the repo, ask Gemini CLI to onboard or set up the repo, and have it run the same cold-start shell entrypoint plus shared bootstrap flow. Read `GEMINI.md` for Gemini-specific notes.

## Underlying Probe

`tools/onboard_probe.py` is the reusable probe library and CLI used by
`tools/bootstrap.py`. It remains part of the contract, but it is not the
primary onboarding entry point.

## Bootstrap Plan Contract

`tools/bootstrap.py audit` is the source of truth for what still needs to run.
If the repo is not ready yet, the audit report should emit a `bootstrap_plan`
with exact PowerShell/native and Bash commands plus phase metadata for:

- missing core shell/runtime tools
- missing Python packages
- missing or external repo package installs
- optional WRDS setup
- optional writing/R setup
- refreshing canonical external local state
- rerunning the audit at the end

Agents should prefer executing those commands directly, because that allows the
agent runtime to request any needed approvals for package installation.

## Rules

- Never assume bare `python` or `pip` are safe on Windows.
- Claude hook automation requires `bash` on `PATH`; on Windows, Git Bash is the expected setup.
- Prefer `uv pip install --python <path>` when uv is available; fall back to `<path> -m pip install`.
- Prefer `tools/onboard.ps1` / `tools/onboard.sh` plus `tools/onboard_driver.py` for true cold-start onboarding.
- If canonical local state is missing, create it before relying on machine-specific commands.
- Prefer `tools/bootstrap.py audit`, its emitted `bootstrap_plan`, and `tools/bootstrap.py apply` over ad hoc local file generation.
- Keep `tools/bootstrap.py repair --write-canonical-state` as a convenience fallback for unsandboxed local terminals.
- `tools/release_preflight.py --strict` auto-cleans repo temp artifacts such as `.tmp-*`, `.test-tmp-*`, and `__pycache__`, and it tolerates gitignored repo-root local artifacts such as `.venv/`, `venv/`, and `.Rhistory`. It still treats repo-root compatibility shims as release blockers.
- If the repo lives in Dropbox/OneDrive, keep canonical local state external and avoid repo-root compatibility shims unless the working copy is private to one machine.
- Dropbox/OneDrive are supported sync layers, not a substitute for Git merge/conflict handling on the same tracked code/config files.
- WRDS is optional. Ask once whether the user has a WRDS account and wants it configured now. If the answer is no, skip WRDS setup and still treat onboarding as complete once the base repo is ready.
- If WRDS is requested, use `tools/bootstrap.py wrds-files` with a password env var to write `pg_service.conf` / `.pgpass` without echoing the password.

## Claude Code Permissions and `settings.local.json`

Claude Code may auto-create `.claude/settings.local.json` in the repo root when
a user clicks "always allow" on a permission prompt. This is upstream Claude Code
behavior, not controlled by bootstrap. Key facts:

- Claude Code's overwrite bug (GitHub issues #9234, #9814, #9875) replaces the
  entire `permissions.allow` array on each approval, so machine-specific entries
  placed there get wiped.
- The shared `.claude/settings.json` already has generic globs (`*/python*`,
  `*/psql*`) that cover all common tool paths across machines.
- Bootstrap no longer writes machine-specific Bash entries to
  `settings.local.json`. It writes only a minimal structure to the canonical
  external path.
- If `.claude/settings.local.json` appears in the repo root with user-specific
  paths, it is safe to delete. It is `.gitignore`-d and will not propagate via
  Git. However, OneDrive and Dropbox sync ignore `.gitignore`, so the file may
  propagate via cloud sync.
- OneDrive has no file-level exclusion mechanism (no `.driveignore`). The only
  defense against synced local files is architectural elimination: keep all
  important permissions in the shared `settings.json` so the auto-created local
  file is inconsequential.
