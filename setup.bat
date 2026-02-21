@echo off
setlocal

:: ── RPX Setup Launcher ──────────────────────────────────────────────
:: Thin ignition: elevates privileges, checks Python, then launches
:: setup.py in Windows Terminal for proper ANSI + Unicode rendering.
:: Falls back to current cmd window if wt.exe is unavailable.
:: Usage: setup.bat [--skip-clone | --install-only | -s]

:: Ensure working directory is script location (elevated cmd starts in System32)
cd /d "%~dp0"

:: ── Self-elevate if not admin ───────────────────────────────────────
net session >nul 2>&1
if errorlevel 1 (
    echo Requesting administrator privileges...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "Start-Process -FilePath '%~f0' -ArgumentList '%*' -Verb RunAs"
    exit /b
)

:: ── Check Python ────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ and add to PATH.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: ── Launch in best available terminal ───────────────────────────────
:: Windows Terminal (wt.exe) renders colors, Unicode, and interactive
:: selectors perfectly. The bat window closes after handoff.

where wt.exe >nul 2>&1
if not errorlevel 1 (
    wt.exe --title "Raptor X" -d "%~dp0" -- cmd /c "python setup.py %* & echo. & pause"
    exit /b
)

:: Fallback: run in current cmd window
python "%~dp0setup.py" %*
echo.
pause
