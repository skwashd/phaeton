#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TODO="$SCRIPT_DIR/TODO.md"

while true; do
  # Read first non-empty line from TODO.md
  NEXT=$(sed -n '/\S/{ p; q; }' "$TODO")
  [ -z "$NEXT" ] && break

  echo "=== Processing: $NEXT ==="

  claude --dangerously-skip-permissions -p "Take $NEXT and implement it. Do no work on any other tasks. Only implement the work requested in the file. When the task is complete, move the file to tasks/complete/. Append the filename to the end of the list in tasks/complete/DONE.md and remove it from tasks/TODO.md. This ensures outstanding tasks are properly tracked."

  echo "=== Completed: $NEXT ==="
done

echo "All tasks complete."
