#!/bin/bash
# PreToolUse hook: run release_preflight.py before git commit.
# Blocks the commit (exit 2) if preflight fails.

set -uo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Only trigger on git commit commands
echo "$COMMAND" | grep -qE '\bgit\s+commit\b' || exit 0

REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || echo .)}"

# Locate Python from LOCAL_ENV.md or fall back to python3/python
PYTHON=""
if [[ -f "$REPO_ROOT/LOCAL_ENV.md" ]]; then
  FOUND=$(grep -oP '(?<=\| Python\s+\| `)[^`]+' "$REPO_ROOT/LOCAL_ENV.md" 2>/dev/null | head -1)
  [[ -n "$FOUND" && -x "$FOUND" ]] && PYTHON="$FOUND"
fi
if [[ -z "$PYTHON" ]]; then
  PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null || echo "")
fi
[[ -n "$PYTHON" ]] || exit 0

# Run preflight
OUTPUT=$("$PYTHON" "$REPO_ROOT/tools/release_preflight.py" --strict 2>&1) || {
  echo "Release preflight FAILED — commit blocked:" >&2
  echo "$OUTPUT" >&2
  exit 2
}

exit 0
