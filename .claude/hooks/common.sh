#!/bin/bash
# Shared helpers for Claude hook scripts.

resolve_repo_root() {
  if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
    printf '%s\n' "$CLAUDE_PROJECT_DIR"
    return 0
  fi

  git rev-parse --show-toplevel 2>/dev/null || pwd
}


canonical_state_dir() {
  local app_name="ai-asset-pricing"
  if [[ -n "${AI_ASSET_PRICING_STATE_DIR:-}" ]]; then
    printf '%s\n' "$AI_ASSET_PRICING_STATE_DIR"
    return 0
  fi

  # Keep the previous env var working as a local compatibility fallback.
  if [[ -n "${EMPIRICAL_CLAUDE_STATE_DIR:-}" ]]; then
    printf '%s\n' "$EMPIRICAL_CLAUDE_STATE_DIR"
    return 0
  fi

  local system_name="${AI_ASSET_PRICING_SYSTEM_NAME:-}"
  if [[ -z "$system_name" ]]; then
    local uname_s=""
    uname_s=$(uname -s 2>/dev/null || echo "")

    if [[ "$uname_s" == Darwin ]]; then
      system_name="Darwin"
    elif [[ "$uname_s" == MINGW* || "$uname_s" == MSYS* || "$uname_s" == CYGWIN* || "${OS:-}" == Windows_NT ]]; then
      system_name="Windows"
    else
      system_name="Linux"
    fi
  fi

  local home_dir=""
  if [[ "$system_name" == "Windows" ]]; then
    home_dir="${USERPROFILE:-${HOME:-}}"
  else
    home_dir="${HOME:-}"
  fi

  if [[ "$system_name" == "Darwin" ]]; then
    printf '%s\n' "${home_dir}/Library/Application Support/${app_name}/state"
    return 0
  fi

  if [[ "$system_name" == "Windows" ]]; then
    if [[ -n "${LOCALAPPDATA:-}" ]]; then
      printf '%s\n' "${LOCALAPPDATA}/${app_name}"
    else
      printf '%s\n' "${home_dir}/AppData/Local/${app_name}"
    fi
    return 0
  fi

  if [[ -n "${XDG_STATE_HOME:-}" ]]; then
    printf '%s\n' "${XDG_STATE_HOME}/${app_name}"
  else
    printf '%s\n' "${home_dir}/.local/state/${app_name}"
  fi
}


local_env_tool_path() {
  local repo_root="$1"
  local tool_label="$2"
  local state_dir=""
  local canonical_local_env=""
  local compat_local_env="$repo_root/LOCAL_ENV.md"

  state_dir=$(canonical_state_dir)
  canonical_local_env="$state_dir/local_env.md"

  local local_env=""
  if [[ -f "$canonical_local_env" ]]; then
    local_env="$canonical_local_env"
  elif [[ -f "$compat_local_env" ]]; then
    local_env="$compat_local_env"
  else
    return 1
  fi

  awk -v tool="$tool_label" -F'`' '
    $0 ~ "^\\|[[:space:]]*" tool "[[:space:]]*\\|" {
      if (NF >= 2) {
        print $2
        exit
      }
    }
  ' "$local_env"
}


resolve_hook_python() {
  local repo_root="$1"
  local found=""

  found=$(local_env_tool_path "$repo_root" "Python" 2>/dev/null || true)
  if [[ -n "$found" && -x "$found" ]]; then
    printf '%s\n' "$found"
    return 0
  fi

  found=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)
  if [[ -n "$found" ]]; then
    printf '%s\n' "$found"
    return 0
  fi

  return 1
}


json_tool_input_value() {
  local python_bin="$1"
  local input="$2"
  shift 2

  [[ -n "$python_bin" ]] || return 1

  printf '%s' "$input" | "$python_bin" -c '
import json
import sys

keys = sys.argv[1:]
try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(0)

tool_input = payload.get("tool_input") or {}
for key in keys:
    value = tool_input.get(key)
    if isinstance(value, str) and value:
        print(value)
        break
' "$@"
}
