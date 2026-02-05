@echo off
setlocal enabledelayedexpansion

:: Usage: setup.bat [--skip-clone | --install-only | -s]
::   No args    : Interactive menu
::   --skip-clone, --install-only, -s : Skip git operations, install only

echo ============================================
echo   RPX - Raptor X Setup Script
echo ============================================
echo.

:: Configuration
set REPO_URL=https://github.com/ShreyX24/RP-X-temp.git
set REPO_NAME=RPX
set GDRIVE_FILE_ID=1Otyc6swsZkzNyDHdPvPIXbyCky6QhNkg
set WEIGHTS_FILE=weights.zip

:: Check for --skip-clone or --install-only flag
if "%1"=="--skip-clone" goto :install_only
if "%1"=="--install-only" goto :install_only
if "%1"=="-s" goto :install_only

:: Interactive menu if no arguments
echo Select setup mode:
echo   [1] Full setup (clone/update repos + install)
echo   [2] Install only (skip git operations)
echo.
set /p SETUP_MODE="Enter choice (1 or 2): "

if "%SETUP_MODE%"=="2" goto :install_only

:: ============================================
:: FULL SETUP MODE
:: ============================================

:: Check if we're already inside RPX directory (validate with rpx-core)
if exist ".git" if exist "rpx-core" (
    echo Current directory: %CD%
    echo.
    goto :update_existing
)

:: Check if RPX folder exists in current directory (validate with rpx-core)
if exist "%REPO_NAME%\rpx-core" (
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
echo [1/7] Fetching latest branches...
git fetch --all --prune
if errorlevel 1 (
    echo [WARNING] Failed to fetch, continuing anyway...
)

echo.
echo Available branches (sorted by most recent):
echo ----------------------------------------

:: Build numbered list of remote branches sorted by most recent commit
set BRANCH_COUNT=0
for /f "tokens=1,2" %%A in ('git for-each-ref --sort=-committerdate refs/remotes/origin/ --format="%%(refname:short) %%(committerdate:short)"') do (
    set "RAW_BRANCH=%%A"
    set "BRANCH_DATE=%%B"

    :: Skip origin/HEAD
    if /i not "!RAW_BRANCH!"=="origin/HEAD" (
        :: Strip origin/ prefix
        set "BRANCH_NAME=!RAW_BRANCH:origin/=!"
        set /a BRANCH_COUNT+=1
        set "BRANCH_!BRANCH_COUNT!=!BRANCH_NAME!"
        if !BRANCH_COUNT! LEQ 9 (
            echo   [!BRANCH_COUNT!] !BRANCH_NAME! ^(!BRANCH_DATE!^)
        )
    )
)

if !BRANCH_COUNT! GTR 9 (
    echo.
    echo   ... and !BRANCH_COUNT! total branches ^(showing top 9^)
)

echo.
set /p BRANCH_CHOICE="Select branch number [1]: "
if "!BRANCH_CHOICE!"=="" set BRANCH_CHOICE=1

:: Validate selection
set "SELECTED_BRANCH=!BRANCH_%BRANCH_CHOICE%!"
if "!SELECTED_BRANCH!"=="" (
    echo [WARNING] Invalid selection, defaulting to branch 1
    set "SELECTED_BRANCH=!BRANCH_1!"
)

echo.
echo Switching to branch: !SELECTED_BRANCH!
git checkout !SELECTED_BRANCH!
if errorlevel 1 (
    echo [WARNING] Failed to checkout !SELECTED_BRANCH!, continuing anyway...
)
git pull origin !SELECTED_BRANCH!
if errorlevel 1 (
    echo [WARNING] Failed to pull, continuing anyway...
)

echo.
echo [2/7] Initializing and updating submodules...
git submodule init
git submodule update --recursive

:: Check if submodules exist, if not clone them
if not exist "omniparser-server\.git" (
    echo Cloning OmniParser server...
    git clone https://github.com/YpS-YpS/OmniLocal.git "omniparser-server"
)

if not exist "preset-manager\.git" (
    echo Cloning preset-manager...
    git clone https://github.com/ShreyX24/preset-manager.git preset-manager
)

echo.
echo [3/7] Downloading OmniParser weights...
if exist "omniparser-server\weights\icon_detect\model.pt" (
    echo [OK] Weights already exist, skipping download
    goto :skip_weights
)

echo Downloading weights from Google Drive (~1.5GB)...
echo This may take a few minutes...

cd "omniparser-server"

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
goto :install_dependencies

:: ============================================
:: INSTALL ONLY MODE (skip git operations)
:: ============================================
:install_only
echo.
echo ============================================
echo   Install Only Mode
echo ============================================
echo Skipping: git clone, git pull, submodule updates, weights download
echo.

:: Verify we're in the right directory
if not exist "rpx-core" (
    echo [ERROR] Not in RPX directory. Please run from the RPX root folder.
    echo Expected to find 'rpx-core' folder.
    pause
    exit /b 1
)

:install_dependencies

echo.
echo ----------------------------------------
echo   Installing NPM Dependencies
echo ----------------------------------------
echo.
echo Installing RPX Admin dependencies...
if exist "rpx-core\admin\package.json" (
    cd rpx-core\admin
    call npm install
    if errorlevel 1 (
        echo [WARNING] npm install failed for RPX admin
    ) else (
        echo [OK] RPX admin dependencies installed
    )
    cd ..\..
) else (
    echo [WARNING] rpx-core/admin/package.json not found
)

echo.
echo Installing Preset Manager Admin dependencies...
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
echo ----------------------------------------
echo   Installing Python Services (pip -e)
echo ----------------------------------------

echo Installing RPX Backend...
pip install -e rpx-core
if errorlevel 1 (
    echo [WARNING] Failed to install RPX backend
) else (
    echo [OK] RPX backend installed
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

echo Installing SUT Client...
pip install -e sut_client
if errorlevel 1 (
    echo [WARNING] Failed to install SUT Client
) else (
    echo [OK] SUT Client installed
)

echo Installing Preset Manager...
pip install -e preset-manager
if errorlevel 1 (
    echo [WARNING] Failed to install Preset Manager
) else (
    echo [OK] Preset Manager installed
)

echo.
echo ----------------------------------------
echo   OmniParser Setup (Optional)
echo ----------------------------------------
echo.
echo OmniParser requires Python 3.12 + CUDA 12.8 + PyTorch 2.8.0
echo It will install ~2GB of dependencies + flash-attention wheel.
echo.
set /p INSTALL_OMNI="Install OmniParser dependencies? (y/n) [n]: "
if /i "!INSTALL_OMNI!"=="y" (
    if exist "omniparser-server\install.bat" (
        echo.
        cd omniparser-server
        call install.bat
        cd ..
    ) else (
        echo [WARNING] omniparser-server/install.bat not found, skipping
    )
) else (
    echo Skipping OmniParser setup.
)

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo To start RPX, double-click: start-rpx.bat
echo.
pause
