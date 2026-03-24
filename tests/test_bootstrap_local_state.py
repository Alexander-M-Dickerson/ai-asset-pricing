"""Bootstrap regression coverage for the local-state refactor."""

from pathlib import Path
import shutil
import uuid
import warnings

from tools import bootstrap


def test_wrds_smoke_dates_are_fixed():
    assert bootstrap.WRDS_SMOKE_COUNT_START == "2022-01-01"
    assert bootstrap.WRDS_SMOKE_COUNT_END == "2023-01-01"
    assert bootstrap.WRDS_SMOKE_SAMPLE_START == "2022-12-01"


def test_build_actions_warn_for_synced_folder_and_missing_bash(monkeypatch):
    temp_root = Path(".test-tmp-bootstrap-actions") / uuid.uuid4().hex
    temp_root.mkdir(parents=True, exist_ok=False)
    try:
        service_path = temp_root / "pg_service.conf"
        service_path.write_text("[wrds]\n", encoding="utf-8")
        monkeypatch.setattr(bootstrap, "preferred_pg_service_path", lambda probe: service_path)

        report = {
            "probe": {
                "local_state": {
                    "storage_hint": {"kind": "synced_folder_candidate", "provider": "OneDrive"},
                },
                "tools": {
                    "uv": {"path": ""},
                    "bash": {"path": ""},
                    "psql": {"path": "psql"},
                },
                "wrds": {
                    "pgpass": "OK",
                    "ssh_config": "OK",
                    "ssh_key": "OK",
                },
            },
            "bootstrap_plan": {
                "steps": [{"id": "install_fintools"}],
            },
            "compatibility_files": [
                {"status": "MISSING"},
                {"status": "MISSING"},
                {"status": "MISSING"},
            ],
            "wrds_test": {"status": "SKIPPED"},
        }

        actions = bootstrap.build_actions(report)

        assert any("synced folder" in action for action in actions)
        assert any("Bash on PATH" in action for action in actions)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


# --- 9a: build_actions emits FAIL when synced + compat shims present ---

def test_build_actions_fail_when_synced_with_compat_shims(monkeypatch):
    temp_root = Path(".test-tmp-bootstrap-synced") / uuid.uuid4().hex
    temp_root.mkdir(parents=True, exist_ok=False)
    try:
        service_path = temp_root / "pg_service.conf"
        service_path.write_text("[wrds]\n", encoding="utf-8")
        monkeypatch.setattr(bootstrap, "preferred_pg_service_path", lambda probe: service_path)

        report = {
            "probe": {
                "local_state": {
                    "storage_hint": {"kind": "synced_folder_candidate", "provider": "OneDrive"},
                },
                "tools": {"uv": {"path": ""}, "bash": {"path": "/bin/bash"}, "psql": {"path": ""}},
                "wrds": {"pgpass": "OK", "ssh_config": "OK", "ssh_key": "OK"},
            },
            "bootstrap_plan": {"steps": []},
            "compatibility_files": [
                {"status": "OK", "path": "LOCAL_ENV.md"},
                {"status": "MISSING", "path": "CLAUDE.local.md"},
                {"status": "MISSING", "path": ".claude/settings.local.json"},
            ],
            "wrds_test": {"status": "SKIPPED"},
        }
        actions = bootstrap.build_actions(report)
        fail_actions = [a for a in actions if "FAIL" in a]
        assert len(fail_actions) >= 1
        assert any("compat" in a.lower() or "Remove" in a for a in fail_actions)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


# --- 9b: build_bootstrap_plan emits cleanup step ---

def test_build_bootstrap_plan_emits_cleanup_for_synced_compat_shims():
    report = {
        "probe": {
            "python": {"path": "/usr/bin/python3"},
            "local_state": {
                "storage_hint": {"kind": "synced_folder_candidate", "provider": "Dropbox"},
                "files": {
                    "local_env": {"canonical_path": "/tmp/state/local_env.md", "canonical_status": "OK"},
                    "claude_local": {"canonical_path": "/tmp/state/claude.local.md", "canonical_status": "OK"},
                    "settings_local": {"canonical_path": "/tmp/state/settings.local.json", "canonical_status": "OK"},
                },
            },
            "packages": {},
            "tools": {"uv": {"path": ""}},
        },
        "repo_packages": [],
        "local_files": [{"path": "/tmp/state/local_env.md", "status": "OK"}],
        "compatibility_files": [
            {"status": "OK", "path": "LOCAL_ENV.md"},
            {"status": "OK", "path": "CLAUDE.local.md"},
            {"status": "MISSING", "path": ".claude/settings.local.json"},
        ],
    }
    plan = bootstrap.build_bootstrap_plan(report)
    cleanup_steps = [s for s in plan["steps"] if s["id"] == "remove_synced_compat_shims"]
    assert len(cleanup_steps) == 1
    assert "Dropbox" in cleanup_steps[0]["reason"]


# --- 9c: write_outputs refuses compat shims in synced folders ---

