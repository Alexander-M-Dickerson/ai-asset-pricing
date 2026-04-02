"""Coverage for external canonical local-state resolution."""

from pathlib import Path
import shutil
import uuid

import pytest

from tools.local_state import canonical_directories, local_state_records, synced_storage_hint


def make_local_temp_root() -> Path:
    root = Path(".tmp-local-state-tests") / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    return root


def test_canonical_directories_windows():
    env = {
        "USERPROFILE": r"C:\Users\alice",
        "APPDATA": r"C:\Users\alice\AppData\Roaming",
        "LOCALAPPDATA": r"C:\Users\alice\AppData\Local",
    }
    result = canonical_directories(env=env, system_name="Windows")
    assert result["config_dir"] == Path(r"C:\Users\alice\AppData\Roaming") / "ai-asset-pricing"
    assert result["state_dir"] == Path(r"C:\Users\alice\AppData\Local") / "ai-asset-pricing"


def test_canonical_directories_macos():
    env = {
        "HOME": "/Users/alice",
    }
    result = canonical_directories(env=env, system_name="Darwin")
    base = Path("/Users/alice/Library/Application Support/ai-asset-pricing")
    assert result["config_dir"] == base / "config"
    assert result["state_dir"] == base / "state"


def test_local_state_prefers_canonical_over_compat(monkeypatch):
    temp_path = make_local_temp_root()
    try:
        repo_root = temp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".claude").mkdir()
        compat_local_env = repo_root / "LOCAL_ENV.md"
        compat_local_env.write_text("compat", encoding="utf-8")

        state_dir = temp_path / "user-state"
        state_dir.mkdir()
        canonical_local_env = state_dir / "local_env.md"
        canonical_local_env.write_text("canonical", encoding="utf-8")

        monkeypatch.setenv("AI_ASSET_PRICING_STATE_DIR", str(state_dir))
        records = local_state_records(repo_root)
        local_env = records["files"]["local_env"]
        assert local_env["active_source"] == "canonical"
        assert local_env["active_path"] == str(canonical_local_env)
        assert local_env["compat_path"] == str(compat_local_env)
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


def test_two_users_same_repo_get_distinct_canonical_paths():
    temp_path = make_local_temp_root()
    try:
        repo_root = temp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".claude").mkdir()

        records_a = local_state_records(
            repo_root,
            env={"AI_ASSET_PRICING_STATE_DIR": str(temp_path / "alice-state")},
        )
        records_b = local_state_records(
            repo_root,
            env={"AI_ASSET_PRICING_STATE_DIR": str(temp_path / "bob-state")},
        )

        assert records_a["files"]["local_env"]["canonical_path"] != records_b["files"]["local_env"]["canonical_path"]
        assert records_a["files"]["local_env"]["compat_path"] == records_b["files"]["local_env"]["compat_path"]
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


def test_synced_storage_hint_detects_onedrive():
    hint = synced_storage_hint(Path(r"C:\Users\alice\OneDrive\Documents\repo"))
    assert hint == {"kind": "synced_folder_candidate", "provider": "OneDrive"}


# --- 7a: Platform-parametrized cross-user isolation ---

@pytest.mark.parametrize("system_name,env_a,env_b", [
    (
        "Windows",
        {
            "USERPROFILE": r"C:\Users\alice",
            "APPDATA": r"C:\Users\alice\AppData\Roaming",
            "LOCALAPPDATA": r"C:\Users\alice\AppData\Local",
        },
        {
            "USERPROFILE": r"C:\Users\bob",
            "APPDATA": r"C:\Users\bob\AppData\Roaming",
            "LOCALAPPDATA": r"C:\Users\bob\AppData\Local",
        },
    ),
    (
        "Darwin",
        {"HOME": "/Users/alice"},
        {"HOME": "/Users/bob"},
    ),
    (
        "Linux",
        {"HOME": "/home/alice"},
        {"HOME": "/home/bob"},
    ),
])
def test_cross_user_canonical_paths_differ_per_platform(system_name, env_a, env_b):
    """Two different users on the same platform must get distinct canonical paths."""
    dirs_a = canonical_directories(env=env_a, system_name=system_name)
    dirs_b = canonical_directories(env=env_b, system_name=system_name)
    assert dirs_a["state_dir"] != dirs_b["state_dir"]
    assert dirs_a["config_dir"] != dirs_b["config_dir"]


# --- 7b: No-state-in-repo test ---

@pytest.mark.parametrize("system_name,env", [
    ("Windows", {
        "USERPROFILE": r"C:\Users\testuser",
        "APPDATA": r"C:\Users\testuser\AppData\Roaming",
        "LOCALAPPDATA": r"C:\Users\testuser\AppData\Local",
    }),
    ("Darwin", {"HOME": "/Users/testuser"}),
    ("Linux", {"HOME": "/home/testuser"}),
])
def test_canonical_paths_never_inside_repo(system_name, env):
    """Canonical state dirs must not be inside the repo root."""
    from tools.local_state import repo_root
    root = repo_root()
    dirs = canonical_directories(env=env, system_name=system_name)
    for key in ("config_dir", "state_dir"):
        path = dirs[key]
        try:
            path.relative_to(root)
            pytest.fail(f"Canonical {key}={path} is inside repo root {root}")
        except ValueError:
            pass  # Expected: path is outside repo


# --- 7c: Synced-folder detection edge cases ---

@pytest.mark.parametrize("path_str,expected_kind", [
    (r"C:\Users\alice\OneDrive\Documents\repo", "synced_folder_candidate"),
    (r"C:\Users\alice\Dropbox\repo", "synced_folder_candidate"),
    ("/Users/alice/Google Drive/repo", "synced_folder_candidate"),
    ("/Users/alice/iCloud Drive/repo", "synced_folder_candidate"),
    (r"C:\Users\alice\Documents\repo", "local_or_unknown"),
    ("/home/alice/projects/repo", "local_or_unknown"),
])
def test_synced_storage_hint_coverage(path_str, expected_kind):
    hint = synced_storage_hint(Path(path_str))
    assert hint["kind"] == expected_kind
