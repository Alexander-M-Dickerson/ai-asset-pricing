#!/usr/bin/env python3
"""Shared cross-platform environment probe for bootstrap and onboarding."""

from __future__ import annotations

import importlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from glob import glob
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

try:
    from tools.local_state import local_state_records
except ImportError:  # pragma: no cover - script execution path
    from local_state import local_state_records


PACKAGE_NAMES = (
    "pandas",
    "psycopg2",
    "pyarrow",
    "numpy",
    "matplotlib",
    "statsmodels",
)


def run_version(cmd: list[str], first_line_only: bool = True) -> str:
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return ""

    output = (proc.stdout or proc.stderr or "").strip()
    if not output:
        return ""
    return output.splitlines()[0] if first_line_only else output


def command_succeeds(cmd: list[str]) -> bool:
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return False
    return proc.returncode == 0


def which(name: str) -> str:
    return shutil.which(name) or ""


def existing_path(*candidates: Path) -> str:
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def first_glob(pattern: str) -> str:
    for match in sorted(glob(pattern)):
        path = Path(match)
        if path.exists():
            return str(path)
    return ""


def detect_psql(home: Path) -> str:
    found = which("psql")
    if found:
        return found

    if os.name == "nt":
        candidates = [
            home / "tools" / "pgsql" / "bin" / "psql.exe",
            Path(os.environ.get("ProgramFiles", "")) / "PostgreSQL",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "PostgreSQL",
        ]
        direct = existing_path(candidates[0])
        if direct:
            return direct
        for base in candidates[1:]:
            if not str(base) or str(base) == ".":
                continue
            match = first_glob(str(base / "*" / "bin" / "psql.exe"))
            if match:
                return match
        return ""

    if platform.system() == "Darwin":
        return existing_path(
            Path("/opt/homebrew/opt/libpq/bin/psql"),
            Path("/usr/local/opt/libpq/bin/psql"),
        )

    return ""


def detect_pdflatex() -> str:
    found = which("pdflatex")
    if found:
        return found
    if os.name == "nt":
        return existing_path(
            Path(r"C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe"),
            Path(r"C:\Program Files\MiKTeX\miktex\bin\pdflatex.exe"),
        )
    return ""


def detect_bibtex(pdflatex_path: str = "") -> str:
    if pdflatex_path:
        pdflatex_dir = Path(pdflatex_path).parent
        sibling = existing_path(
            pdflatex_dir / "bibtex",
            pdflatex_dir / "bibtex.exe",
        )
        if sibling:
            return sibling

    found = which("bibtex")
    if found:
        return found

    if os.name == "nt":
        return existing_path(
            Path(r"C:\Program Files\MiKTeX\miktex\bin\x64\bibtex.exe"),
            Path(r"C:\Program Files\MiKTeX\miktex\bin\bibtex.exe"),
        )
    return ""


def detect_r() -> str:
    found = which("R") or which("Rscript")
    if found:
        return found
    if os.name == "nt":
        match = first_glob(r"C:\Program Files\R\R-*\bin\R.exe")
        if match:
            return match
    return ""


def detect_bash() -> str:
    found = which("bash")
    if found and command_succeeds([found, "-lc", "exit 0"]):
        return found
    return ""


def detect_installers() -> dict[str, dict[str, str]]:
    installers: dict[str, dict[str, str]] = {}
    for label, command in (
        ("winget", "winget"),
        ("brew", "brew"),
        ("apt_get", "apt-get"),
        ("dnf", "dnf"),
    ):
        path = which(command)
        installers[label] = {
            "path": path,
            "version": run_version([path, "--version"]) if path else "",
        }
    return installers


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def contains_wrds_host(ssh_config: Path) -> bool:
    text = read_text(ssh_config)
    return bool(re.search(r"(?im)^\s*host\s+wrds\s*$", text))


def extract_wrds_user(pg_service: Path) -> str:
    text = read_text(pg_service)
    for line in text.splitlines():
        if line.strip().startswith("user="):
            return line.split("=", 1)[1].strip()
    return ""


def package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in PACKAGE_NAMES:
        try:
            module = importlib.import_module(name)
            versions[name] = getattr(module, "__version__", "installed")
        except ImportError:
            versions[name] = "MISSING"
    return versions


