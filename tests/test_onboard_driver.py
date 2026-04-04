"""Regression coverage for the Python onboarding driver."""

from __future__ import annotations

from tools import onboard_driver as driver


def test_resolve_wrds_choice_defaults_to_no_when_noninteractive(monkeypatch):
    args = driver.parse_args(["--non-interactive"])
    monkeypatch.setattr(driver.sys.stdin, "isatty", lambda: False)

    assert driver.resolve_wrds_choice(args) == "no"


def test_execute_plan_steps_dry_run_preserves_step_metadata():
    payload = {
        "bootstrap_plan": {
            "steps": [
                {
                    "id": "install_bash",
                    "phase": "base",
                    "blocking": True,
                    "auto_run": True,
                    "powershell": "Write-Host hi",
                    "bash": "echo hi",
                },
                {
                    "id": "install_r",
                    "phase": "r",
                    "blocking": False,
                    "auto_run": True,
                    "powershell": "Write-Host r",
                    "bash": "echo r",
                },
            ]
        }
    }

    results, blocking_failed = driver.execute_plan_steps(
        audit_payload=payload,
        shell_name="bash",
        env={},
        dry_run=True,
    )

    assert blocking_failed is False
    assert [item["status"] for item in results] == ["DRY_RUN", "DRY_RUN"]
    assert results[0]["command"] == "echo hi"


def test_chosen_shell_returns_powershell_on_nt(monkeypatch):
    monkeypatch.setattr(driver.os, "name", "nt")
    assert driver.chosen_shell("auto") == "powershell"


def test_chosen_shell_returns_bash_on_posix(monkeypatch):
    monkeypatch.setattr(driver.os, "name", "posix")
    assert driver.chosen_shell("auto") == "bash"


def test_chosen_shell_respects_explicit_value():
    assert driver.chosen_shell("bash") == "bash"
    assert driver.chosen_shell("powershell") == "powershell"


def test_shell_command_for_step_dispatches_correctly():
    step = {"powershell": "Write-Host hi", "bash": "echo hi"}
    cmd = driver.shell_command_for_step(step, "bash")
    assert cmd == ["bash", "-lc", "echo hi"]
    cmd = driver.shell_command_for_step(step, "powershell")
    assert "Write-Host hi" in cmd


def test_resolve_wrds_choice_returns_explicit_yes():
    args = driver.parse_args(["--wrds", "yes"])
    assert driver.resolve_wrds_choice(args) == "yes"


def test_resolve_wrds_choice_returns_explicit_no():
    args = driver.parse_args(["--wrds", "no"])
    assert driver.resolve_wrds_choice(args) == "no"


def test_execute_plan_steps_halts_on_blocking_failure(monkeypatch):
    """When a blocking step fails, execution should stop and report blocking_failed."""
    call_count = 0

    class FakeResult:
        returncode = 1
        stdout = ""
        stderr = "install failed"

    def fake_run(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return FakeResult()

    monkeypatch.setattr(driver.subprocess, "run", fake_run)

    payload = {
        "bootstrap_plan": {
            "steps": [
                {
                    "id": "step_a",
                    "phase": "base",
                    "blocking": True,
                    "auto_run": True,
                    "powershell": "fail",
                    "bash": "fail",
                },
                {
                    "id": "step_b",
                    "phase": "base",
                    "blocking": False,
                    "auto_run": True,
                    "powershell": "ok",
                    "bash": "ok",
                },
            ]
        }
    }

    results, blocking_failed = driver.execute_plan_steps(
        audit_payload=payload,
        shell_name="bash",
        env={},
        dry_run=False,
        verbose=False,
    )

    assert blocking_failed is True
    assert len(results) == 1
    assert results[0]["status"] == "FAIL"
    assert call_count == 1
