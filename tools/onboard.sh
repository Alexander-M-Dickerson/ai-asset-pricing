#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

python_version_ok() {
  local python_bin="$1"
  [[ -n "$python_bin" ]] || return 1
  "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)' >/dev/null 2>&1
}

find_python() {
  local candidate=""
  for candidate in \
    "${HOME}/miniforge3/bin/python" \
    "${HOME}/miniconda3/bin/python" \
    "${HOME}/anaconda3/bin/python"; do
    if [[ -x "$candidate" ]] && python_version_ok "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      local resolved
      resolved=$(command -v "$candidate")
      if python_version_ok "$resolved"; then
        printf '%s\n' "$resolved"
        return 0
      fi
    fi
  done

  return 1
}

install_miniforge() {
  local system_name arch_name installer_url installer_path
  system_name=$(uname -s)
  arch_name=$(uname -m)

  if [[ "$system_name" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
    brew install --cask miniforge
    return 0
  fi

  case "$system_name" in
    Linux) system_name="Linux" ;;
    Darwin) system_name="MacOSX" ;;
    *)
      cat >&2 <<'ERRMSG'
No Python 3.11+ interpreter found and no supported installer is available.
Options:
  1. Install Miniforge from https://conda-forge.org/miniforge/
  2. Install Python 3.11+ from https://python.org/downloads/
After installing, rerun: bash tools/onboard.sh
ERRMSG
      return 1
      ;;
  esac

  case "$arch_name" in
    x86_64|amd64) arch_name="x86_64" ;;
    arm64|aarch64) arch_name="arm64" ;;
  esac

  installer_url="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-${system_name}-${arch_name}.sh"
  installer_path="${TMPDIR:-/tmp}/ai-asset-pricing-miniforge.sh"

  curl -L "$installer_url" -o "$installer_path"
  bash "$installer_path" -b -p "${HOME}/miniforge3"
}

main() {
  local python_bin
  if ! python_bin=$(find_python); then
    install_miniforge
    python_bin=$(find_python)
  fi

  if [[ -z "${python_bin:-}" ]]; then
    echo "Failed to provision Python 3.11+ for onboarding." >&2
    exit 1
  fi

  cd "$REPO_ROOT"
  "$python_bin" tools/onboard_driver.py --shell bash "$@"
}

main "$@"
