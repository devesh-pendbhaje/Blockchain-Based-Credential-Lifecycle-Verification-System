#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/backend/.venv/Scripts/python.exe" ]; then
    PYTHON_CMD="$SCRIPT_DIR/backend/.venv/Scripts/python.exe"
else
    PYTHON_CMD="$SCRIPT_DIR/backend/.venv/bin/python"
fi
if [ ! -f "$PYTHON_CMD" ]; then
    echo "Install dependencies first: see README.md (Local quick start)."
    exit 1
fi
exec "$PYTHON_CMD" -u "$SCRIPT_DIR/scripts/local_stack.py" "${1:-start}"
