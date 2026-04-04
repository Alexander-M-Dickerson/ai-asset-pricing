#!/bin/bash
# PostToolUse hook: auto-recompile LaTeX after any .tex file is edited/written.
# Finds the nearest main.tex in the same directory and runs the full build cycle.
# Uses canonical external local-state paths when available and falls back to PATH.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=/dev/null
source "$SCRIPT_DIR/common.sh"

INPUT=$(cat)
REPO_ROOT=$(resolve_repo_root)
HOOK_PYTHON=$(resolve_hook_python "$REPO_ROOT" || true)
FILE_PATH=$(json_tool_input_value "$HOOK_PYTHON" "$INPUT" file_path path || true)

# Only trigger for .tex files
[[ "$FILE_PATH" == *.tex ]] || exit 0

# Resolve the directory containing the edited file
if [[ -f "$FILE_PATH" ]]; then
  TEX_DIR=$(cd "$(dirname "$FILE_PATH")" && pwd)
else
  exit 0
fi

# Find main.tex: check same dir, then parent
MAIN_TEX=""
if [[ -f "$TEX_DIR/main.tex" ]]; then
  MAIN_TEX="$TEX_DIR/main.tex"
elif [[ -f "$(dirname "$TEX_DIR")/main.tex" ]]; then
  MAIN_TEX="$(dirname "$TEX_DIR")/main.tex"
  TEX_DIR="$(dirname "$TEX_DIR")"
fi

[[ -n "$MAIN_TEX" ]] || exit 0

PDFLATEX="pdflatex"
BIBTEX="bibtex"

FOUND=$(local_env_tool_path "$REPO_ROOT" "pdflatex" 2>/dev/null || true)
if [[ -n "$FOUND" && -x "$FOUND" ]]; then
  PDFLATEX="$FOUND"
fi

FOUND=$(local_env_tool_path "$REPO_ROOT" "bibtex" 2>/dev/null || true)
if [[ -n "$FOUND" && -x "$FOUND" ]]; then
  BIBTEX="$FOUND"
fi

if [[ "$PDFLATEX" != "pdflatex" ]]; then
  PDFLATEX_DIR=$(cd "$(dirname "$PDFLATEX")" && pwd)
  if [[ -x "$PDFLATEX_DIR/bibtex" ]]; then
    BIBTEX="$PDFLATEX_DIR/bibtex"
  elif [[ -x "$PDFLATEX_DIR/bibtex.exe" ]]; then
    BIBTEX="$PDFLATEX_DIR/bibtex.exe"
  fi
fi

if [[ "$BIBTEX" == "bibtex" ]]; then
  FOUND=$(command -v bibtex 2>/dev/null || true)
  [[ -n "$FOUND" ]] && BIBTEX="$FOUND"
fi

cd "$TEX_DIR"
"$PDFLATEX" -interaction=nonstopmode main.tex > /dev/null 2>&1 || true
"$BIBTEX" main > /dev/null 2>&1 || true
"$PDFLATEX" -interaction=nonstopmode main.tex > /dev/null 2>&1 || true
"$PDFLATEX" -interaction=nonstopmode main.tex > /dev/null 2>&1 || true

exit 0
