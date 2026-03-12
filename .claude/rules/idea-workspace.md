---
description: Conventions for idea workspace folders under projects/*_idea/. Enforces append-only musings, verification markers, and research plan template compliance.
paths:
  - "projects/*_idea/**"
---

# Idea Workspace Conventions

These rules apply when editing any file inside a `projects/*_idea/` folder.

## musings.md

- **Append-only**: Never overwrite or delete previous round entries. Each round adds a new `## Round {N}` section at the bottom.
- The YAML header at the top (`Status:`) may be updated (e.g., `active` to `graduated`).
- Each round entry must include: Challenge, User response, Synthesis, Feasibility, Status.

## literature.md

- Every paper must carry a verification status: **VERIFIED**, **PARTIAL**, or **UNVERIFIED**.
- Only report bibliographic details that Perplexity explicitly confirmed. Write "UNCONFIRMED" for any field not verified. Never fill from training data.
- Organize papers into three sections: builds on, differentiates from, methodological references.

## research_plan.md

- Must follow the template in `.claude/skills/idea/research-plan-template.md`.
- The one-sentence contribution must be concrete and specific (Cochrane style), not a vague abstract.
- All `{placeholders}` must be replaced with actual content before the plan is considered complete.

## Folder scope

- `_idea/` folders are lightweight: they contain only `musings.md`, `literature.md`, and `research_plan.md`.
- Do NOT create `latex/`, `code/`, `results/`, or other project subdirectories here.
- To graduate to a full project, use `/idea resume {mnemonic}` (Phase 6) or run `/new-project` manually.
