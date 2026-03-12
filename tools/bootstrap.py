#!/usr/bin/env python3
"""Shared repo-local onboarding bootstrap engine."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from onboard_probe import PACKAGE_NAMES, collect_probe


REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_ENV_PATH = REPO_ROOT / "LOCAL_ENV.md"
CLAUDE_LOCAL_PATH = REPO_ROOT / "CLAUDE.local.md"
SETTINGS_LOCAL_PATH = REPO_ROOT / ".claude" / "settings.local.json"
PYBONDLAB_ROOT = REPO_ROOT / "packages" / "PyBondLab"
IGNORED_CLEANUP_PARTS = {".git", "_release_check"}

PACKAGE_INSTALL_SPECS = {
    "pandas": "pandas",
    "psycopg2": "psycopg2-binary",
    "pyarrow": "pyarrow",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "statsmodels": "statsmodels",
}


@dataclass(frozen=True)
class RepoPackage:
    label: str
    distribution: str
    import_name: str
    expected_root: Path
    install_target: str
    install_cwd: Path


REPO_PACKAGES = (
    RepoPackage(
        label="fintools",
        distribution="fintools",
        import_name="fintools",
        expected_root=REPO_ROOT / "fintools",
        install_target=".",
        install_cwd=REPO_ROOT,
    ),
    RepoPackage(
        label="PyBondLab",
        distribution="PyBondLab",
        import_name="PyBondLab",
        expected_root=PYBONDLAB_ROOT / "PyBondLab",
        install_target=".[performance]",
        install_cwd=PYBONDLAB_ROOT,
    ),
)


def run_command(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 15,
) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            env=env,
        )
    except Exception as exc:
        return 1, "", str(exc)
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def install_subprocess_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def path_is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def preferred_pg_service_path(probe: dict[str, Any]) -> Path:
    home_path = Path(probe["platform"]["home"]) / ".pg_service.conf"
    if home_path.exists():
        return home_path

    appdata = probe["platform"].get("appdata") or ""
    windows = probe.get("windows", {})
    if appdata and windows.get("appdata_pg_service") == "OK":
        return Path(appdata) / "postgresql" / "pg_service.conf"

    return home_path


def display_bash_path(path: str) -> str:
    if os.name != "nt":
        return path

    normalized = path.replace("\\", "/")
    match = re.match(r"^([A-Za-z]):/(.*)$", normalized)
    if not match:
        return normalized
    drive = match.group(1).lower()
    rest = match.group(2)
    return f"/{drive}/{rest}"


def powershell_quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def shell_quote(text: str) -> str:
    return shlex.quote(text)


def format_powershell_command(parts: list[str]) -> str:
    return "& " + " ".join(powershell_quote(part) for part in parts)


def format_shell_command(parts: list[str]) -> str:
    return " ".join(shell_quote(part) for part in parts)


def powershell_in_directory(cwd: Path, parts: list[str], *, disable_bytecode: bool = False) -> str:
    inner = format_powershell_command(parts)
    preamble = ""
    cleanup = ""
    if disable_bytecode:
        preamble = (
            "$__prevDontWriteBytecode = "
            "[System.Environment]::GetEnvironmentVariable('PYTHONDONTWRITEBYTECODE', 'Process'); "
            "$env:PYTHONDONTWRITEBYTECODE = '1'; "
        )
        cleanup = (
            "if ($null -eq $__prevDontWriteBytecode) { "
            "Remove-Item Env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue "
            "} else { $env:PYTHONDONTWRITEBYTECODE = $__prevDontWriteBytecode }; "
        )
    return (
        f"Push-Location {powershell_quote(str(cwd))}; "
        f"{preamble}try {{ {inner} }} finally {{ {cleanup}Pop-Location }}"
    )


def bash_in_directory(cwd: Path, parts: list[str], *, disable_bytecode: bool = False) -> str:
    inner = format_shell_command(parts)
    cwd_text = shell_quote(display_bash_path(str(cwd)))
    prefix = "PYTHONDONTWRITEBYTECODE=1 " if disable_bytecode else ""
    return f"(cd {cwd_text} && {prefix}{inner})"


def python_module_probe(python_path: str, import_name: str, *, cwd: Path) -> dict[str, str]:
    code = """
import importlib
import json
import sys

result = {}
try:
    module = importlib.import_module(sys.argv[1])
