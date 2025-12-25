# Gemma Service Launcher - 4 Separate Windows with Tabs
#
# Layout:
# +---------------------------+---------------------------+
# | Gemma Window              | SUT Discovery Window      |
# |  Tab 1: Backend (5000)    |  Single tab (5001)        |
# |  Tab 2: Frontend (3000)   |                           |
# +---------------------------+---------------------------+
# | Queue Service Window      | Preset Manager Window     |
# |  Single tab (9000)        |  Tab 1: Backend (5002)    |
# |                           |  Tab 2: Frontend (3001)   |
# +---------------------------+---------------------------+

Write-Host "Starting Gemma services (4 windows)..." -ForegroundColor Cyan
Write-Host ""

# Get screen working area (excludes taskbar)
Add-Type -AssemblyName System.Windows.Forms
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea

$halfW = [math]::Floor($screen.Width / 2)
$halfH = [math]::Floor($screen.Height / 2)

Write-Host "Screen: $($screen.Width)x$($screen.Height) -> Positions: (0,0), ($halfW,0), (0,$halfH), ($halfW,$halfH)" -ForegroundColor DarkGray

$base = "D:\Code\Gemma"

# Top-Left: Gemma (backend + frontend with delayed start)
# Frontend waits 8 seconds for backend to be ready
$cmd1 = "wt -w new --pos 0,0 --title `"gemma [backend]`" -d `"$base\Gemma`" cmd /k gemma --port 5000 `; nt --title `"gemma [frontend]`" -d `"$base\Gemma\admin`" cmd /k `"timeout /t 8 /nobreak >nul && npm run dev -- --host`""
Start-Process cmd -ArgumentList "/c", $cmd1
Start-Sleep -Milliseconds 500

# Top-Right: SUT Discovery
$cmd2 = "wt -w new --pos $halfW,0 --title `"sut-discovery [5001]`" -d `"$base\sut_discovery_service`" cmd /k sut-discovery --port 5001"
Start-Process cmd -ArgumentList "/c", $cmd2
Start-Sleep -Milliseconds 500

# Bottom-Left: Queue Service (backend + dashboard with delayed start)
$cmd3 = "wt -w new --pos 0,$halfH --title `"queue-service [9000]`" -d `"$base\queue_service`" cmd /k queue-service --port 9000 `; nt --title `"queue-service [dashboard]`" -d `"$base\queue_service`" cmd /k `"timeout /t 8 /nobreak >nul && queue-dashboard --url http://localhost:9000`""
Start-Process cmd -ArgumentList "/c", $cmd3
Start-Sleep -Milliseconds 500

# Bottom-Right: Preset Manager (backend + frontend with delayed start)
$cmd4 = "wt -w new --pos $halfW,$halfH --title `"preset-manager [backend]`" -d `"$base\preset-manager`" cmd /k preset-manager --port 5002 `; nt --title `"preset-manager [frontend]`" -d `"$base\preset-manager\admin`" cmd /k `"timeout /t 8 /nobreak >nul && npm run dev -- --host --port 3001`""
Start-Process cmd -ArgumentList "/c", $cmd4

Write-Host ""
Write-Host "4 Windows launched:" -ForegroundColor Green
Write-Host "  [Top-Left]     Gemma Window:          Tabs: [backend 5000] [frontend 3000]"
Write-Host "  [Top-Right]    SUT Discovery Window:  Tab:  [5001]"
Write-Host "  [Bottom-Left]  Queue Service Window:  Tabs: [9000] [dashboard]"
Write-Host "  [Bottom-Right] PM Window:             Tabs: [backend 5002] [frontend 3001]"
Write-Host ""
Write-Host "Tip: Use Win+Arrow keys to snap windows to quadrants" -ForegroundColor DarkGray
