@echo off
REM ============================================================================
REM  RAPTOR X SUT Client Restarter
REM  Called after updates to restart the SUT client service
REM ============================================================================

title RPX SUT Client Restarter
color 0A

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║              RAPTOR X SUT CLIENT RESTARTER                   ║
echo  ╠══════════════════════════════════════════════════════════════╣
echo  ║  This script will restart the SUT client after updates.     ║
echo  ║  Please wait...                                              ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

REM Step 1: Wait 5 seconds for calling process to exit
echo [1/4] Waiting 5 seconds for processes to cleanup...
timeout /t 5 /nobreak > nul
echo      Done.
echo.

REM Step 2: Kill any existing sut-client processes
echo [2/4] Stopping existing SUT client processes...

REM Kill by process name (pythonw.exe running sut-client or sut_client)
taskkill /F /IM "sut-client.exe" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo      Killed sut-client.exe
) else (
    echo      No sut-client.exe found
)

REM Also try to kill Python processes running sut_client
REM This is a bit aggressive but ensures clean restart
for /f "tokens=2" %%i in ('wmic process where "commandline like '%%sut_client%%' and name='python.exe'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /F /PID %%i 2>nul
    echo      Killed Python process %%i
)

echo      Done.
echo.

REM Step 3: Clear Python cache
echo [3/4] Clearing Python cache...

REM Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"
set "SUT_CLIENT_DIR=%SCRIPT_DIR%src\sut_client"

REM Clear __pycache__ directories
if exist "%SUT_CLIENT_DIR%" (
    for /d /r "%SUT_CLIENT_DIR%" %%d in (__pycache__) do (
        if exist "%%d" (
            rd /s /q "%%d" 2>nul
            echo      Cleared: %%d
        )
    )
)

REM Also clear .pyc files
del /s /q "%SUT_CLIENT_DIR%\*.pyc" 2>nul

echo      Cache cleared.
echo.

REM Step 4: Start SUT client
echo [4/4] Starting SUT client...

REM Find sut-client executable
where sut-client >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo      Found sut-client in PATH
    start "SUT Client" cmd /c "sut-client"
) else (
    REM Try running as Python module
    echo      Running as Python module...
    start "SUT Client" cmd /c "python -m sut_client"
)

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║                    RESTART COMPLETE!                         ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

REM Auto-close after 3 seconds
echo This window will close in 3 seconds...
timeout /t 3 /nobreak > nul
exit
