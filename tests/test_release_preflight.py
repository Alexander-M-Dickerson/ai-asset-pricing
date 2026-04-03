"""Coverage for release-preflight cleanup and artifact reporting."""

from __future__ import annotations

from tools import bootstrap
from tools import release_preflight as preflight


def test_cleanup_generated_repo_artifacts_removes_repo_temp_roots(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "tests" / "__pycache__").mkdir(parents=True)
    (repo_root / "tests" / "__pycache__" / "test_mod.pyc").write_bytes(b"bytecode")
    (repo_root / ".tmp-local-state-tests" / "session").mkdir(parents=True)
    (repo_root / ".test-tmp-onboarding-smoke" / "session").mkdir(parents=True)
    (repo_root / ".tmp-pytest-current" / "case").mkdir(parents=True)
    (repo_root / "build_check_root" / "cache").mkdir(parents=True)
    (repo_root / ".venv" / "Lib" / "site-packages").mkdir(parents=True)
    (repo_root / ".venv" / "Lib" / "site-packages" / "kept.pyd").write_bytes(b"binary")

    removed = bootstrap.cleanup_generated_repo_artifacts(repo_root)

    assert "tests/__pycache__" in removed
    assert ".tmp-local-state-tests" in removed
    assert ".test-tmp-onboarding-smoke" in removed
    assert ".tmp-pytest-current" in removed
    assert "build_check_root" in removed
    assert not (repo_root / "tests" / "__pycache__").exists()
    assert not (repo_root / ".tmp-local-state-tests").exists()
    assert not (repo_root / ".test-tmp-onboarding-smoke").exists()
    assert not (repo_root / ".tmp-pytest-current").exists()
    assert not (repo_root / "build_check_root").exists()
    assert (repo_root / ".venv").exists()


def test_collect_findings_ignores_repo_root_venv(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    (root / ".venv" / "Lib" / "site-packages").mkdir(parents=True)
    (root / ".venv" / "Lib" / "site-packages" / "nested.pyd").write_bytes(b"binary")

    monkeypatch.setattr(preflight, "REQUIRED_FILES", ())
    monkeypatch.setattr(preflight, "REQUIRED_BOOTSTRAP_SNIPPETS", {})
    monkeypatch.setattr(preflight, "REQUIRED_GITIGNORE_ENTRIES", ())
    monkeypatch.setattr(preflight, "BOOTSTRAP_LOCAL_PATHS", ())
    monkeypatch.setattr(preflight, "REQUIRED_GIT_TRACKED_PATHS", ())
    monkeypatch.setattr(preflight, "SHARED_TEXT_FILES", ())
    monkeypatch.setattr(preflight, "cleanup_generated_repo_artifacts", lambda _: [])
    monkeypatch.setattr(preflight, "run_onboarding_smoke", lambda _: preflight.Finding("PASS", "smoke ok"))
    monkeypatch.setattr(preflight, "run_pybondlab_smoke", lambda _: preflight.Finding("PASS", "pybondlab ok"))
    monkeypatch.setattr(preflight, "has_git_metadata", lambda _: False)

    findings = preflight.collect_findings(root)
    fail_messages = [finding.message for finding in findings if finding.level == "FAIL"]

    assert fail_messages == []


def test_collect_findings_reports_auto_cleaned_artifacts(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()

    cleanup_calls = iter([
        ["tests/__pycache__", ".tmp-pytest-current"],
        ["tests/__pycache__"],
    ])

    monkeypatch.setattr(preflight, "REQUIRED_FILES", ())
    monkeypatch.setattr(preflight, "REQUIRED_BOOTSTRAP_SNIPPETS", {})
    monkeypatch.setattr(preflight, "REQUIRED_GITIGNORE_ENTRIES", ())
    monkeypatch.setattr(preflight, "BOOTSTRAP_LOCAL_PATHS", ())
    monkeypatch.setattr(preflight, "REQUIRED_GIT_TRACKED_PATHS", ())
    monkeypatch.setattr(preflight, "SHARED_TEXT_FILES", ())
    monkeypatch.setattr(preflight, "cleanup_generated_repo_artifacts", lambda _: next(cleanup_calls))
    monkeypatch.setattr(preflight, "run_onboarding_smoke", lambda _: preflight.Finding("PASS", "smoke ok"))
    monkeypatch.setattr(preflight, "run_pybondlab_smoke", lambda _: preflight.Finding("PASS", "pybondlab ok"))
    monkeypatch.setattr(preflight, "has_git_metadata", lambda _: False)

    findings = preflight.collect_findings(root)
    info_messages = [finding.message for finding in findings if finding.level == "INFO"]

    assert "Auto-cleaned generated artifacts: tests/__pycache__, .tmp-pytest-current" in info_messages
