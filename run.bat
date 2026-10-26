@echo off
REM ==============================================================================
REM Blockchain-Based Credential Lifecycle Verification System
REM Windows Batch Launcher (Calls PowerShell run.ps1)
REM ==============================================================================

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%run.ps1" %*
