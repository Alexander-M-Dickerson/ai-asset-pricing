#!/bin/bash
# PostToolUse hook: clean Python build artifacts after pip install.
# Removes __pycache__, *.pyc, *.egg-info from the repo tree.

set -uo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Only trigger on pip install commands
echo "$COMMAND" | grep -qE '\bpip\s+install\b' || exit 0

REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || echo .)}"

find "$REPO_ROOT" -type d -name '__pycache__' -not -path '*/.git/*' -exec rm -rf {} + 2>/dev/null || true
find "$REPO_ROOT" -type d -name '*.egg-info' -not -path '*/.git/*' -exec rm -rf {} + 2>/dev/null || true
find "$REPO_ROOT" -name '*.pyc' -not -path '*/.git/*' -delete 2>/dev/null || true

exit 0
