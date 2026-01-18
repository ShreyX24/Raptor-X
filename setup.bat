@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   RPX - Raptor X Setup Script
echo ============================================
echo.

:: Configuration
set REPO_URL=https://github.com/ShreyX24/RP-X-temp.git
set REPO_NAME=RPX
set GDRIVE_FILE_ID=1Otyc6swsZkzNyDHdPvPIXbyCky6QhNkg
set WEIGHTS_FILE=weights.zip

:: Check if we're already inside RPX directory
if exist ".git" (
    for %%I in (.) do set CURRENT_DIR=%%~nxI
    echo Current directory: %CD%
    echo.
    goto :update_existing
)

:: Check if RPX folder exists in current directory
if exist "%REPO_NAME%" (
    echo Found existing %REPO_NAME% folder, updating...
    cd "%REPO_NAME%"
    goto :update_existing
)

:: Clone fresh
echo Cloning RPX repository...
git clone %REPO_URL% %REPO_NAME%
if errorlevel 1 (
    echo [ERROR] Failed to clone repository
    pause
    exit /b 1
)
cd "%REPO_NAME%"

:update_existing
echo.
echo [1/4] Pulling latest changes...
git pull origin master
if errorlevel 1 (
    echo [WARNING] Failed to pull, continuing anyway...
)

echo.
echo [2/4] Initializing and updating submodules...
git submodule init
git submodule update --recursive

:: Check if submodules exist, if not clone them
if not exist "omniparser-server\.git" (
    if not exist "Omniparser server\.git" (
        echo Cloning omniparser-server...
        git clone https://github.com/YpS-YpS/OmniLocal.git "omniparser-server"
    )
)

if not exist "preset-manager\.git" (
    echo Cloning preset-manager...
    git clone https://github.com/ShreyX24/preset-manager.git preset-manager
)

echo.
echo [3/4] Downloading OmniParser weights...

:: Check both possible locations
set WEIGHTS_EXIST=0
if exist "omniparser-server\weights\icon_detect\model.pt" set WEIGHTS_EXIST=1
if exist "Omniparser server\weights\icon_detect\model.pt" set WEIGHTS_EXIST=1

if %WEIGHTS_EXIST%==1 (
    echo [OK] Weights already exist, skipping download
    goto :skip_weights
)

echo Downloading weights from Google Drive (~1.5GB)...
echo This may take a few minutes...

:: Determine which omniparser directory exists
set OMNI_DIR=omniparser-server
if not exist "omniparser-server" (
    if exist "Omniparser server" (
        set OMNI_DIR=Omniparser server
    )
)

cd "%OMNI_DIR%"

:: Google Drive large file download requires two steps:
:: 1. First request gets a warning page with UUID
:: 2. Second request uses UUID to download actual file

echo Step 1: Getting download token...
curl -s -L -c gdrive_cookies.txt "https://drive.google.com/uc?export=download&id=%GDRIVE_FILE_ID%" -o gdrive_warning.html

:: Extract UUID from the warning page
set "UUID="
for /f "tokens=2 delims==" %%a in ('findstr /i "uuid" gdrive_warning.html 2^>nul') do (
    for /f "tokens=1 delims=&" %%b in ("%%a") do set "UUID=%%~b"
)

if defined UUID (
    echo Step 2: Downloading with token...
    curl -L -b gdrive_cookies.txt -o "%WEIGHTS_FILE%" "https://drive.usercontent.google.com/download?id=%GDRIVE_FILE_ID%&export=download&confirm=t&uuid=!UUID!"
) else (
    echo Step 2: Trying direct download...
    curl -L -b gdrive_cookies.txt -o "%WEIGHTS_FILE%" "https://drive.usercontent.google.com/download?id=%GDRIVE_FILE_ID%&export=download&confirm=t"
)

:: Cleanup temp files
del gdrive_cookies.txt 2>nul
del gdrive_warning.html 2>nul

:: Check if download succeeded
if not exist "%WEIGHTS_FILE%" goto :download_failed

:: Check file size (should be > 100MB for valid download)
set "FILESIZE=0"
for %%F in ("%WEIGHTS_FILE%") do set FILESIZE=%%~zF
if !FILESIZE! LSS 100000000 (
    echo [WARNING] Downloaded file too small, may be HTML error page
    del "%WEIGHTS_FILE%"
    goto :download_failed
)

echo Extracting weights...
powershell -Command "Expand-Archive -Path '%WEIGHTS_FILE%' -DestinationPath '.' -Force"
del "%WEIGHTS_FILE%"
echo [OK] Weights downloaded and extracted
cd ..
goto :skip_weights

:download_failed
echo [WARNING] Failed to download weights
echo Please download manually from:
echo https://drive.google.com/file/d/%GDRIVE_FILE_ID%/view
echo.
echo After downloading, extract weights.zip into "omniparser-server" folder
cd ..

:skip_weights

echo.
echo [4/4] Running RPX Unified Installer...
echo.

:: Run the Python installer (handles SSH, npm, pip installs)
python rpx_installer.py
if errorlevel 1 (
    echo.
    echo [WARNING] Some components may have failed to install.
    echo Check the output above for details.
)

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo To start RPX, double-click: start-rpx.bat
echo Or run: rpx-manager
echo.
pause
