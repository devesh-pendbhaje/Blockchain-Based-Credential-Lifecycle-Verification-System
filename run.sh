#!/usr/bin/env bash
# ==============================================================================
# Blockchain-Based Credential Lifecycle Verification System
# Universal Runner Script (Git Bash / WSL / Linux / macOS)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "======================================================================="
echo "   Blockchain-Based Credential Lifecycle Verification System          "
echo "   Bash Runner (Windows Git Bash / WSL / Linux)                        "
echo "======================================================================="
echo ""

# 1. Detect Python executable
if [ -f "$SCRIPT_DIR/backend/.venv/Scripts/python.exe" ]; then
    PYTHON_CMD="$SCRIPT_DIR/backend/.venv/Scripts/python.exe"
elif [ -f "$SCRIPT_DIR/backend/.venv/bin/python" ]; then
    PYTHON_CMD="$SCRIPT_DIR/backend/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "Error: Python 3 is required but was not found in PATH."
    exit 1
fi

echo "[1/3] Using Python: $($PYTHON_CMD --version) at $PYTHON_CMD"

# 2. Check Node.js and Frontend
if ! command -v node >/dev/null 2>&1; then
    echo "Error: Node.js is required but was not found in PATH."
    exit 1
fi
echo "[2/3] Using Node: $(node -v)"

if [ ! -d "$SCRIPT_DIR/frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    (cd "$SCRIPT_DIR/frontend" && npm install)
fi

# 3. Launch Services Concurrently
echo "[3/3] Starting Backend and Frontend..."
echo ""
echo "  • Frontend Web Portal:    http://localhost:5173"
echo "  • Holder Sovereign Wallet:http://localhost:5173/wallet"
echo "  • Public Verification:   http://localhost:5173/verify"
echo "  • Backend Swagger UI:     http://localhost:8000/api/v1/docs"
echo "  • Health Probe:           http://localhost:8000/health/live"
echo ""
echo "Press Ctrl+C to stop both services."
echo "-----------------------------------------------------------------------"

cleanup() {
    echo ""
    echo "Shutting down services..."
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    wait 2>/dev/null || true
    echo "Services stopped cleanly."
}

trap cleanup INT TERM EXIT

# Start Backend
"$PYTHON_CMD" -m uvicorn app.main:app --app-dir "$SCRIPT_DIR/backend" --reload --port 8000 &
BACKEND_PID=$!

# Start Frontend
(cd "$SCRIPT_DIR/frontend" && npm run dev -- --port 5173 --host) &
FRONTEND_PID=$!

wait
