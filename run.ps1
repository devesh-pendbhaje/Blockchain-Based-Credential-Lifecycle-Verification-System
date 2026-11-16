param([ValidateSet("start", "stop", "status")][string]$Command = "start")
$ErrorActionPreference = "Stop"
$PythonPath = Join-Path $PSScriptRoot "backend/.venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Install dependencies first: see README.md (Local quick start)."
}
& $PythonPath -u (Join-Path $PSScriptRoot "scripts/local_stack.py") $Command
exit $LASTEXITCODE
