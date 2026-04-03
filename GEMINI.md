# Gemini CLI Adapter

This file is auto-loaded by Gemini CLI. It imports the shared routing layer
and adds Gemini-specific notes.

@AGENTS.md

## Gemini-Specific Notes

- Onboarding: ask Gemini CLI to onboard or set up the repo in chat. Under the
  hood it should run `tools/bootstrap.py audit`, execute the bootstrap plan,
  then `tools/bootstrap.py apply`. This is the same shared flow as Claude
  `/onboard` and Codex.
- Skills: read `.claude/skills/*/SKILL.md` files directly — they are plain markdown
  instructions, not Claude-binary artifacts. Gemini can follow them as-is.
- Domain experts: read `.claude/agents/*.md` for deep WRDS, CRSP, OptionMetrics,
  TAQ, bonds, and Fama-French domain context.
- Hooks: `.claude/hooks/` are Claude Code automation (LaTeX rebuild, pre-commit
  preflight). Gemini CLI users should run `tools/release_preflight.py --strict`
  manually before commits.
- Strict preflight auto-cleans repo temp artifacts and tolerates gitignored
  repo-root virtual environments such as `.venv/`, but it still treats
  `.Rhistory` and repo-root compatibility shims as release blockers.
- MCP: Perplexity MCP is configured in `.claude/settings.json`. Gemini users
  should configure equivalent MCP servers in `.gemini/settings.json` if needed.
- The canonical local state lives outside the repo. See `docs/ai/onboarding.md`.
