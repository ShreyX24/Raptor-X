@echo off
:: Launch RPX Service Manager and close this terminal
:: Using 'start' with pythonw or direct command to avoid keeping terminal open

:: Try rpx-manager command (installed via pip)
where rpx-manager >nul 2>&1
if %errorlevel%==0 (
    start "" rpx-manager
    exit
)

:: Fallback to gemma-manager (old name)
where gemma-manager >nul 2>&1
if %errorlevel%==0 (
    start "" gemma-manager
    exit
)

:: Fallback to running the module directly with pythonw (no console)
start "" pythonw -m service_manager
exit