def test_write_outputs_refuses_compat_shims_in_synced_folder(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setenv("EMPIRICAL_CLAUDE_STATE_DIR", str(state_dir))

    report = _make_minimal_report(
        state_dir=state_dir,
        storage_hint={"kind": "synced_folder_candidate", "provider": "OneDrive"},
    )
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        bootstrap.write_outputs(report, write_compat_shims=True)
        assert any("Refusing" in str(warning.message) for warning in w)
    # Canonical files should be written
    assert (state_dir / "local_env.md").exists()
    # Repo-root compat shims should NOT be written
    assert not (bootstrap.REPO_ROOT / "LOCAL_ENV.md").exists()


def _make_minimal_report(*, state_dir: Path, storage_hint: dict) -> dict:
    """Build a minimal report dict for write_outputs() testing."""
    return {
        "generated_at": "2026-03-24T00:00:00+00:00",
        "probe": {
            "python": {"path": "/usr/bin/python3", "version": "3.11.0"},
            "platform": {
                "system": "Linux", "release": "6.0", "machine": "x86_64",
                "home": "/home/test", "shell": "bash",
            },
            "local_state": {
                "config_dir": str(state_dir),
                "state_dir": str(state_dir),
                "storage_hint": storage_hint,
                "files": {
                    "local_env": {
                        "canonical_path": str(state_dir / "local_env.md"),
                        "canonical_status": "MISSING",
                        "compat_path": str(bootstrap.REPO_ROOT / "LOCAL_ENV.md"),
                        "compat_status": "MISSING",
                        "active_path": str(state_dir / "local_env.md"),
                        "active_source": "missing",
                    },
                    "claude_local": {
                        "canonical_path": str(state_dir / "claude.local.md"),
                        "canonical_status": "MISSING",
                        "compat_path": str(bootstrap.REPO_ROOT / "CLAUDE.local.md"),
                        "compat_status": "MISSING",
                        "active_path": str(state_dir / "claude.local.md"),
                        "active_source": "missing",
                    },
                    "settings_local": {
                        "canonical_path": str(state_dir / "settings.local.json"),
                        "canonical_status": "MISSING",
                        "compat_path": str(bootstrap.REPO_ROOT / ".claude" / "settings.local.json"),
                        "compat_status": "MISSING",
                        "active_path": str(state_dir / "settings.local.json"),
                        "active_source": "missing",
                    },
                },
            },
            "tools": {
                "uv": {"path": "", "version": ""},
                "bash": {"path": "/bin/bash", "version": "5.0"},
                "psql": {"path": "", "version": ""},
                "pdflatex": {"path": "", "version": ""},
                "r": {"path": "", "version": ""},
                "git": {"path": "/usr/bin/git", "version": "2.40"},
                "gh": {"path": "", "version": ""},
                "ssh": {"path": "/usr/bin/ssh", "version": ""},
            },
            "packages": {
                "pandas": "2.0.0", "psycopg2": "2.9.0", "pyarrow": "14.0.0",
                "numpy": "1.26.0", "matplotlib": "3.8.0", "statsmodels": "0.14.0",
            },
            "wrds": {
                "wrds_user": "",
                "pg_service_conf": "MISSING",
                "pgpass": "MISSING",
                "ssh_config": "MISSING",
                "ssh_key": "MISSING",
            },
        },
        "preferred_pg_service_file": "/home/test/.pg_service.conf",
        "repo_packages": [],
        "local_files": [],
        "compatibility_files": [],
        "commands": {
            "powershell": {"python": "python3", "pip": "python3 -m pip", "psql": "psql not installed"},
            "bash": {"python": "python3", "pip": "python3 -m pip", "psql": "psql not installed"},
        },
        "bootstrap_plan": {"steps": [], "required_ids": []},
        "synced_folder_status": "OK",
        "summary": [],
        "actions": [],
        "wrds_test": {"status": "SKIPPED"},
    }


# --- 9d: _synced_folder_audit_status tests ---

def test_synced_folder_audit_status_ok_when_no_compat_shims():
    report = {
        "probe": {
            "local_state": {
                "storage_hint": {"kind": "synced_folder_candidate", "provider": "OneDrive"},
            },
        },
        "compatibility_files": [
            {"status": "MISSING"}, {"status": "MISSING"}, {"status": "MISSING"},
        ],
    }
    assert bootstrap._synced_folder_audit_status(report) == "OK"


def test_synced_folder_audit_status_fail_when_compat_shims_exist():
    report = {
        "probe": {
            "local_state": {
                "storage_hint": {"kind": "synced_folder_candidate", "provider": "OneDrive"},
            },
        },
        "compatibility_files": [
            {"status": "OK"}, {"status": "MISSING"}, {"status": "MISSING"},
        ],
    }
    assert bootstrap._synced_folder_audit_status(report) == "FAIL"


def test_synced_folder_audit_status_not_synced():
    report = {
        "probe": {
            "local_state": {
                "storage_hint": {"kind": "local_or_unknown", "provider": ""},
            },
        },
        "compatibility_files": [
            {"status": "OK"}, {"status": "MISSING"}, {"status": "MISSING"},
        ],
    }
    assert bootstrap._synced_folder_audit_status(report) == "NOT_SYNCED"
