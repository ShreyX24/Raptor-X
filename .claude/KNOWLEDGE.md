# Gemma E2E Test Environment Knowledge Base

## SSH Access to SUT (Gaming Machine)

### ZEL-X7 (Gaming SUT)
- **IP**: 192.168.0.106
- **Username**: shrey
- **SSH Port**: 22
- **Auth**: SSH key (pubkey in `C:\ProgramData\ssh\administrators_authorized_keys`)

### SSH Commands
```bash
# Connect to SUT
ssh shrey@192.168.0.106

# Run commands remotely
ssh shrey@192.168.0.106 "command here"

# Copy files to SUT
scp -r local_path shrey@192.168.0.106:"D:/Code/Gemma/destination"

# Check SUT processes
ssh shrey@192.168.0.106 "tasklist | findstr python"

# Kill process on SUT
ssh shrey@192.168.0.106 "taskkill /F /IM python.exe"
```

### SUT Client Location
- **Path**: `D:\Code\Gemma\sut_client`
- **Start Command**: `cd /d D:\Code\Gemma\sut_client && set PYTHONPATH=src && python -m sut_client`
- **Batch File**: `D:\Code\Gemma\start_sut.bat`

## Services Overview

### Backend Services (This Machine - ZEL-X2)
| Service | Port | Command |
|---------|------|---------|
| SUT Discovery | 5001 | `PYTHONPATH=src python -m sut_discovery_service` |
| Queue Service | 9000 | `PYTHONPATH=src OMNIPARSER_URLS=http://192.168.0.103:8000,http://192.168.0.103:8001 python -m queue_service` |
| Gemma Backend | 5000 | `cd Gemma/backend && python server.py` |
| Preset Manager | 5002 | `cd preset-manager && PYTHONPATH=src python -m preset_manager` |

### Frontend Services
| Service | Port | Command |
|---------|------|---------|
| Gemma Frontend | 3000 | `cd Gemma/admin && npm run dev` |
| PM Frontend | 3001 | `cd preset-manager/preset-manager-ui && npm run dev` |

### External Services
| Service | Port | Location |
|---------|------|----------|
| OmniParser 1 | 8000 | 192.168.0.103 |
| OmniParser 2 | 8001 | 192.168.0.103 |
| SUT Client | 8080 | 192.168.0.106 (ZEL-X7) |

## API Endpoints

### Start Automation Run
```bash
curl -X POST "http://localhost:5000/api/runs" \
  -H "Content-Type: application/json" \
  -d '{"sut_ip": "192.168.0.106", "game_name": "Shadow of the Tomb Raider", "iterations": 1}'
```

### Check Run Status
```bash
curl -s http://localhost:5000/api/runs/<run_id> | python -m json.tool
```

### List Games
```bash
curl -s http://localhost:5000/api/games | python -m json.tool
```

### Reload Game Configs
```bash
curl -X POST http://localhost:5000/api/games/reload
```

### Kill Game on SUT
```bash
curl -X POST "http://192.168.0.106:8080/kill" \
  -H "Content-Type: application/json" \
  -d '{"process_name": "SOTTR"}'
```

### Check SUT Health
```bash
curl -s http://192.168.0.106:8080/health
```

### Check Discovery Service
```bash
curl -s http://localhost:5001/api/suts | python -m json.tool
```

## Troubleshooting

### SUT Not Responding
1. Check if SUT client is running: `ssh shrey@192.168.0.106 "tasklist | findstr python"`
2. Restart SUT client via SSH or batch file
3. Verify firewall rules are in place

### SSH Connection Issues
1. Verify OpenSSH Server running on SUT: `Get-Service sshd`
2. Check network profile is Private: `Get-NetConnectionProfile`
3. Verify authorized_keys file: `C:\ProgramData\ssh\administrators_authorized_keys`

### OmniParser Issues
1. Check queue service health: `curl http://localhost:9000/health`
2. Check probe endpoint: `curl http://localhost:9000/probe`

## Running Backends in Claude Code Background Tasks

Use these commands with `run_in_background: true` to start services without opening terminal windows.

### OmniParser (Port 8100)
```bash
cd "/c/Users/shrey/OneDrive/Documents/Code/Gemma/RPX/omniparser-server/omnitool/omniparserserver" && python -c "import uvicorn; from omniparserserver import app; uvicorn.run(app, host='0.0.0.0', port=8100)"
```

