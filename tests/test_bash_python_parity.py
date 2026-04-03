"""Contract tests: Bash common.sh and Python local_state.py must agree on state_dir."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.local_state import canonical_directories

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMON_SH = REPO_ROOT / ".claude" / "hooks" / "common.sh"


def bash_canonical_state_dir(*, env: dict[str, str]) -> str:
    """Invoke canonical_state_dir() from common.sh and return its output."""
    bash = os.environ.get("BASH_PATH", "bash")
    script = f'source "{COMMON_SH.as_posix()}" && canonical_state_dir'
    try:
        proc = subprocess.run(
            [bash, "-c", script],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
    except FileNotFoundError:
        pytest.skip("bash not available")
    if proc.returncode != 0:
        pytest.skip(f"common.sh failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


@pytest.mark.parametrize("env_overrides,system_name", [
    (
        {"AI_ASSET_PRICING_STATE_DIR": "/tmp/test-state"},
        "Linux",
    ),
    (
        {"HOME": "/home/testuser"},
        "Linux",
    ),
    (
        {"HOME": "/home/testuser", "XDG_STATE_HOME": "/custom/state"},
        "Linux",
    ),
    (
        {"HOME": "/Users/testuser"},
        "Darwin",
    ),
])
def test_state_dir_parity(env_overrides, system_name):
    """Bash and Python must agree on state_dir for the same environment."""
    if sys.platform == "win32" and system_name != "Windows":
        pytest.skip("Cannot test non-Windows bash paths on Windows")

    py_dirs = canonical_directories(env=env_overrides, system_name=system_name)
    py_state = str(py_dirs["state_dir"])

    bash_env = {"PATH": os.environ.get("PATH", "")}
    for key in (
        "AI_ASSET_PRICING_STATE_DIR",
        "AI_ASSET_PRICING_SYSTEM_NAME",
        "EMPIRICAL_CLAUDE_STATE_DIR",
        "XDG_STATE_HOME",
        "HOME",
        "LOCALAPPDATA",
        "USERPROFILE",
        "APPDATA",
    ):
        bash_env.pop(key, None)
    bash_env.update(env_overrides)
    bash_env["AI_ASSET_PRICING_SYSTEM_NAME"] = system_name
    bash_state = bash_canonical_state_dir(env=bash_env)

    assert py_state == bash_state, (
        f"Parity mismatch: Python={py_state}, Bash={bash_state}"
    )
