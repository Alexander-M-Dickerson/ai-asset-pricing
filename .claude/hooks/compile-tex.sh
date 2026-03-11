#!/bin/bash
# PostToolUse hook: auto-recompile LaTeX after any .tex file is edited/written.
# Finds the nearest main.tex in the same directory and runs the full build cycle.
# Uses LOCAL_ENV.md paths; falls back to bare pdflatex/bibtex if not found.

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.content // empty' 2>/dev/null)

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

# Locate pdflatex — try LOCAL_ENV.md, then PATH
PDFLATEX="pdflatex"
REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || echo .)}"
if [[ -f "$REPO_ROOT/LOCAL_ENV.md" ]]; then
  FOUND=$(grep -oP '(?<=\| pdflatex\s+\| `)[^`]+' "$REPO_ROOT/LOCAL_ENV.md" 2>/dev/null | head -1)
  [[ -n "$FOUND" && -x "$FOUND" ]] && PDFLATEX="$FOUND"
fi

# Run the full build cycle
cd "$TEX_DIR"
"$PDFLATEX" -interaction=nonstopmode main.tex > /dev/null 2>&1 || true
bibtex main > /dev/null 2>&1 || true
"$PDFLATEX" -interaction=nonstopmode main.tex > /dev/null 2>&1 || true
"$PDFLATEX" -interaction=nonstopmode main.tex > /dev/null 2>&1 || true

exit 0