### Queue Service (Port 9000)
```bash
cd /c/Users/shrey/OneDrive/Documents/Code/Gemma/RPX/queue_service && PYTHONPATH=src OMNIPARSER_URLS=http://localhost:8100 python -m queue_service
```

### Gemma Backend (Port 5000)
```bash
cd /c/Users/shrey/OneDrive/Documents/Code/Gemma/RPX/Gemma && gemma
```

### SUT Discovery (Port 5001)
```bash
cd /c/Users/shrey/OneDrive/Documents/Code/Gemma/RPX/sut_discovery_service && PYTHONPATH=src python -m sut_discovery_service
```

### Preset Manager (Port 5002)
```bash
cd /c/Users/shrey/OneDrive/Documents/Code/Gemma/RPX/preset-manager && PYTHONPATH=src python -m preset_manager
```

### Gemma Frontend (Port 3000)
```bash
cd /c/Users/shrey/OneDrive/Documents/Code/Gemma/RPX/Gemma/admin && npm run dev
```

### Verify All Services
```bash
curl -s http://localhost:8100/probe/ && \
curl -s http://localhost:9000/health && \
curl -s http://localhost:5000/api/health && \
curl -s http://localhost:5001/api/health && \
curl -s http://localhost:5002/api/health
```

**Note**: Use Unix-style paths (`/c/Users/...`) for Git Bash compatibility in background tasks.

## Timeline Storage Architecture

### Directory Structure

```
Gemma/logs/runs/
├── 2026-01-02_033449_14600KF_192-168-0-106_single-Far Cry 6/
│   ├── timeline.json          # Single file with ALL events for this run
│   └── screenshots/           # Screenshots captured during run
│
├── 2026-01-01_Test-Campaign_192-168-0-102/    # Campaign directory
│   ├── campaign_manifest.json                  # Campaign metadata
│   ├── 2026-01-01_150405_..._single-Cyberpunk 2077/
│   │   └── timeline.json                       # Run 1 timeline
│   └── 2026-01-01_150537_..._single-Far Cry 6/
│       └── timeline.json                       # Run 2 timeline
```

### Single Run (Multiple Iterations)

- **One timeline.json per run** - contains ALL iterations in a single flat array
- Events are stored in **arrival order** (NOT chronological!)
- Frontend must **sort by timestamp** before grouping by iteration

### Iteration Boundaries

- `iteration_started` event marks **START** of iteration
- `iteration_completed` event marks **END** and **REPLACES** `iteration_started`
- Events between boundaries belong to that iteration

Example event sequence (by timestamp):
```
iteration_1 (started) → [setup events] → [step events] → iteration_1_done
iteration_2 (started) → [setup events] → [step events] → iteration_2_done
iteration_3 (started) → [setup events] → [step events] → iteration_3_done
```

### Campaign Structure

- Campaign = parent directory containing multiple run directories
- Each game in campaign has its own run directory with own timeline.json
- campaign_manifest.json tracks campaign metadata

### Event Schema

```json
{
  "event_id": "step_1",
  "event_type": "step_started",
  "message": "Step 1/7: Click OPTIONS",
  "timestamp": "2026-01-02T03:51:04.640248",
  "status": "in_progress|completed|failed|skipped",
  "duration_ms": null,
  "metadata": { "step": 1, "total": 7 },
  "replaces_event_id": null,
  "group": "steps"
}
```

### Key Event Types

| Event Type | Description |
|------------|-------------|
| run_started | Run begins |
| run_completed/run_failed | Run ends |
| iteration_started | Iteration N begins |
| iteration_completed | Iteration N ends (replaces iteration_N) |
| step_started | Automation step begins |
| step_completed | Step ends (replaces step_N) |
| game_launching | Game launch initiated |
| game_launched | Game process detected |
| steam_dialog_detected | Steam dialog found |

### Frontend Grouping Logic (SnakeTimeline)

1. **Sort events by timestamp** (critical - events are stored in arrival order!)
2. Track `currentIteration` starting at 1
3. When `iteration_started` seen → set `currentIteration = N`
4. When `iteration_completed` seen → add to iteration N, then `currentIteration = N + 1`
5. All other events go to `currentIteration`
