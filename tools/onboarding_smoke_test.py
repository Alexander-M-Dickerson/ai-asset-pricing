#!/usr/bin/env python3
"""Smoke-test onboarding in a temporary clone-like workspace."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Mapping

sys.dont_write_bytecode = True

try:
    from tools.bootstrap import cleanup_generated_repo_artifacts, force_rmtree
except ImportError:  # pragma: no cover - script execution path
    from bootstrap import cleanup_generated_repo_artifacts, force_rmtree

REPO_ROOT = Path(__file__).resolve().parent.parent
PYBONDLAB_ROOT = REPO_ROOT / "packages" / "PyBondLab"
LEGACY_REPO_SMOKE_PREFIX = ".tmp-bootstrap-smoke-"
SMOKE_TEMP_PREFIX = "bootstrap-smoke-"
REPO_LOCAL_SMOKE_ROOT = ".test-tmp-onboarding-smoke"


def run_command(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None, timeout: int = 300) -> str:
    proc = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=env,
        timeout=timeout,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "command failed").strip()
        raise RuntimeError(f"{' '.join(cmd)} failed: {detail}")
    return (proc.stdout or "").strip()


def validate_packaging_layout(clone_root: Path) -> None:
    pyproject_text = (clone_root / "pyproject.toml").read_text(encoding="utf-8")
    required_snippets = (
        "[tool.setuptools.packages.find]",
        'include = ["fintools*"]',
    )
    for snippet in required_snippets:
        if snippet not in pyproject_text:
            raise RuntimeError(f"root pyproject.toml is missing required packaging config: {snippet}")

    if not (clone_root / "fintools" / "__init__.py").exists():
        raise RuntimeError("fintools package is missing from the temp clone")

    pybondlab_pyproject = clone_root / "packages" / "PyBondLab" / "pyproject.toml"
    if not pybondlab_pyproject.exists():
        raise RuntimeError("PyBondLab pyproject.toml is missing from the temp clone")

    if not (clone_root / "packages" / "PyBondLab" / "setup.py").exists():
        raise RuntimeError("PyBondLab setup.py is missing from the temp clone")


def copy_tree(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(
            src,
            dst,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.egg-info", ".tmp-*"),
        )
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def build_temp_repo(temp_root: Path) -> Path:
    clone_root = temp_root / "clone"
    copy_tree(REPO_ROOT / "pyproject.toml", clone_root / "pyproject.toml")
    copy_tree(REPO_ROOT / "README.md", clone_root / "README.md")
    copy_tree(REPO_ROOT / "fintools", clone_root / "fintools")
    copy_tree(REPO_ROOT / "tools" / "bootstrap.py", clone_root / "tools" / "bootstrap.py")
    copy_tree(REPO_ROOT / "tools" / "local_state.py", clone_root / "tools" / "local_state.py")
    copy_tree(REPO_ROOT / "tools" / "onboard_probe.py", clone_root / "tools" / "onboard_probe.py")
    copy_tree(PYBONDLAB_ROOT, clone_root / "packages" / "PyBondLab")
    return clone_root


def smoke_base_dir(env: Mapping[str, str] | None = None) -> Path:
    env = env or os.environ
    override = env.get("AI_ASSET_PRICING_SMOKE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path(tempfile.gettempdir())


def smoke_base_candidates(base_dir: Path | None = None) -> list[Path]:
    candidates = [base_dir or smoke_base_dir()]
    repo_local = REPO_ROOT / REPO_LOCAL_SMOKE_ROOT
    if all(candidate != repo_local for candidate in candidates):
        candidates.append(repo_local)
    return candidates


def smoke_workspace_is_usable(workspace: Path) -> bool:
    probe = workspace / "clone-probe"
    try:
        probe.mkdir(parents=False, exist_ok=False)
    except OSError:
        return False
    probe.rmdir()
    return True


def make_workspace_dir(parent: Path) -> Path:
    for _ in range(10):
        candidate = parent / f"{SMOKE_TEMP_PREFIX}{uuid.uuid4().hex[:8]}"
        try:
            candidate.mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            continue
        return candidate
    raise RuntimeError(f"failed to allocate a unique smoke workspace under {parent}")


def create_smoke_workspace(base_dir: Path | None = None) -> Path:
    last_error: OSError | None = None
    for parent in smoke_base_candidates(base_dir):
        workspace: Path | None = None
        try:
            parent.mkdir(parents=True, exist_ok=True)
            workspace = make_workspace_dir(parent)
            if smoke_workspace_is_usable(workspace):
                return workspace
            last_error = PermissionError(f"smoke workspace is not writable: {workspace}")
        except OSError as exc:
            last_error = exc
        finally:
            if workspace is not None and workspace.exists() and not smoke_workspace_is_usable(workspace):
                force_rmtree(workspace)

    raise RuntimeError(f"failed to create a writable smoke workspace: {last_error}")


def cleanup_legacy_repo_smoke_dirs() -> list[str]:
    failed: list[str] = []
    for path in REPO_ROOT.glob(f"{LEGACY_REPO_SMOKE_PREFIX}*"):
        if path.is_dir() and not force_rmtree(path):
            failed.append(str(path))
    return failed


def main() -> int:
    cleanup_generated_repo_artifacts()
    cleanup_legacy_repo_smoke_dirs()
    temp_root = create_smoke_workspace()
    try:
        clone_root = build_temp_repo(temp_root)
        python_path = Path(sys.executable).resolve()

        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["AI_ASSET_PRICING_CONFIG_DIR"] = str(temp_root / "user-config")
        env["AI_ASSET_PRICING_STATE_DIR"] = str(temp_root / "user-state")

        validate_packaging_layout(clone_root)

        audit_output = run_command(
            [str(python_path), "tools/bootstrap.py", "audit", "--skip-wrds-test", "--json"],
            cwd=clone_root,
            env=env,
        )
        audit_payload = json.loads(audit_output)
        if audit_payload.get("mode") != "audit":
            raise RuntimeError("bootstrap audit returned the wrong mode")
        audit_plan = audit_payload.get("bootstrap_plan", {}).get("steps", [])
        audit_plan_ids = {step.get("id") for step in audit_plan}
        required_plan_ids = {"install_fintools", "install_pybondlab", "apply_local_files", "rerun_audit"}
        if not required_plan_ids.issubset(audit_plan_ids):
            raise RuntimeError("bootstrap audit did not emit the expected bootstrap_plan steps for a fresh clone")

        # Smoke-test `tools/bootstrap.py apply` in the temp clone.
        apply_output = run_command(
            [str(python_path), "tools/bootstrap.py", "apply", "--skip-wrds-test", "--json"],
            cwd=clone_root,
            env=env,
        )
        apply_payload = json.loads(apply_output)
        if apply_payload.get("mode") != "apply":
            raise RuntimeError("bootstrap apply returned the wrong mode")

        local_files = apply_payload.get("local_files", [])
        if not local_files or any(item.get("status") != "OK" for item in local_files):
            raise RuntimeError("bootstrap apply did not leave all local files in OK state")
        compatibility_files = apply_payload.get("compatibility_files", [])
        if any(item.get("status") == "OK" for item in compatibility_files):
            raise RuntimeError("bootstrap apply unexpectedly wrote repo-root compatibility shims by default")
        apply_plan = apply_payload.get("bootstrap_plan", {}).get("steps", [])
        if not any(step.get("id") == "apply_local_files" for step in apply_plan):
            raise RuntimeError("bootstrap apply payload did not preserve bootstrap_plan data")

        written_files = apply_payload.get("written_files", [])
        expected = {
            str((temp_root / "user-state" / "local_env.md").resolve()),
            str((temp_root / "user-state" / "claude.local.md").resolve()),
            str((temp_root / "user-state" / "settings.local.json").resolve()),
        }
        if set(written_files) != expected:
            raise RuntimeError("bootstrap apply did not report the expected written files")
        if (clone_root / "LOCAL_ENV.md").exists() or (clone_root / "CLAUDE.local.md").exists():
            raise RuntimeError("bootstrap apply should not create repo-root compatibility shims by default")
        if (clone_root / ".claude" / "settings.local.json").exists():
            raise RuntimeError("bootstrap apply should not create repo-root settings.local.json by default")

        print("onboarding smoke test passed")
        return 0
    finally:
        cleanup_error = ""
        if temp_root.exists() and not force_rmtree(temp_root):
            cleanup_error = f"failed to remove temporary smoke workspace: {temp_root}"
        fallback_root = REPO_ROOT / REPO_LOCAL_SMOKE_ROOT
        if temp_root.parent == fallback_root and fallback_root.exists():
            try:
                fallback_root.rmdir()
            except OSError:
                pass
        cleanup_generated_repo_artifacts()
        cleanup_legacy_repo_smoke_dirs()
        if cleanup_error:
            raise RuntimeError(cleanup_error)


if __name__ == "__main__":
    raise SystemExit(main())
