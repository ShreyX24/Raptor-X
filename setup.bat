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
echo [1/7] Pulling latest changes...
git pull origin master
if errorlevel 1 (
    echo [WARNING] Failed to pull, continuing anyway...
)

echo.
echo [2/7] Initializing and updating submodules...
git submodule init
git submodule update --recursive

:: Check if submodules exist, if not clone them
if not exist "Omniparser server\.git" (
    echo Cloning Omniparser server...
    git clone https://github.com/YpS-YpS/OmniLocal.git "Omniparser server"
)

if not exist "preset-manager\.git" (
    echo Cloning preset-manager...
    git clone https://github.com/ShreyX24/preset-manager.git preset-manager
)

echo.
echo [3/7] Downloading OmniParser weights...
if exist "Omniparser server\weights\icon_detect\model.pt" (
    echo [OK] Weights already exist, skipping download
) else (
    echo Downloading weights from Google Drive (~1.5GB)...
    echo This may take a few minutes...

    cd "Omniparser server"

    :: Google Drive large file download requires two steps:
    :: 1. First request gets a warning page with UUID
    :: 2. Second request uses UUID to download actual file

    echo Step 1: Getting download token...
    curl -s -L -c gdrive_cookies.txt "https://drive.google.com/uc?export=download&id=%GDRIVE_FILE_ID%" -o gdrive_warning.html

    :: Extract UUID from the warning page
    for /f "tokens=2 delims==" %%a in ('findstr /i "uuid" gdrive_warning.html 2^>nul') do (
        set "UUID_RAW=%%a"
    )
    :: Clean up UUID (remove quotes and ampersand suffix)
    if defined UUID_RAW (
        for /f "tokens=1 delims=&" %%b in ("!UUID_RAW!") do set "UUID=%%~b"
    )

    if defined UUID (
        echo Step 2: Downloading with token...
        curl -L -b gdrive_cookies.txt -o "%WEIGHTS_FILE%" "https://drive.usercontent.google.com/download?id=%GDRIVE_FILE_ID%&export=download&confirm=t&uuid=!UUID!"
    ) else (
        :: Fallback: try direct download with confirm=t
        echo Step 2: Trying direct download...
        curl -L -b gdrive_cookies.txt -o "%WEIGHTS_FILE%" "https://drive.usercontent.google.com/download?id=%GDRIVE_FILE_ID%&export=download&confirm=t"
    )

    :: Cleanup temp files
    del gdrive_cookies.txt 2>nul
    del gdrive_warning.html 2>nul

    if exist "%WEIGHTS_FILE%" (
        :: Check file size (should be > 100MB for valid download)
        for %%F in ("%WEIGHTS_FILE%") do set FILESIZE=%%~zF
        if !FILESIZE! GTR 100000000 (
            echo Extracting weights...
            powershell -Command "Expand-Archive -Path '%WEIGHTS_FILE%' -DestinationPath '.' -Force"
            del "%WEIGHTS_FILE%"
            echo [OK] Weights downloaded and extracted
        ) else (
            echo [WARNING] Downloaded file too small, may be HTML error page
            del "%WEIGHTS_FILE%"
            goto :manual_download
        )
    ) else (
        :manual_download
        echo [WARNING] Failed to download weights
        echo Please download manually from:
        echo https://drive.google.com/file/d/%GDRIVE_FILE_ID%/view
        echo.
        echo After downloading, extract weights.zip into "Omniparser server" folder
    )
    cd ..
)

echo.
echo [4/7] Installing Gemma Admin dependencies...
if exist "Gemma\admin\package.json" (
    cd Gemma\admin
    call npm install
    if errorlevel 1 (
        echo [WARNING] npm install failed for Gemma admin
    ) else (
        echo [OK] Gemma admin dependencies installed
    )
    cd ..\..
) else (
    echo [WARNING] Gemma/admin/package.json not found
)

echo.
echo [5/7] Installing Preset Manager Admin dependencies...
if exist "preset-manager\admin\package.json" (
    cd preset-manager\admin
    call npm install
    if errorlevel 1 (
        echo [WARNING] npm install failed for preset-manager admin
    ) else (
        echo [OK] Preset Manager admin dependencies installed
    )
    cd ..\..
) else (
    echo [WARNING] preset-manager/admin/package.json not found
)

echo.
echo [6/7] Installing Python services...

echo Installing Gemma Backend...
pip install -e Gemma\backend
if errorlevel 1 (
    echo [WARNING] Failed to install Gemma backend
) else (
    echo [OK] Gemma backend installed
)

echo Installing SUT Discovery Service...
pip install -e sut_discovery_service
if errorlevel 1 (
    echo [WARNING] Failed to install SUT Discovery
) else (
    echo [OK] SUT Discovery installed
)

echo Installing Queue Service...
pip install -e queue_service
if errorlevel 1 (
    echo [WARNING] Failed to install Queue Service
) else (
    echo [OK] Queue Service installed
)

echo Installing Service Manager...
pip install -e service_manager
if errorlevel 1 (
    echo [WARNING] Failed to install Service Manager
) else (
    echo [OK] Service Manager installed
)

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo [7/7] Launching Service Manager...
echo.
gemma-manager
