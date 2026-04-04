# Contributing

Thank you for your interest in contributing to this project.

## Getting Started

1. Clone the repository.
2. Ask your agent to onboard the repo. In Claude Code the standard entry point
   is `/onboard`; in Codex and Gemini CLI, ask in chat.
3. Under the hood, the agent should use the cold-start shell driver
   (`tools/onboard.ps1` or `tools/onboard.sh`) to find or install Python 3.11+,
   then let `tools/onboard_driver.py` run `tools/bootstrap.py audit`, execute
   the emitted bootstrap plan commands, and run `tools/bootstrap.py apply` to
   write canonical local state to a per-user external directory outside the repo.

Canonical local state (tool paths, WRDS config, etc.) lives outside the repo so
that shared synced folders (Dropbox, OneDrive) stay safe for multi-user
collaboration. The paths are OS-specific and reported by `tools/bootstrap.py audit`.

Repo-root compatibility shims (`LOCAL_ENV.md`, `CLAUDE.local.md`,
`.claude/settings.local.json`) are legacy files. Do not create them in synced
folders -- they leak machine-specific state to other users.

WRDS is optional. The agent should ask once whether the user has a WRDS account.
If the answer is no, onboarding should skip WRDS setup and still complete once
the base repo is usable.

## Synced Folders (OneDrive, Dropbox)

If the repo lives in a synced folder:

- All local state is written to external per-user directories automatically.
- `--write-compat-shims` is refused by bootstrap when a synced folder is detected.
- If repo-root compat shims already exist, `tools/bootstrap.py audit` flags them
  for removal and the bootstrap plan includes a cleanup step.
- Claude Code may auto-create `.claude/settings.local.json` on permission
  approvals. This file is `.gitignore`-d and should be manually deleted if it
  contains user-specific paths. See `docs/ai/onboarding.md` for details.

## Development Workflow

- Make changes on a feature branch.
- Run `tools/release_preflight.py --strict` before committing.
- Ensure `tools/onboarding_smoke_test.py` passes.
- Open a pull request against `main`.

Strict preflight auto-cleans repo temp artifacts and tolerates gitignored
repo-root local artifacts such as `.venv/`, `venv/`, and `.Rhistory`, but it
still expects the repo to be free of repo-root compatibility shims.

## Code Style

- Python: follow existing patterns in `fintools/` and `tools/`.
- LaTeX: follow `.claude/rules/latex-conventions.md`.
- Academic writing: follow `.claude/rules/academic-writing.md`.

## Adding Skills or Rules

- Use `/create-skill` or `/rule-create` to scaffold new files.
- See `.claude/exemplars/rules_best_practices.md` for rule guidelines.
- See `.claude/exemplars/agents_best_practices.md` for agent guidelines.

## Reporting Issues

Open an issue on GitHub with:
- What you expected to happen
- What actually happened
- Your OS, Python version, and shell (from `tools/bootstrap.py audit` output)