def bashrc_flags(bashrc: Path, home: Path) -> dict[str, str]:
    if os.name != "nt":
        return {}

    text = read_text(bashrc) if bashrc.exists() else ""
    psql_hint = str(home / "tools" / "pgsql" / "bin").replace("\\", "/")
    return {
        "exists": "YES" if bashrc.exists() else "NO",
        "has_psql_path": "YES" if psql_hint in text or "pgsql/bin" in text else "NO",
        "has_pgservicefile": "YES" if "PGSERVICEFILE" in text else "NO",
    }


def running_in_virtualenv() -> bool:
    return sys.prefix != sys.base_prefix


def reported_python_path() -> str:
    executable = Path(sys.executable)
    if running_in_virtualenv():
        return str(executable if executable.is_absolute() else executable.absolute())
    return str(executable.resolve())


def collect_probe() -> dict[str, Any]:
    home = Path.home()
    pg_service = home / ".pg_service.conf"
    pgpass = home / ".pgpass"
    ssh_config = home / ".ssh" / "config"
    ssh_key = home / ".ssh" / "wrds"
    bashrc = home / ".bashrc"
    appdata = Path(os.environ.get("APPDATA", "")) if os.environ.get("APPDATA") else None

    python_path = reported_python_path()
    python_version = platform.python_version()
    pip_command = f'"{python_path}" -m pip'
    shell = os.environ.get("SHELL") or os.environ.get("ComSpec") or ""

    psql_path = detect_psql(home)
    pdflatex_path = detect_pdflatex()
    bibtex_path = detect_bibtex(pdflatex_path)
    r_path = detect_r()
    git_path = which("git")
    gh_path = which("gh")
    ssh_path = which("ssh")
    bash_path = detect_bash()
    conda_path = which("conda")
    uv_path = which("uv")
    installers = detect_installers()

    result = {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "shell": shell,
            "home": str(home),
            "appdata": str(appdata) if appdata else "",
        },
        "python": {
            "path": python_path,
            "version": python_version,
            "pip_command": pip_command,
            "conda_path": conda_path,
        },
        "tools": {
            "uv": {
                "path": uv_path,
                "version": run_version([uv_path, "--version"]) if uv_path else "",
            },
            "psql": {
                "path": psql_path,
                "version": run_version([psql_path, "--version"]) if psql_path else "",
            },
            "pdflatex": {
                "path": pdflatex_path,
                "version": run_version([pdflatex_path, "--version"]) if pdflatex_path else "",
            },
            "bibtex": {
                "path": bibtex_path,
                "version": run_version([bibtex_path, "--version"]) if bibtex_path else "",
            },
            "r": {
                "path": r_path,
                "version": run_version([r_path, "--version"]) if r_path else "",
            },
            "git": {
                "path": git_path,
                "version": run_version([git_path, "--version"]) if git_path else "",
            },
            "gh": {
                "path": gh_path,
                "version": run_version([gh_path, "--version"]) if gh_path else "",
            },
            "ssh": {
                "path": ssh_path,
                "version": run_version([ssh_path, "-V"]) if ssh_path else "",
            },
            "bash": {
                "path": bash_path,
                "version": (
                    "bash on PATH"
                    if bash_path and os.name == "nt"
                    else run_version([bash_path, "--version"]) if bash_path else ""
                ),
            },
        },
        "installers": installers,
        "packages": package_versions(),
        "wrds": {
            "pg_service_conf": "OK" if pg_service.exists() else "MISSING",
            "pgpass": "OK" if pgpass.exists() else "MISSING",
            "ssh_config": "OK" if contains_wrds_host(ssh_config) else "MISSING",
            "ssh_key": "OK" if ssh_key.exists() else "MISSING",
            "wrds_user": extract_wrds_user(pg_service),
        },
        "windows": {},
        "local_state": local_state_records(Path(__file__).resolve().parent.parent),
    }

    if os.name == "nt":
        app_pg_dir = appdata / "postgresql" if appdata else None
        result["windows"] = {
            "appdata_pg_service": "OK"
            if app_pg_dir and (app_pg_dir / "pg_service.conf").exists()
            else "MISSING",
            "appdata_pgpass": "OK"
            if app_pg_dir and (app_pg_dir / "pgpass.conf").exists()
            else "MISSING",
            "bashrc": bashrc_flags(bashrc, home),
        }

    return result


def emit_probe_json(result: dict[str, Any]) -> None:
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def main() -> int:
    emit_probe_json(collect_probe())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
