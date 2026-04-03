#!/usr/bin/env python3
"""Release preflight checks for clone-and-bootstrap readiness."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.dont_write_bytecode = True

try:
    from tools.bootstrap import cleanup_generated_repo_artifacts
except ImportError:  # pragma: no cover - script execution path
    from bootstrap import cleanup_generated_repo_artifacts


REQUIRED_FILES = (
    Path("AGENTS.md"),
    Path("README.md"),
    Path("CLAUDE.md"),
    Path(".claude/settings.json"),
    Path(".claude/skills/onboard/SKILL.md"),
    Path(".claude/skills/setup-paper/SKILL.md"),
    Path(".claude/skills/new-project/SKILL.md"),
    Path(".claude/skills/build-context/SKILL.md"),
    Path("boilerplate/template_main.tex"),
    Path("boilerplate/template_references.bib"),
    Path("docs/ai/core.md"),
    Path("docs/ai/onboarding.md"),
    Path("docs/ai/wrds.md"),
    Path("docs/ai/pybondlab.md"),
    Path("docs/ai/writing.md"),
    Path("packages/PyBondLab/AGENTS.md"),
    Path("packages/PyBondLab/pyproject.toml"),
    Path("packages/PyBondLab/PyBondLab/data/__init__.py"),
    Path("packages/PyBondLab/PyBondLab/data/data_loading.py"),
    Path("packages/PyBondLab/PyBondLab/data/WRDS/__init__.py"),
    Path("packages/PyBondLab/PyBondLab/data/WRDS/breakpoints_wrds.csv"),
    Path("CONTRIBUTING.md"),
    Path("GEMINI.md"),
    Path("tools/bootstrap.py"),
    Path("tools/context_drift.py"),
    Path("tools/local_state.py"),
    Path("tools/onboarding_smoke_test.py"),
    Path("tools/onboard_probe.py"),
)

REQUIRED_GITIGNORE_ENTRIES = (
    "LOCAL_ENV.md",
    "CLAUDE.local.md",
    ".claude/settings.local.json",
    ".venv/",
    "venv/",
    ".Rhistory",
    "*.egg-info/",
    "*.nbc",
    "*.nbi",
)

BOOTSTRAP_LOCAL_PATHS = (
    Path("LOCAL_ENV.md"),
    Path("CLAUDE.local.md"),
    Path(".claude/settings.local.json"),
)

REQUIRED_GIT_TRACKED_PATHS = (
    Path("packages/PyBondLab/PyBondLab/data/__init__.py"),
    Path("packages/PyBondLab/PyBondLab/data/data_loading.py"),
    Path("packages/PyBondLab/PyBondLab/data/WRDS/__init__.py"),
    Path("packages/PyBondLab/PyBondLab/data/WRDS/breakpoints_wrds.csv"),
)

EXACT_FORBIDDEN_PATHS = (Path(".Rhistory"),)

FORBIDDEN_DIR_NAMES = {"__pycache__"}
ROOT_LEVEL_IGNORED_DIR_NAMES = {".venv", "venv"}
FORBIDDEN_DIR_PREFIXES = (".tmp-", ".test-tmp-")
FORBIDDEN_DIR_SUFFIXES = (".egg-info",)
FORBIDDEN_FILE_SUFFIXES = (".pyc", ".pyo", ".pyd", ".nbc", ".nbi")

LOCAL_PATH_PATTERNS = (
    re.compile(r"(?i)c:\\users\\"),
    re.compile(r"(?i)//c/users/"),
    re.compile(r"/Users/"),
    re.compile(r"/home/"),
)

SHARED_TEXT_FILES = (
    Path("AGENTS.md"),
    Path("README.md"),
    Path("CLAUDE.md"),
    Path(".claude/settings.json"),
    Path(".claude/skills/onboard/SKILL.md"),
    Path("docs/ai/core.md"),
    Path("docs/ai/onboarding.md"),
    Path("docs/ai/wrds.md"),
    Path("docs/ai/pybondlab.md"),
    Path("docs/ai/writing.md"),
    Path("CONTRIBUTING.md"),
    Path("GEMINI.md"),
    Path("packages/PyBondLab/AGENTS.md"),
    Path("tools/bootstrap.py"),
    Path("tools/onboard_probe.py"),
    Path(".claude/skills/setup-paper/SKILL.md"),
)

REQUIRED_BOOTSTRAP_SNIPPETS = {
    Path("README.md"): ("tools/bootstrap.py", "/onboard", "canonical local state"),
    Path("AGENTS.md"): ("tools/bootstrap.py", "docs/ai/onboarding.md", "canonical local state"),
    Path("CLAUDE.md"): ("tools/bootstrap.py", "/onboard", "canonical local state"),
    Path("CONTRIBUTING.md"): ("tools/bootstrap.py", "canonical local state", "/onboard"),
    Path("GEMINI.md"): ("AGENTS.md", "tools/bootstrap.py", "canonical local state"),
    Path("docs/ai/onboarding.md"): ("tools/bootstrap.py", "audit", "bootstrap_plan", "apply", "/onboard", "canonical local state"),
    Path(".claude/skills/onboard/SKILL.md"): ("tools/bootstrap.py audit", "bootstrap_plan.steps", "tools/bootstrap.py apply"),
    Path("tools/onboard_probe.py"): ("def collect_probe",),
    Path("tools/bootstrap.py"): ("audit", "repair", "apply", "collect_probe", "build_bootstrap_plan", "write_compat_shims"),
    Path("tools/local_state.py"): ("def canonical_directories", "def local_state_records"),
    Path("tools/onboarding_smoke_test.py"): ("validate_packaging_layout", "bootstrap.py apply", "AI_ASSET_PRICING_STATE_DIR"),
    Path(".claude/skills/setup-paper/SKILL.md"): ("boilerplate/template_main.tex", "[REMOVE]", "references.bib"),
    Path(".claude/skills/new-project/SKILL.md"): ("/setup-paper",),
    Path(".claude/skills/build-context/SKILL.md"): ("guidance/paper-context.md", "guidance/"),
}


@dataclass
class Finding:
    level: str
    message: str


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def require_snippets(findings: list[Finding], root: Path, rel_path: Path, snippets: tuple[str, ...]) -> None:
    path = root / rel_path
    if not path.exists():
        return
    text = read_text(path)
    for snippet in snippets:
        if snippet not in text:
            findings.append(
                Finding(
                    "FAIL",
                    f"{rel_path.as_posix()} is missing required bootstrap contract text: {snippet}",
                )
            )


def unique_strings(values: list[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique


def summarize_paths(paths: list[str], *, limit: int = 6) -> str:
    unique_paths = unique_strings(paths)
    if len(unique_paths) <= limit:
        return ", ".join(unique_paths)
    shown = ", ".join(unique_paths[:limit])
    return f"{shown}, and {len(unique_paths) - limit} more"


def run_onboarding_smoke(root: Path) -> Finding:
    smoke_script = root / "tools" / "onboarding_smoke_test.py"
    if not smoke_script.exists():
        return Finding("FAIL", "Missing onboarding smoke test script")

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    smoke_temp_dir = Path(tempfile.mkdtemp(prefix="ai-asset-pricing-preflight-"))
    env["AI_ASSET_PRICING_SMOKE_DIR"] = str(smoke_temp_dir)
    try:
        proc = subprocess.run(
            [sys.executable, "-B", str(smoke_script)],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(root),
            env=env,
            timeout=300,
        )
    finally:
        shutil.rmtree(smoke_temp_dir, ignore_errors=True)
    if proc.returncode == 0:
        return Finding("PASS", "Onboarding smoke test passed")

    detail = (proc.stderr or proc.stdout or "onboarding smoke test failed").strip()
    return Finding("FAIL", f"Onboarding smoke test failed: {detail}")


def run_pybondlab_smoke(root: Path) -> Finding:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(root / "packages" / "PyBondLab"),
            env.get("PYTHONPATH", ""),
        ]
    ).rstrip(os.pathsep)
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            (
                "import PyBondLab as pbl; "
                "assert pbl.StrategyFormation is not None; "
                "assert pbl.BatchStrategyFormation is not None; "
                "df = pbl.load_breakpoints_WRDS(); "
                "assert not df.empty"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(root),
        env=env,
        timeout=120,
    )
    if proc.returncode == 0:
        return Finding("PASS", "PyBondLab import and bundled-data smoke test passed")

    detail = (proc.stderr or proc.stdout or "PyBondLab smoke test failed").strip()
    return Finding("FAIL", f"PyBondLab smoke test failed: {detail}")


def has_git_metadata(root: Path) -> bool:
    return (root / ".git").exists()


def git_tracks_path(root: Path, rel_path: Path) -> bool | None:
    if not has_git_metadata(root):
        return None

    proc = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel_path.as_posix()],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=15,
    )
    return proc.returncode == 0


def collect_release_tree_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []

    for rel_path in EXACT_FORBIDDEN_PATHS:
        if (root / rel_path).exists():
            findings.append(Finding("FAIL", f"Release tree contains local/generated file: {rel_path.as_posix()}"))

    for current_root, dirnames, filenames in os.walk(root, topdown=True):
        current_path = Path(current_root)
        try:
            relative_root = current_path.relative_to(root)
        except ValueError:
            continue

        if relative_root != Path(".") and ".git" in relative_root.parts:
            dirnames[:] = []
            continue

        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            if dirname == ".git":
                continue
            relative = Path(dirname) if relative_root == Path(".") else relative_root / dirname
            if relative_root == Path(".") and dirname in ROOT_LEVEL_IGNORED_DIR_NAMES:
                continue
            if (
                dirname in FORBIDDEN_DIR_NAMES
                or dirname.startswith(FORBIDDEN_DIR_PREFIXES)
                or dirname.endswith(FORBIDDEN_DIR_SUFFIXES)
            ):
                findings.append(Finding("FAIL", f"Release tree contains generated directory: {relative.as_posix()}"))
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in filenames:
            relative = Path(filename) if relative_root == Path(".") else relative_root / filename
            if Path(filename).suffix in FORBIDDEN_FILE_SUFFIXES:
                findings.append(Finding("FAIL", f"Release tree contains generated file: {relative.as_posix()}"))

    return findings


def collect_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    cleaned_artifacts = cleanup_generated_repo_artifacts(root)

    for rel_path in REQUIRED_FILES:
        if not (root / rel_path).exists():
            findings.append(Finding("FAIL", f"Missing required file: {rel_path.as_posix()}"))

    for rel_path, snippets in REQUIRED_BOOTSTRAP_SNIPPETS.items():
        require_snippets(findings, root, rel_path, snippets)

    gitignore_path = root / ".gitignore"
    gitignore_text = read_text(gitignore_path) if gitignore_path.exists() else ""
    for entry in REQUIRED_GITIGNORE_ENTRIES:
        if entry not in gitignore_text:
            findings.append(Finding("FAIL", f".gitignore is missing required entry: {entry}"))

    findings.append(run_onboarding_smoke(root))
    findings.append(run_pybondlab_smoke(root))
    cleaned_artifacts.extend(cleanup_generated_repo_artifacts(root))

    cleaned_artifacts = unique_strings(cleaned_artifacts)
    if cleaned_artifacts:
        findings.append(
            Finding(
                "INFO",
                f"Auto-cleaned generated artifacts: {summarize_paths(cleaned_artifacts)}",
            )
        )

    for rel_path in BOOTSTRAP_LOCAL_PATHS:
        if not (root / rel_path).exists():
            continue
        findings.append(Finding("FAIL", f"Release tree contains repo-root local/generated file: {rel_path.as_posix()}"))

    if has_git_metadata(root):
        for rel_path in REQUIRED_GIT_TRACKED_PATHS:
            if git_tracks_path(root, rel_path):
                continue
            findings.append(
                Finding(
                    "FAIL",
                    f"Required PyBondLab package file is not tracked by git: {rel_path.as_posix()}",
                )
            )

    findings.extend(collect_release_tree_findings(root))

    settings_path = root / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(read_text(settings_path))
        except json.JSONDecodeError as exc:
            findings.append(Finding("FAIL", f".claude/settings.json is invalid JSON: {exc}"))
        else:
            if "enabledPlugins" in settings:
                findings.append(Finding("FAIL", ".claude/settings.json should not enable user-local plugins"))
            serialized = json.dumps(settings)
            if "mcp__" in serialized:
                findings.append(Finding("WARN", ".claude/settings.json still contains MCP-specific permissions"))

    for rel_path in SHARED_TEXT_FILES:
        path = root / rel_path
        if not path.exists():
            continue
        text = read_text(path)
        for pattern in LOCAL_PATH_PATTERNS:
            if pattern.search(text):
                findings.append(
                    Finding("FAIL", f"Shared file leaks a user-specific absolute path: {rel_path.as_posix()}")
                )
                break

    readme_path = root / "README.md"
    if readme_path.exists():
        readme = read_text(readme_path)
        if "/onboard" not in readme:
            findings.append(Finding("FAIL", "README.md no longer documents /onboard"))
        if "tools/bootstrap.py" not in readme:
            findings.append(Finding("FAIL", "README.md does not document tools/bootstrap.py"))
        if "release_preflight.py" not in readme:
            findings.append(Finding("WARN", "README.md does not mention the release preflight checker"))
        if "canonical local state" not in readme:
            findings.append(Finding("FAIL", "README.md does not document canonical external local state"))

    agents_path = root / "AGENTS.md"
    if agents_path.exists():
        agents = read_text(agents_path)
        if "docs/ai/onboarding.md" not in agents:
            findings.append(Finding("FAIL", "AGENTS.md does not route onboarding tasks"))
        if "tools/bootstrap.py" not in agents:
            findings.append(Finding("FAIL", "AGENTS.md does not reference tools/bootstrap.py"))
        if "canonical local state" not in agents:
            findings.append(Finding("FAIL", "AGENTS.md does not reference canonical local state"))

    claude_path = root / "CLAUDE.md"
    if claude_path.exists():
        claude = read_text(claude_path)
        if "tools/bootstrap.py" not in claude:
            findings.append(Finding("FAIL", "CLAUDE.md does not reference tools/bootstrap.py"))
        if "canonical local state" not in claude:
            findings.append(Finding("FAIL", "CLAUDE.md does not reference canonical local state"))

    onboarding_path = root / "docs" / "ai" / "onboarding.md"
    if onboarding_path.exists():
        onboarding = read_text(onboarding_path)
        if "tools/bootstrap.py" not in onboarding:
            findings.append(Finding("FAIL", "docs/ai/onboarding.md does not reference tools/bootstrap.py"))
        if "audit" not in onboarding or "bootstrap_plan" not in onboarding or "apply" not in onboarding:
            findings.append(Finding("FAIL", "docs/ai/onboarding.md does not describe bootstrap audit/bootstrap_plan/apply"))

    if not has_git_metadata(root):
        findings.append(Finding("INFO", "No .git directory found; git-tracked release checks were skipped"))

    if not findings:
        findings.append(Finding("PASS", "No release-preflight issues found"))

    return findings


def print_findings(findings: list[Finding]) -> None:
    for finding in findings:
        print(f"[{finding.level}] {finding.message}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    findings = collect_findings(root)
    print_findings(findings)

    has_fail = any(f.level == "FAIL" for f in findings)
    has_warn = any(f.level == "WARN" for f in findings)
    return 1 if has_fail or (args.strict and has_warn) else 0


if __name__ == "__main__":
    raise SystemExit(main())
