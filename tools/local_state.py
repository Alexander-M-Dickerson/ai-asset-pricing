#!/usr/bin/env python3
"""Shared local-state path resolution for onboarding, hooks, and docs."""

from __future__ import annotations

import argparse
import json
import os
import platform
from pathlib import Path
from typing import Any, Mapping


APP_NAME = "ai-asset-pricing"
CANONICAL_FILENAMES = {
    "local_env": "local_env.md",
    "claude_local": "claude.local.md",
    "settings_local": "settings.local.json",
}
COMPAT_FILENAMES = {
    "local_env": Path("LOCAL_ENV.md"),
    "claude_local": Path("CLAUDE.local.md"),
    "settings_local": Path(".claude") / "settings.local.json",
}
SYNCED_FOLDER_MARKERS = {
    "dropbox": "Dropbox",
    "onedrive": "OneDrive",
    "google drive": "Google Drive",
    "icloud drive": "iCloud Drive",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _env_path(env: Mapping[str, str], key: str) -> Path | None:
    value = env.get(key, "").strip()
    return Path(value).expanduser() if value else None


def _home_path(env: Mapping[str, str], *, system_label: str) -> Path:
    if system_label == "Windows":
        return _env_path(env, "USERPROFILE") or Path.home()
    return _env_path(env, "HOME") or Path.home()


def _platform_name(*, system_name: str | None = None, os_name: str | None = None) -> str:
    if system_name:
        return system_name
    if os_name == "nt":
        return "Windows"
    return platform.system()


def canonical_directories(
    *,
    env: Mapping[str, str] | None = None,
    system_name: str | None = None,
    os_name: str | None = None,
) -> dict[str, Path]:
    env = env or os.environ
    system_label = _platform_name(system_name=system_name, os_name=os_name)
    home = _home_path(env, system_label=system_label)

    config_override = _env_path(env, "AI_ASSET_PRICING_CONFIG_DIR")
    state_override = _env_path(env, "AI_ASSET_PRICING_STATE_DIR")

    if config_override or state_override:
        config_dir = config_override or state_override or home / ".config" / APP_NAME
        state_dir = state_override or config_override or home / ".local" / "state" / APP_NAME
        return {"config_dir": config_dir, "state_dir": state_dir}

    if system_label == "Windows":
        config_root = _env_path(env, "APPDATA") or home / "AppData" / "Roaming"
        state_root = _env_path(env, "LOCALAPPDATA") or home / "AppData" / "Local"
        config_dir = config_root / APP_NAME
        state_dir = state_root / APP_NAME
        return {"config_dir": config_dir, "state_dir": state_dir}

    if system_label == "Darwin":
        base = home / "Library" / "Application Support" / APP_NAME
        return {"config_dir": base / "config", "state_dir": base / "state"}

    config_home = _env_path(env, "XDG_CONFIG_HOME") or home / ".config"
    state_home = _env_path(env, "XDG_STATE_HOME") or home / ".local" / "state"
    return {
        "config_dir": config_home / APP_NAME,
        "state_dir": state_home / APP_NAME,
    }


def canonical_paths(
    *,
    env: Mapping[str, str] | None = None,
    system_name: str | None = None,
    os_name: str | None = None,
) -> dict[str, Path]:
    dirs = canonical_directories(env=env, system_name=system_name, os_name=os_name)
    state_dir = dirs["state_dir"]
    return {
        "config_dir": dirs["config_dir"],
        "state_dir": state_dir,
        **{name: state_dir / filename for name, filename in CANONICAL_FILENAMES.items()},
    }


def compatibility_paths(repo: Path | None = None) -> dict[str, Path]:
    root = repo or repo_root()
    return {name: root / rel_path for name, rel_path in COMPAT_FILENAMES.items()}


def synced_storage_hint(repo: Path | None = None) -> dict[str, str]:
    root = repo or repo_root()
    lowered_parts = [part.lower() for part in root.parts]
    for marker, label in SYNCED_FOLDER_MARKERS.items():
        if any(marker in part for part in lowered_parts):
            return {"kind": "synced_folder_candidate", "provider": label}
    return {"kind": "local_or_unknown", "provider": ""}


def local_state_records(
    repo: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    system_name: str | None = None,
    os_name: str | None = None,
) -> dict[str, Any]:
    root = repo or repo_root()
    canonical = canonical_paths(env=env, system_name=system_name, os_name=os_name)
    compat = compatibility_paths(root)
    files: dict[str, dict[str, str]] = {}

    for name in CANONICAL_FILENAMES:
        canonical_path = canonical[name]
        compat_path = compat[name]
        canonical_exists = canonical_path.exists()
        compat_exists = compat_path.exists()
        if canonical_exists:
            active_path = canonical_path
            active_source = "canonical"
        elif compat_exists:
            active_path = compat_path
            active_source = "compat"
        else:
            active_path = canonical_path
            active_source = "missing"
        files[name] = {
            "name": name,
            "canonical_path": str(canonical_path),
            "canonical_status": "OK" if canonical_exists else "MISSING",
            "compat_path": str(compat_path),
            "compat_status": "OK" if compat_exists else "MISSING",
            "active_path": str(active_path),
            "active_source": active_source,
        }

    return {
        "config_dir": str(canonical["config_dir"]),
        "state_dir": str(canonical["state_dir"]),
        "storage_hint": synced_storage_hint(root),
        "files": files,
    }


def local_state_path(name: str, *, repo: Path | None = None) -> Path:
    records = local_state_records(repo)
    file_record = records["files"][name]
    return Path(file_record["canonical_path"])


def active_local_state_path(name: str, *, repo: Path | None = None) -> Path:
    records = local_state_records(repo)
    file_record = records["files"][name]
    return Path(file_record["active_path"])


def emit_json(payload: Mapping[str, Any]) -> None:
    json.dump(payload, fp=os.sys.stdout, indent=2, sort_keys=True)
    os.sys.stdout.write("\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit the full local-state payload as JSON.")
    subparsers = parser.add_subparsers(dest="mode")

    path_parser = subparsers.add_parser("path")
    path_parser.add_argument("name", choices=sorted(CANONICAL_FILENAMES))
    path_parser.add_argument(
        "--active",
        action="store_true",
        help="Print the active path after canonical->compat fallback resolution.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    records = local_state_records()
    if args.mode == "path":
        path = active_local_state_path(args.name) if args.active else local_state_path(args.name)
        print(path)
        return 0
    emit_json(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
