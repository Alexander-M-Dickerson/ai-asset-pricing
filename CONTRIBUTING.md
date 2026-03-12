# Contributing

Thank you for your interest in contributing to this project.

## Getting Started

1. Clone the repository
2. Run `/onboard` (Claude Code) or follow `docs/ai/onboarding.md` (Codex)
3. This creates `LOCAL_ENV.md` with your machine-specific tool paths

## Development Workflow

- Make changes on a feature branch
- Run `tools/release_preflight.py --strict` before committing
- Ensure `tools/onboarding_smoke_test.py` passes
- Open a pull request against `main`

## Code Style

- Python: follow existing patterns in `fintools/` and `tools/`
- LaTeX: follow `.claude/rules/latex-conventions.md`
- Academic writing: follow `.claude/rules/academic-writing.md`

## Adding Skills or Rules

- Use `/create-skill` or `/rule-create` to scaffold new files
- See `.claude/exemplars/rules_best_practices.md` for rule guidelines
- See `.claude/exemplars/agents_best_practices.md` for agent guidelines

## Reporting Issues

Open an issue on GitHub with:
- What you expected to happen
- What actually happened
- Your OS, Python version, and shell (from `LOCAL_ENV.md` if available)
