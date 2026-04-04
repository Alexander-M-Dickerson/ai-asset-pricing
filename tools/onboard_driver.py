#!/usr/bin/env python3
"""Agent-facing onboarding driver.

Once a usable Python exists, this script owns the shared onboarding flow:
run bootstrap audit, optionally prompt for WRDS details, execute auto-run plan
steps in the current shell, and report the final readiness state.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WRDS_PASSWORD_ENV = "AI_ASSET_PRICING_WRDS_PASSWORD"
WRDS_CHOICES = ("auto", "yes", "no")
SHELL_CHOICES = ("auto", "powershell", "bash")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell", choices=SHELL_CHOICES, default="auto")
    parser.add_argument("--wrds", choices=WRDS_CHOICES, default="auto")
    parser.add_argument("--wrds-username", default="")
    parser.add_argument("--skip-wrds-test", action="store_true")
    parser.add_argument("--password-env", default=DEFAULT_WRDS_PASSWORD_ENV)
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def is_interactive(args: argparse.Namespace) -> bool:
    return sys.stdin.isatty() and not args.non_interactive


def chosen_shell(value: str) -> str:
    if value != "auto":
        return value
    return "powershell" if os.name == "nt" else "bash"


def prompt_yes_no(prompt: str, *, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{prompt} {suffix} ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def resolve_wrds_choice(args: argparse.Namespace) -> str:
    if args.wrds != "auto":
        return args.wrds
    if not is_interactive(args):
        return "no"
    return "yes" if prompt_yes_no("Do you have a WRDS account and want it configured now?") else "no"


def run_bootstrap_audit(
    *,
    wrds: str,
    wrds_username: str,
    skip_wrds_test: bool,
) -> dict[str, Any]:
    cmd = [sys.executable, "tools/bootstrap.py", "audit", "--json", "--wrds", wrds]
    if skip_wrds_test:
        cmd.append("--skip-wrds-test")
    if wrds_username:
        cmd.extend(["--wrds-username", wrds_username])
    proc = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=300,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "bootstrap audit failed").strip()
        raise RuntimeError(detail)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid bootstrap audit JSON: {exc}") from exc


def shell_command_for_step(step: dict[str, Any], shell_name: str) -> list[str]:
    if shell_name == "powershell":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", step["powershell"]]
    return ["bash", "-lc", step["bash"]]


def maybe_prompt_wrds_username(args: argparse.Namespace, wrds: str) -> str:
    username = args.wrds_username.strip()
    if wrds != "yes" or username or not is_interactive(args):
        return username
    return input("WRDS username: ").strip()


def maybe_prompt_wrds_password(
    args: argparse.Namespace,
    audit_payload: dict[str, Any],
    env: dict[str, str],
) -> None:
    if audit_payload.get("wrds_mode", {}).get("effective") != "yes":
        return
    if env.get(args.password_env):
        return
    step_ids = {step.get("id") for step in audit_payload.get("bootstrap_plan", {}).get("steps", [])}
    if "create_wrds_files" not in step_ids:
        return
    if not is_interactive(args):
        return
    env[args.password_env] = getpass.getpass("WRDS password: ")


def execute_plan_steps(
    *,
    audit_payload: dict[str, Any],
    shell_name: str,
    env: dict[str, str],
    dry_run: bool,
    verbose: bool = True,
) -> tuple[list[dict[str, Any]], bool]:
    results: list[dict[str, Any]] = []
    blocking_failed = False

    for step in audit_payload.get("bootstrap_plan", {}).get("steps", []):
        if not step.get("auto_run", True):
            continue

        result = {
            "id": step["id"],
            "phase": step.get("phase", ""),
            "blocking": bool(step.get("blocking")),
            "command": step[shell_name],
        }

        if dry_run:
            result["status"] = "DRY_RUN"
            results.append(result)
            continue

        if verbose:
            label = step.get("label", step["id"])
            print(f"Running: {label}...", file=sys.stderr)

        proc = subprocess.run(
            shell_command_for_step(step, shell_name),
            check=False,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
            timeout=3600,
        )
        result["status"] = "OK" if proc.returncode == 0 else "FAIL"
        result["returncode"] = proc.returncode
        result["stdout_tail"] = (proc.stdout or "").strip().splitlines()[-10:]
        result["stderr_tail"] = (proc.stderr or "").strip().splitlines()[-10:]
        results.append(result)

        if proc.returncode != 0 and step.get("blocking"):
            blocking_failed = True
            break

    return results, blocking_failed


def print_human_summary(payload: dict[str, Any], executed_steps: list[dict[str, Any]]) -> None:
    print(f"Onboarding {'succeeded' if payload['onboarding_success'] else 'is still blocked'}.")
    for phase_name in ("base_repo", "wrds", "writing", "r"):
        phase = payload["phase_status"][phase_name]
        print(f"  {phase_name}: {phase['status']} - {phase['detail']}")
    if executed_steps:
        print("Executed plan steps:")
        for step in executed_steps:
            print(f"  {step['id']}: {step['status']}")
            if step.get("status") == "FAIL":
                for line in step.get("stderr_tail", []):
                    print(f"    {line}")
    actions = payload.get("actions", [])
    if actions:
        print("Next steps:")
        for action in actions:
            print(f"  - {action}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    shell_name = chosen_shell(args.shell)
    wrds = resolve_wrds_choice(args)
    wrds_username = maybe_prompt_wrds_username(args, wrds)

    audit_payload = run_bootstrap_audit(
        wrds=wrds,
        wrds_username=wrds_username,
        skip_wrds_test=args.skip_wrds_test,
    )
    env = dict(os.environ)
    maybe_prompt_wrds_password(args, audit_payload, env)

    executed_steps, blocking_failed = execute_plan_steps(
        audit_payload=audit_payload,
        shell_name=shell_name,
        env=env,
        dry_run=args.dry_run,
    )

    final_payload = audit_payload
    if not args.dry_run:
        final_payload = run_bootstrap_audit(
            wrds=wrds,
            wrds_username=wrds_username,
            skip_wrds_test=args.skip_wrds_test,
        )

    output = {
        "shell": shell_name,
        "wrds": wrds,
        "wrds_username": wrds_username,
        "executed_steps": executed_steps,
        "final_audit": final_payload,
    }

    if args.json:
        json.dump(output, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print_human_summary(final_payload, executed_steps)

    if args.dry_run:
        return 0
    if blocking_failed:
        return 1
    return 0 if final_payload.get("onboarding_success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
