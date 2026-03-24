# Shared Onboarding

This repo has one repo-local onboarding engine for Claude Code, Codex, and Gemini CLI:
`tools/bootstrap.py`.

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

1. Find a working Python interpreter.
2. Run `<python> tools/bootstrap.py audit`.
3. Execute the required shell-specific commands listed in the audit report's `bootstrap_plan`.
4. Run `<python> tools/bootstrap.py apply`.
5. Re-run `<python> tools/bootstrap.py audit`.
6. Treat `<python> tools/bootstrap.py repair --write-canonical-state` as an optional convenience for direct local terminals, not the primary agent path.

On Windows, if bare `python` hits the Store shim or the wrong install, use the
exact interpreter path reported by `tools/bootstrap.py audit`. `py` is optional,
not required.

## Tool-Specific Entry Points

- Claude Code users: clone the repo, run `/onboard`, and let the skill wrap the shared bootstrap `audit` -> execute bootstrap plan -> `apply` -> `audit` flow.
- Codex users: clone the repo, ask Codex to set up the repo, and have it run the same shared bootstrap `audit` -> execute bootstrap plan -> `apply` -> `audit` flow.
- Gemini CLI users: clone the repo, follow the bootstrap `audit` -> execute bootstrap plan -> `apply` -> `audit` flow described above. Read `GEMINI.md` for Gemini-specific notes.

## Underlying Probe

`tools/onboard_probe.py` is the reusable probe library and CLI used by
`tools/bootstrap.py`. It remains part of the contract, but it is not the
primary onboarding entry point.

## Bootstrap Plan Contract

`tools/bootstrap.py audit` is the source of truth for what still needs to run.
If the repo is not ready yet, the audit report should emit a `bootstrap_plan`
with exact PowerShell/native and Bash commands for:

- missing Python packages
- missing or external repo package installs
- refreshing canonical external local state
- rerunning the audit at the end

Agents should prefer executing those commands directly, because that allows the
agent runtime to request any needed approvals for package installation.

## Rules

- Never assume bare `python` or `pip` are safe on Windows.
- Claude hook automation requires `bash` on `PATH`; on Windows, Git Bash is the expected setup.
- Prefer `uv pip install --python <path>` when uv is available; fall back to `<path> -m pip install`.
- If canonical local state is missing, create it before relying on machine-specific commands.
- Prefer `tools/bootstrap.py audit`, its emitted `bootstrap_plan`, and `tools/bootstrap.py apply` over ad hoc local file generation.
- Keep `tools/bootstrap.py repair --write-canonical-state` as a convenience fallback for unsandboxed local terminals.
- If the repo lives in Dropbox/OneDrive, keep canonical local state external and avoid repo-root compatibility shims unless the working copy is private to one machine.
- Dropbox/OneDrive are supported sync layers, not a substitute for Git merge/conflict handling on the same tracked code/config files.
- If WRDS access is missing, record the missing pieces explicitly but treat onboarding as complete. WRDS is optional — only needed for data extraction workflows.

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
