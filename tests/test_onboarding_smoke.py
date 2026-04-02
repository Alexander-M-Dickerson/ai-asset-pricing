"""Regression coverage for onboarding smoke temp-workspace handling."""

from pathlib import Path
import uuid

from tools import onboarding_smoke_test as smoke


def make_temp_root() -> Path:
    root = Path(".test-tmp-onboarding-smoke") / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    return root


def cleanup_temp_root(temp_root: Path) -> None:
    smoke.force_rmtree(temp_root)
    parent = temp_root.parent
    if parent.name == ".test-tmp-onboarding-smoke":
        try:
            parent.rmdir()
        except OSError:
            pass


def test_smoke_base_dir_prefers_override(monkeypatch):
    temp_root = make_temp_root()
    try:
        monkeypatch.setenv("AI_ASSET_PRICING_SMOKE_DIR", str(temp_root))
        assert smoke.smoke_base_dir() == temp_root
    finally:
        cleanup_temp_root(temp_root)


def test_create_smoke_workspace_uses_requested_base_dir():
    temp_root = make_temp_root()
    workspace = smoke.create_smoke_workspace(temp_root)
    try:
        assert workspace.parent.resolve() == temp_root.resolve()
        assert workspace.name.startswith(smoke.SMOKE_TEMP_PREFIX)
    finally:
        smoke.force_rmtree(workspace)
        cleanup_temp_root(temp_root)


def test_create_smoke_workspace_falls_back_to_repo_local_root(monkeypatch):
    temp_root = make_temp_root()
    fallback_root = temp_root / smoke.REPO_LOCAL_SMOKE_ROOT
    monkeypatch.setattr(smoke, "REPO_ROOT", temp_root)
    monkeypatch.setattr(smoke, "smoke_base_dir", lambda env=None: temp_root / "blocked")

    real_usability_check = smoke.smoke_workspace_is_usable

    def fake_is_usable(workspace):
        if workspace.parent.name == "blocked":
            return False
        return real_usability_check(workspace)

    monkeypatch.setattr(smoke, "smoke_workspace_is_usable", fake_is_usable)

    workspace = smoke.create_smoke_workspace()
    try:
        assert workspace.parent.resolve() == fallback_root.resolve()
        assert workspace.name.startswith(smoke.SMOKE_TEMP_PREFIX)
    finally:
        smoke.force_rmtree(workspace)
        cleanup_temp_root(temp_root)


def test_cleanup_legacy_repo_smoke_dirs_removes_stale_dirs(monkeypatch):
    temp_root = make_temp_root()
    stale = temp_root / f"{smoke.LEGACY_REPO_SMOKE_PREFIX}old"
    stale.mkdir()
    monkeypatch.setattr(smoke, "REPO_ROOT", temp_root)

    try:
        failures = smoke.cleanup_legacy_repo_smoke_dirs()

        assert failures == []
        assert not stale.exists()
    finally:
        cleanup_temp_root(temp_root)


def test_cleanup_legacy_repo_smoke_dirs_reports_failures(monkeypatch):
    temp_root = make_temp_root()
    stale = temp_root / f"{smoke.LEGACY_REPO_SMOKE_PREFIX}locked"
    stale.mkdir()
    monkeypatch.setattr(smoke, "REPO_ROOT", temp_root)
    monkeypatch.setattr(smoke, "force_rmtree", lambda path: False)

    try:
        failures = smoke.cleanup_legacy_repo_smoke_dirs()

        assert failures == [str(stale)]
        assert stale.exists()
    finally:
        cleanup_temp_root(temp_root)