except Exception as exc:
    result["status"] = "ERROR"
    result["detail"] = f"{type(exc).__name__}: {exc}"
else:
    result["status"] = "OK"
    result["origin"] = getattr(module, "__file__", "") or ""
    version = getattr(module, "__version__", "")
    if version is not None:
        result["version"] = str(version)
print(json.dumps(result))
""".strip()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONPATH", None)
    rc, stdout, stderr = run_command(
        [python_path, "-c", code, import_name],
        cwd=cwd,
        env=env,
        timeout=30,
    )
    if rc != 0:
        detail = stderr or stdout or "module probe failed"
        return {"status": "ERROR", "detail": detail}
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {"status": "ERROR", "detail": stdout or "invalid module probe output"}
    if not isinstance(payload, dict):
        return {"status": "ERROR", "detail": "invalid module probe payload"}
    return {key: str(value) for key, value in payload.items()}


def repo_package_status(probe: dict[str, Any]) -> list[dict[str, str]]:
    python_path = probe["python"]["path"]
    probe_cwd = Path(probe["platform"]["home"]) if probe["platform"].get("home") else REPO_ROOT.parent
    results: list[dict[str, str]] = []
    for package in REPO_PACKAGES:
        version = ""
        try:
            version = metadata.version(package.distribution)
        except metadata.PackageNotFoundError:
            version = ""

        module_probe = python_module_probe(python_path, package.import_name, cwd=probe_cwd)
        origin = module_probe.get("origin", "")
        detail = module_probe.get("detail", "")

        if module_probe.get("status") != "OK":
            status = "MISSING"
        elif origin and path_is_within(Path(origin), package.expected_root):
            status = "OK"
        else:
            status = "EXTERNAL"
            if not detail and origin:
                detail = f"loaded from {origin}"

        version = module_probe.get("version", "") or version
        results.append(
            {
                "label": package.label,
                "distribution": package.distribution,
                "import_name": package.import_name,
                "status": status,
                "version": version,
                "origin": origin,
                "expected_root": str(package.expected_root),
                "detail": detail,
            }
        )
    return results


def local_file_status() -> list[dict[str, str]]:
    return [
        {
            "path": "LOCAL_ENV.md",
            "status": "OK" if LOCAL_ENV_PATH.exists() else "MISSING",
        },
        {
            "path": "CLAUDE.local.md",
            "status": "OK" if CLAUDE_LOCAL_PATH.exists() else "MISSING",
        },
        {
            "path": ".claude/settings.local.json",
            "status": "OK" if SETTINGS_LOCAL_PATH.exists() else "MISSING",
        },
    ]


def validate_csv_sample(output: str) -> tuple[bool, str]:
    reader = csv.DictReader(io.StringIO(output))
    rows = list(reader)
    fieldnames = reader.fieldnames or []
    expected = {"date", "sprtrn"}
    if not rows:
        return False, "no rows returned"
    if not expected.issubset(fieldnames):
        missing = ", ".join(sorted(expected - set(fieldnames)))
        return False, f"missing expected columns: {missing}"
    return True, f"{len(rows)} rows, columns: {', '.join(fieldnames)}"


def run_wrds_checks(probe: dict[str, Any], *, skip: bool) -> dict[str, Any]:
    if skip:
        return {"status": "SKIPPED", "reason": "skipped by flag", "checks": []}

    psql_path = probe["tools"]["psql"]["path"]
    pg_service_path = preferred_pg_service_path(probe)
    missing_prereqs: list[str] = []

    if not psql_path:
        missing_prereqs.append("psql not found")
    if not pg_service_path.exists():
        missing_prereqs.append(f"{pg_service_path} missing")

    if missing_prereqs:
        return {
            "status": "SKIPPED",
            "reason": ", ".join(missing_prereqs),
            "checks": [],
        }

    env = os.environ.copy()
    env["PGSERVICEFILE"] = str(pg_service_path)

    checks: list[dict[str, str]] = []

    connection_cmd = [psql_path, "-X", "-w", "-At", "service=wrds", "-c", "SELECT 1;"]
    rc, stdout, stderr = run_command(connection_cmd, env=env, cwd=REPO_ROOT)
    connection_ok = rc == 0 and stdout == "1"
    checks.append(
        {
            "name": "connection_test",
            "status": "OK" if connection_ok else "FAIL",
            "detail": "SELECT 1 succeeded" if connection_ok else stderr or stdout or "connection failed",
        }
    )
    if not connection_ok:
        return {"status": "FAIL", "checks": checks}

    count_cmd = [
        psql_path,
        "-X",
        "-w",
        "-At",
        "service=wrds",
        "-c",
        f"SELECT COUNT(*) FROM crsp.dsi WHERE date >= '{datetime.now().year - 1}-01-01';",
    ]
    rc, stdout, stderr = run_command(count_cmd, env=env, cwd=REPO_ROOT)
    try:
        row_count = int(stdout)
        count_ok = rc == 0 and row_count >= 1
        detail = f"{row_count} rows visible in crsp.dsi since {datetime.now().year - 1}-01-01"
    except ValueError:
        count_ok = False
        detail = stderr or stdout or "COUNT query failed"
    checks.append(
        {
            "name": "crsp_count",
            "status": "OK" if count_ok else "FAIL",
            "detail": detail,
        }
    )
    if not count_ok:
        return {"status": "FAIL", "checks": checks}

    pipeline_cmd = [
        psql_path,
        "-X",
        "-w",
        "service=wrds",
        "-c",
        f"COPY (SELECT date, sprtrn FROM crsp.dsi WHERE date >= '{datetime.now().year - 1}-12-01' ORDER BY date LIMIT 5) "
        "TO STDOUT WITH CSV HEADER",
    ]
    rc, stdout, stderr = run_command(pipeline_cmd, env=env, cwd=REPO_ROOT)
    if rc == 0:
        pipeline_ok, detail = validate_csv_sample(stdout)
    else:
        pipeline_ok = False
        detail = stderr or stdout or "CSV sample query failed"
    checks.append(
        {
            "name": "pipeline_sample",
            "status": "OK" if pipeline_ok else "FAIL",
            "detail": detail,
        }
    )

    overall = "OK" if all(check["status"] == "OK" for check in checks) else "FAIL"
    return {"status": overall, "checks": checks}


def missing_python_modules(probe: dict[str, Any]) -> list[str]:
    return [name for name, version in probe["packages"].items() if version == "MISSING"]


def installable_repo_packages(report: dict[str, Any]) -> list[RepoPackage]:
    failing_labels = {item["label"] for item in report["repo_packages"] if item["status"] != "OK"}
    return [package for package in REPO_PACKAGES if package.label in failing_labels]


def repair_python_packages(report: dict[str, Any]) -> list[dict[str, str]]:
    probe = report["probe"]
    missing_modules = missing_python_modules(probe)
    if not missing_modules:
        return []

    specs = [PACKAGE_INSTALL_SPECS[name] for name in missing_modules]
    cmd = [probe["python"]["path"], "-m", "pip", "install", "--no-compile", *specs]
    rc, stdout, stderr = run_command(cmd, cwd=REPO_ROOT, env=install_subprocess_environment(), timeout=900)
    detail = stdout.splitlines()[-1] if rc == 0 and stdout else stderr or stdout or "pip install failed"
    return [
        {
            "name": "python_packages",
            "status": "OK" if rc == 0 else "FAIL",
            "detail": detail,
            "command": " ".join(shell_quote(part) for part in cmd),
        }
    ]


def repair_repo_packages(report: dict[str, Any]) -> list[dict[str, str]]:
    probe = report["probe"]
    operations: list[dict[str, str]] = []
    pip_env = install_subprocess_environment()
    for package in installable_repo_packages(report):
        cmd = [probe["python"]["path"], "-m", "pip", "install", "--no-compile", "-e", package.install_target]
        rc, stdout, stderr = run_command(cmd, cwd=package.install_cwd, env=pip_env, timeout=900)
        detail = stdout.splitlines()[-1] if rc == 0 and stdout else stderr or stdout or "editable install failed"
        operations.append(
            {
                "name": package.label,
                "status": "OK" if rc == 0 else "FAIL",
                "detail": detail,
                "command": " ".join(shell_quote(part) for part in cmd),
            }
        )
    return operations


def repair_environment(report: dict[str, Any]) -> list[dict[str, str]]:
    operations: list[dict[str, str]] = []
    operations.extend(repair_python_packages(report))
    operations.extend(repair_repo_packages(report))
    return operations


def power_shell_commands(probe: dict[str, Any]) -> dict[str, str]:
    python_path = probe["python"]["path"]
    pg_service_path = str(preferred_pg_service_path(probe))
    commands = {
        "python": f"& {powershell_quote(python_path)}",
        "pip": f"& {powershell_quote(python_path)} -m pip",
    }

    psql_path = probe["tools"]["psql"]["path"]
    if psql_path:
        commands["psql"] = (
            f"$env:PGSERVICEFILE = {powershell_quote(pg_service_path)}; "
            f"& {powershell_quote(psql_path)} service=wrds"
        )
    else:
        commands["psql"] = "psql not installed"
    return commands


def bash_commands(probe: dict[str, Any]) -> dict[str, str]:
    python_path = display_bash_path(probe["python"]["path"])
    pg_service_path = display_bash_path(str(preferred_pg_service_path(probe)))
    commands = {
        "python": shell_quote(python_path),
        "pip": f"{shell_quote(python_path)} -m pip",
    }

    psql_path = probe["tools"]["psql"]["path"]
    if psql_path:
        bash_psql = display_bash_path(psql_path)
        commands["psql"] = (
            f"PGSERVICEFILE={shell_quote(pg_service_path)} "
            f"{shell_quote(bash_psql)} service=wrds"
        )
    else:
        commands["psql"] = "psql not installed"
    return commands


def build_bootstrap_plan(report: dict[str, Any]) -> dict[str, Any]:
    probe = report["probe"]
    python_path = probe["python"]["path"]
    bash_python = display_bash_path(python_path)
    missing_modules = missing_python_modules(probe)
    missing_local_files = [item["path"] for item in report["local_files"] if item["status"] != "OK"]
    steps: list[dict[str, Any]] = []

    if missing_modules:
        specs = [PACKAGE_INSTALL_SPECS[name] for name in missing_modules]
        steps.append(
            {
                "id": "install_python_packages",
                "label": "Install missing Python packages",
                "required": True,
                "reason": f"Missing packages: {', '.join(missing_modules)}",
                "powershell": powershell_in_directory(
                    REPO_ROOT,
                    [python_path, "-m", "pip", "install", "--no-compile", *specs],
                    disable_bytecode=True,
                ),
                "bash": bash_in_directory(
                    REPO_ROOT,
                    [bash_python, "-m", "pip", "install", "--no-compile", *specs],
                    disable_bytecode=True,
                ),
            }
        )

    for package in installable_repo_packages(report):
        package_state = next(
            (item["status"] for item in report["repo_packages"] if item["label"] == package.label),
            "UNKNOWN",
        )
        steps.append(
            {
                "id": f"install_{package.label.lower()}",
                "label": f"Install repo package {package.label}",
                "required": True,
                "reason": f"{package.label} status is {package_state}",
                "powershell": powershell_in_directory(
                    package.install_cwd,
                    [python_path, "-m", "pip", "install", "--no-compile", "-e", package.install_target],
                    disable_bytecode=True,
                ),
                "bash": bash_in_directory(
                    package.install_cwd,
                    [bash_python, "-m", "pip", "install", "--no-compile", "-e", package.install_target],
                    disable_bytecode=True,
                ),
            }
        )

    needs_apply = bool(steps) or bool(missing_local_files)
    if needs_apply:
        apply_reason = (
            f"Missing local files: {', '.join(missing_local_files)}"
            if missing_local_files
            else "Refresh LOCAL_ENV.md and Claude compatibility outputs after setup changes"
        )
        steps.append(
            {
                "id": "apply_local_files",
                "label": "Write or refresh local onboarding files",
                "required": True,
                "reason": apply_reason,
                "powershell": powershell_in_directory(
                    REPO_ROOT,
                    [python_path, "tools/bootstrap.py", "apply"],
                ),
                "bash": bash_in_directory(
                    REPO_ROOT,
                    [bash_python, "tools/bootstrap.py", "apply"],
                ),
            }
        )
        steps.append(
            {
                "id": "rerun_audit",
                "label": "Re-run bootstrap audit",
                "required": True,
                "reason": "Verify that the clone is ready after the required setup steps.",
                "powershell": powershell_in_directory(
                    REPO_ROOT,
                    [python_path, "tools/bootstrap.py", "audit"],
                ),
                "bash": bash_in_directory(
                    REPO_ROOT,
                    [bash_python, "tools/bootstrap.py", "audit"],
                ),
            }
        )

    return {
        "steps": steps,
        "required_ids": [step["id"] for step in steps if step["required"]],
    }


def summary_rows(report: dict[str, Any]) -> list[tuple[str, str]]:
    probe = report["probe"]
    wrds = report["wrds_test"]
    repo_ok = all(item["status"] == "OK" for item in report["repo_packages"])
    wrds_files_ok = preferred_pg_service_path(probe).exists() and probe["wrds"]["pgpass"] == "OK"
    return [
        ("Python", "OK"),
        ("Python packages", "OK" if not missing_python_modules(probe) else "PARTIAL"),
        ("Repo packages", "OK" if repo_ok else "PARTIAL"),
        ("psql", "OK" if probe["tools"]["psql"]["path"] else "FAIL"),
        ("WRDS files", "OK" if wrds_files_ok else "PARTIAL"),
        ("WRDS connection", wrds["status"]),
        ("LaTeX", "OK" if probe["tools"]["pdflatex"]["path"] else "NOT INSTALLED"),
        ("R", "OK" if probe["tools"]["r"]["path"] else "NOT INSTALLED"),
        ("SSH key", "OK" if probe["wrds"]["ssh_key"] == "OK" else "NOT CONFIGURED"),
    ]


def build_actions(report: dict[str, Any]) -> list[str]:
    probe = report["probe"]
    actions: list[str] = []
    plan_steps = report["bootstrap_plan"]["steps"]

    if plan_steps:
        actions.append(
            "Execute the required bootstrap plan commands below. In sandboxed agent sessions, run the shell commands directly so approvals can be requested."
        )

    if not probe["tools"]["psql"]["path"]:
        actions.append("Install the PostgreSQL client so `psql service=wrds` is available.")

    if not preferred_pg_service_path(probe).exists():
        actions.append("Create or copy `pg_service.conf` into the location used by this machine.")
    if probe["wrds"]["pgpass"] != "OK":
        actions.append("Create or repair `.pgpass` with your WRDS credentials.")

    if probe["wrds"]["ssh_config"] != "OK":
        actions.append("Add an optional `Host wrds` SSH config entry if you need SSH or TAQ workflows.")
    if probe["wrds"]["ssh_key"] != "OK":
        actions.append("Configure the optional WRDS SSH key if you need SSH or TAQ workflows.")

    if report["wrds_test"]["status"] == "FAIL":
        actions.append("Fix WRDS credentials or connectivity, then rerun `tools/bootstrap.py audit`.")

    if not actions:
        actions.append("No gaps detected. Re-run the bootstrap after major environment changes.")

    return actions


def build_report(*, skip_wrds_test: bool) -> dict[str, Any]:
    probe = collect_probe()
    report = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "probe": probe,
        "preferred_pg_service_file": str(preferred_pg_service_path(probe)),
        "repo_packages": repo_package_status(probe),
        "local_files": local_file_status(),
        "wrds_test": run_wrds_checks(probe, skip=skip_wrds_test),
    }
    report["commands"] = {
        "powershell": power_shell_commands(probe),
        "bash": bash_commands(probe),
    }
    report["bootstrap_plan"] = build_bootstrap_plan(report)
    report["summary"] = summary_rows(report)
    report["actions"] = build_actions(report)
    return report


def format_tool_row(label: str, path: str, version: str) -> str:
    display_path = path or "not installed"
    display_version = version or ""
    return f"| {label} | `{display_path}` | {display_version} |"


def format_package_row(label: str, version: str) -> str:
    return f"| {label} | {version} |"


def format_repo_package_row(package: dict[str, str]) -> str:
    version = package["version"] or ""
    origin = package["origin"] or package["detail"] or ""
    return f"| {package['label']} | {package['status']} | {version} | {origin} |"


def render_local_env(report: dict[str, Any]) -> str:
    probe = report["probe"]
    powershell = report["commands"]["powershell"]
    bash = report["commands"]["bash"]

    lines = [
        "# Local Environment",
        "",
        f"Generated by `tools/bootstrap.py apply` on {report['generated_at']}.",
        "",
        "## Tool Paths",
        "| Tool | Path | Version |",
        "|------|------|---------|",
        format_tool_row("Python", probe["python"]["path"], probe["python"]["version"]),
        format_tool_row("psql", probe["tools"]["psql"]["path"], probe["tools"]["psql"]["version"]),
        format_tool_row("pdflatex", probe["tools"]["pdflatex"]["path"], probe["tools"]["pdflatex"]["version"]),
        format_tool_row("R", probe["tools"]["r"]["path"], probe["tools"]["r"]["version"]),
        format_tool_row("git", probe["tools"]["git"]["path"], probe["tools"]["git"]["version"]),
        format_tool_row("gh", probe["tools"]["gh"]["path"], probe["tools"]["gh"]["version"]),
        format_tool_row("ssh", probe["tools"]["ssh"]["path"], probe["tools"]["ssh"]["version"]),
        "",
        "## Python Packages",
        "| Package | Version |",
        "|---------|---------|",
    ]
    for name in PACKAGE_NAMES:
        lines.append(format_package_row(name, probe["packages"][name]))

    lines.extend(
        [
            "",
            "## Repo Packages",
            "| Package | Status | Version | Origin |",
            "|---------|--------|---------|--------|",
        ]
    )
    for package in report["repo_packages"]:
        lines.append(format_repo_package_row(package))

    lines.extend(
        [
            "",
            "## WRDS",
            f"- Username: {probe['wrds']['wrds_user'] or ''}",
            f"- Preferred pg_service.conf: `{report['preferred_pg_service_file']}`",
            f"- Home pg_service.conf: {probe['wrds']['pg_service_conf']}",
            f"- AppData pg_service.conf: {probe.get('windows', {}).get('appdata_pg_service', '') or 'n/a'}",
            f"- pgpass: {probe['wrds']['pgpass']}",
            f"- SSH config: {probe['wrds']['ssh_config']}",
            f"- SSH key: {probe['wrds']['ssh_key']}",
            f"- Connection test: {report['wrds_test']['status']}",
            "",
            "## Canonical Commands",
            f"- Python (PowerShell/native): `{powershell['python']}`",
            f"- pip (PowerShell/native): `{powershell['pip']}`",
            f"- psql (PowerShell/native): `{powershell['psql']}`",
            f"- Python (Bash): `{bash['python']}`",
            f"- pip (Bash): `{bash['pip']}`",
            f"- psql (Bash): `{bash['psql']}`",
            "",
            "## Notes",
            f"- Platform: {probe['platform']['system']} {probe['platform']['release']} ({probe['platform']['machine']})",
            f"- Shell: {probe['platform']['shell'] or 'unknown'}",
            "- Shared bootstrap flow: `tools/bootstrap.py audit`, run the required bootstrap plan commands, then `tools/bootstrap.py apply` and `audit` again",
            "- `tools/bootstrap.py repair` is a convenience fallback for direct local terminals when agent approval flow is not involved",
            "- Re-run `/onboard` or the bootstrap commands after major environment changes.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_claude_local(report: dict[str, Any]) -> str:
    bash = report["commands"]["bash"]
    lines = [
        "# Claude Local Environment",
        "",
        "`LOCAL_ENV.md` is the canonical machine-local environment note for this clone.",
        "",
        f"Generated by `tools/bootstrap.py apply` on {report['generated_at']}.",
        "",
        "## Preferred Bash Commands",
        f"- Python: `{bash['python']}`",
        f"- pip: `{bash['pip']}`",
        f"- psql: `{bash['psql']}`",
        "",
        "## Notes",
        "- Use `/onboard` to rerun the shared bootstrap flow from Claude Code.",
        "- The shared flow is `tools/bootstrap.py audit`, run the required bootstrap plan commands, then `tools/bootstrap.py apply` and `audit` again.",
        "- `tools/bootstrap.py repair` is an optional convenience path for direct local terminals.",
    ]
    return "\n".join(lines) + "\n"


def bash_allow_entries(probe: dict[str, Any]) -> list[str]:
    def variants(path: str) -> list[str]:
        items = [path]
        slash_path = path.replace("\\", "/")
        if slash_path not in items:
            items.append(slash_path)
        msys_path = display_bash_path(path)
        if msys_path not in items:
            items.append(msys_path)
        return items

    entries: list[str] = []
    for python_path in variants(probe["python"]["path"]):
        entries.extend(
            [
                f"Bash({python_path} *)",
                f'Bash("{python_path}" *)',
                f"Bash({python_path} -m pip *)",
                f'Bash("{python_path}" -m pip *)',
            ]
        )

    psql_path = probe["tools"]["psql"]["path"]
    if psql_path:
        for candidate in variants(psql_path):
            entries.extend(
                [
                    f"Bash({candidate} *)",
                    f'Bash("{candidate}" *)',
                    f"Bash(PGSERVICEFILE=* {candidate} service=wrds*)",
                    f'Bash(PGSERVICEFILE=* "{candidate}" service=wrds*)',
                ]
            )

    unique_entries: list[str] = []
    for entry in entries:
        if entry not in unique_entries:
            unique_entries.append(entry)
    return unique_entries


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def relative_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def force_unlink(path: Path) -> bool:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        try:
            os.chmod(path, stat.S_IWRITE)
            path.unlink(missing_ok=True)
        except OSError:
            return False
    return not path.exists()


def force_rmtree(path: Path) -> bool:
    def onerror(func: Any, target: str, _: Any) -> None:
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            return

    shutil.rmtree(path, onerror=onerror)
    return not path.exists()


def cleanup_generated_repo_artifacts() -> list[str]:
    removed: list[str] = []
    removable_dirs: list[Path] = []
    removable_files: list[Path] = []
    scan_roots = [REPO_ROOT / "fintools", PYBONDLAB_ROOT, REPO_ROOT / "tools"]

    root_egg_info = REPO_ROOT / "fintools.egg-info"
    if root_egg_info.exists():
        removable_dirs.append(root_egg_info)

    for root in scan_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            relative = path.relative_to(REPO_ROOT)
            if any(part in IGNORED_CLEANUP_PARTS or part.startswith(".tmp-") for part in relative.parts):
                continue
            if path.is_dir() and (path.name == "__pycache__" or path.name.endswith(".egg-info")):
                removable_dirs.append(path)
            elif path.is_file() and path.suffix in {".pyc", ".pyo", ".pyd"}:
                removable_files.append(path)

    for path in removable_files:
        if force_unlink(path):
            removed.append(relative_path(path))

    for path in sorted(removable_dirs, key=lambda item: len(item.parts), reverse=True):
        if path.exists() and force_rmtree(path):
            removed.append(relative_path(path))

    unique_removed: list[str] = []
    for item in removed:
        if item not in unique_removed:
            unique_removed.append(item)
    return unique_removed


def render_settings_local(report: dict[str, Any]) -> str:
    current = load_json(SETTINGS_LOCAL_PATH)
    if not isinstance(current, dict):
        current = {}

    permissions = current.get("permissions")
    if not isinstance(permissions, dict):
        permissions = {}
    allow = permissions.get("allow")
    if not isinstance(allow, list):
        allow = []
    deny = permissions.get("deny")
    if not isinstance(deny, list):
        deny = []

    preserved_allow = [
        entry
        for entry in allow
        if not (isinstance(entry, str) and entry.startswith("Bash("))
    ]
    permissions["allow"] = preserved_allow + bash_allow_entries(report["probe"])
    permissions["deny"] = deny

    current["permissions"] = permissions
    return json.dumps(current, indent=2) + "\n"


def write_outputs(report: dict[str, Any]) -> list[str]:
    written_files: list[str] = []

    LOCAL_ENV_PATH.write_text(render_local_env(report), encoding="utf-8")
    written_files.append("LOCAL_ENV.md")

    CLAUDE_LOCAL_PATH.write_text(render_claude_local(report), encoding="utf-8")
    written_files.append("CLAUDE.local.md")

    SETTINGS_LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_LOCAL_PATH.write_text(render_settings_local(report), encoding="utf-8")
    written_files.append(".claude/settings.local.json")

    return written_files


def print_section(title: str) -> None:
    print()
    print(title)


def print_report(
    report: dict[str, Any],
    *,
    mode: str,
    repair_results: list[dict[str, str]] | None = None,
    written_files: list[str] | None = None,
    cleaned_artifacts: list[str] | None = None,
) -> None:
    probe = report["probe"]

    print("Scanning your environment...")
    print(f"Repo root: {REPO_ROOT}")

    print_section("Environment")
    print(
        f"  Platform           {probe['platform']['system']} {probe['platform']['release']} "
        f"({probe['platform']['machine']})"
    )
    print(f"  Python             {probe['python']['path']} ({probe['python']['version']})")
    print(f"  psql               {probe['tools']['psql']['path'] or 'MISSING'}")
    print(f"  pdflatex           {probe['tools']['pdflatex']['path'] or 'not installed'}")
    print(f"  R                  {probe['tools']['r']['path'] or 'not installed'}")
    print(f"  git                {probe['tools']['git']['path'] or 'MISSING'}")
    print(f"  gh                 {probe['tools']['gh']['path'] or 'not installed'}")
    print(f"  ssh                {probe['tools']['ssh']['path'] or 'MISSING'}")

    print_section("Python Packages")
    for name in PACKAGE_NAMES:
        print(f"  {name:<18} {probe['packages'][name]}")

    print_section("Repo Packages")
    for package in report["repo_packages"]:
        origin = package["origin"] or package["detail"] or ""
        suffix = f" [{origin}]" if origin else ""
        version = f" ({package['version']})" if package["version"] else ""
        print(f"  {package['label']:<18} {package['status']}{version}{suffix}")

    print_section("WRDS Files")
    print(f"  preferred_service   {report['preferred_pg_service_file']}")
    print(f"  home_pg_service     {probe['wrds']['pg_service_conf']}")
    print(f"  appdata_pg_service  {probe.get('windows', {}).get('appdata_pg_service', '') or 'n/a'}")
    print(f"  pgpass              {probe['wrds']['pgpass']}")
    print(f"  ssh_config          {probe['wrds']['ssh_config']}")
    print(f"  ssh_key             {probe['wrds']['ssh_key']}")
    print(f"  wrds_user           {probe['wrds']['wrds_user'] or '(not set)'}")

    print()
    print("Testing WRDS connectivity...")
    if report["wrds_test"]["status"] == "SKIPPED":
        print(f"  skipped            {report['wrds_test']['reason']}")
    else:
        for check in report["wrds_test"]["checks"]:
            print(f"  {check['name']:<18} {check['status']}: {check['detail']}")

    if repair_results:
        print_section("Repair")
        for item in repair_results:
            print(f"  {item['name']:<18} {item['status']}: {item['detail']}")

    if report["bootstrap_plan"]["steps"]:
        print_section("Bootstrap Commands")
        for step in report["bootstrap_plan"]["steps"]:
            print(f"  {step['label']}: {step['reason']}")
            print(f"    PowerShell/native: {step['powershell']}")
            print(f"    Bash:              {step['bash']}")

    print_section("Local Files")
    for item in report["local_files"]:
        print(f"  {item['path']:<27} {item['status']}")

    if mode in {"apply", "repair"} and written_files:
        print_section("Wrote")
        for path in written_files:
            print(f"  {path}")

    if cleaned_artifacts:
        print_section("Cleaned")
        for path in cleaned_artifacts:
            print(f"  {path}")

    print_section("Summary")
    for label, status in report["summary"]:
        print(f"  {label:<18} {status}")

    print_section("Next Steps")
    for action in report["actions"]:
        print(f"  - {action}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    for mode in ("audit", "apply", "repair"):
        subparser = subparsers.add_parser(mode)
        subparser.add_argument(
            "--skip-wrds-test",
            action="store_true",
            help="Skip live WRDS connectivity checks and only inspect local state.",
        )
        subparser.add_argument(
            "--json",
            action="store_true",
            help="Emit structured JSON instead of human-readable output.",
        )
        if mode == "repair":
            subparser.add_argument(
                "--write-local-files",
                action="store_true",
                help="Write LOCAL_ENV.md, CLAUDE.local.md, and .claude/settings.local.json after repair.",
            )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    repair_results: list[dict[str, str]] = []
    written_files: list[str] = []
    cleaned_artifacts: list[str] = []

    report = build_report(skip_wrds_test=args.skip_wrds_test)

    if args.mode == "repair":
        repair_results = repair_environment(report)
        report = build_report(skip_wrds_test=args.skip_wrds_test)
        if args.write_local_files:
            written_files = write_outputs(report)
            report = build_report(skip_wrds_test=args.skip_wrds_test)
    elif args.mode == "apply":
        written_files = write_outputs(report)
        report = build_report(skip_wrds_test=args.skip_wrds_test)

    cleaned_artifacts = cleanup_generated_repo_artifacts()

    if args.json:
        payload = {
            "mode": args.mode,
            "repair_results": repair_results,
            "written_files": written_files,
            "cleaned_artifacts": cleaned_artifacts,
            **report,
        }
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print_report(
            report,
            mode=args.mode,
            repair_results=repair_results,
            written_files=written_files,
            cleaned_artifacts=cleaned_artifacts,
        )

    has_failed_repairs = any(item["status"] == "FAIL" for item in repair_results)
    return 1 if has_failed_repairs else 0


if __name__ == "__main__":
    raise SystemExit(main())
