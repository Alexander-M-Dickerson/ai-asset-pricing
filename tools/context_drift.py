#!/usr/bin/env python3
"""Detect documentation drift: source files changed but docs not updated."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent

# Each tuple: (source_glob, doc_file)
# Verified against actual file contents — see plan for line-number references.
DRIFT_MAP: list[tuple[str, str]] = [
    # docs/ai/onboarding.md references tools/bootstrap.py, onboard_probe.py, local_state.py
    ("tools/bootstrap.py", "docs/ai/onboarding.md"),
    ("tools/onboard_probe.py", "docs/ai/onboarding.md"),
    ("tools/local_state.py", "docs/ai/onboarding.md"),
    # docs/ai/core.md references fintools/, .claude/hooks/, tools/release_preflight.py
    ("fintools/**/*.py", "docs/ai/core.md"),
    (".claude/hooks/*.sh", "docs/ai/core.md"),
    ("tools/release_preflight.py", "docs/ai/core.md"),
    # docs/ai/pybondlab.md references PyBondLab code and docs
    ("packages/PyBondLab/PyBondLab/*.py", "docs/ai/pybondlab.md"),
    ("packages/PyBondLab/docs/*.md", "docs/ai/pybondlab.md"),
    # docs/ai/wrds.md references agent files and wrds-psql skill
    (".claude/agents/crsp-wrds-expert.md", "docs/ai/wrds.md"),
    (".claude/agents/optionmetrics-wrds-expert.md", "docs/ai/wrds.md"),
    (".claude/agents/bonds-wrds-expert.md", "docs/ai/wrds.md"),
    (".claude/agents/taq-wrds-expert.md", "docs/ai/wrds.md"),
    (".claude/agents/ff-wrds-expert.md", "docs/ai/wrds.md"),
    (".claude/skills/wrds-psql/SKILL.md", "docs/ai/wrds.md"),
    # docs/ai/writing.md references boilerplate and compile hook
    ("boilerplate/template_main.tex", "docs/ai/writing.md"),
    ("boilerplate/template_references.bib", "docs/ai/writing.md"),
    (".claude/hooks/compile-tex.sh", "docs/ai/writing.md"),
    # AGENTS.md must reflect docs/ai/
    ("docs/ai/core.md", "AGENTS.md"),
    ("docs/ai/onboarding.md", "AGENTS.md"),
    ("docs/ai/wrds.md", "AGENTS.md"),
    ("docs/ai/pybondlab.md", "AGENTS.md"),
    ("docs/ai/writing.md", "AGENTS.md"),
    # CLAUDE.md must reflect docs/ai/
    ("docs/ai/core.md", "CLAUDE.md"),
    ("docs/ai/onboarding.md", "CLAUDE.md"),
    # CONTRIBUTING.md must reflect onboarding and bootstrap
    ("tools/bootstrap.py", "CONTRIBUTING.md"),
    ("docs/ai/onboarding.md", "CONTRIBUTING.md"),
]

# Minimum staleness in days before flagging (avoids noise from same-day commits).
DRIFT_THRESHOLD_DAYS = 1.0


def last_commit_epoch(pattern: str) -> int | None:
    """Return epoch of most recent commit touching files matching a glob or path."""
    from glob import glob as globfn

    files = globfn(str(REPO_ROOT / pattern), recursive=True)
    if not files:
        # Also try the pattern as a literal path
        literal = REPO_ROOT / pattern
        if literal.exists():
            files = [str(literal)]
        else:
            return None

    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--"] + files,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
    except Exception:
        return None

    output = (proc.stdout or "").strip()
    if not output:
        return None
    try:
        return int(output)
    except ValueError:
        return None


def check_drift() -> list[dict[str, object]]:
    """Return a list of drift warnings."""
    warnings: list[dict[str, object]] = []
    for source_glob, doc_file in DRIFT_MAP:
        source_epoch = last_commit_epoch(source_glob)
        doc_epoch = last_commit_epoch(doc_file)
        if source_epoch is None or doc_epoch is None:
            continue
        if source_epoch > doc_epoch:
            days_stale = (source_epoch - doc_epoch) / 86400
            if days_stale >= DRIFT_THRESHOLD_DAYS:
                warnings.append(
                    {
                        "source": source_glob,
                        "doc": doc_file,
                        "days_stale": round(days_stale, 1),
                    }
                )
    return warnings


def print_table(warnings: list[dict[str, object]]) -> None:
    """Print a human-readable drift table."""
    if not warnings:
        print("No documentation drift detected.")
        return

    print(f"{'Source':<50} {'Doc':<30} {'Days Stale':>10}")
    print("-" * 92)
    for w in warnings:
        print(f"{w['source']:<50} {w['doc']:<30} {w['days_stale']:>10}")
    print()
    print(f"{len(warnings)} mapping(s) may be stale. Run /sync-context to review.")


def print_brief(warnings: list[dict[str, object]]) -> None:
    """Print a one-line summary (empty if no drift)."""
    if not warnings:
        return
    docs = sorted(set(str(w["doc"]) for w in warnings))
    print(f"{len(warnings)} doc mapping(s) may be stale: {', '.join(docs)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", help="Emit JSON output.")
    group.add_argument("--brief", action="store_true", help="One-line summary.")
    args = parser.parse_args(argv)

    warnings = check_drift()

    if args.json:
        json.dump(warnings, sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif args.brief:
        print_brief(warnings)
    else:
        print_table(warnings)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
