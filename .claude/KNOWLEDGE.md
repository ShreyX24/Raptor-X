# Gemma E2E Test Environment Knowledge Base

## SSH Access to SUT (Gaming Machine)

### ZEL-X7 (Gaming SUT)
- **IP**: 192.168.0.102
- **Username**: shrey
- **SSH Port**: 22
- **Auth**: SSH key (pubkey in `C:\ProgramData\ssh\administrators_authorized_keys`)

### SSH Commands
```bash
# Connect to SUT
ssh shrey@192.168.0.102

# Run commands remotely
ssh shrey@192.168.0.102 "command here"

# Copy files to SUT
scp -r local_path shrey@192.168.0.102:"D:/Code/Gemma/destination"

# Check SUT processes
ssh shrey@192.168.0.102 "tasklist | findstr python"

# Kill process on SUT
ssh shrey@192.168.0.102 "taskkill /F /IM python.exe"
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
| SUT Client | 8080 | 192.168.0.102 (ZEL-X7) |

## API Endpoints

### Start Automation Run
```bash
curl -X POST "http://localhost:5000/api/runs" \
  -H "Content-Type: application/json" \
  -d '{"sut_ip": "192.168.0.102", "game_name": "Shadow of the Tomb Raider", "iterations": 1}'
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
curl -X POST "http://192.168.0.102:8080/kill" \
  -H "Content-Type: application/json" \
  -d '{"process_name": "SOTTR"}'
```

### Check SUT Health
```bash
curl -s http://192.168.0.102:8080/health
```

### Check Discovery Service
```bash
curl -s http://localhost:5001/api/suts | python -m json.tool
```

## Troubleshooting

### SUT Not Responding
1. Check if SUT client is running: `ssh shrey@192.168.0.102 "tasklist | findstr python"`
2. Restart SUT client via SSH or batch file
3. Verify firewall rules are in place

### SSH Connection Issues
1. Verify OpenSSH Server running on SUT: `Get-Service sshd`
2. Check network profile is Private: `Get-NetConnectionProfile`
3. Verify authorized_keys file: `C:\ProgramData\ssh\administrators_authorized_keys`

### OmniParser Issues
1. Check queue service health: `curl http://localhost:9000/health`
2. Check probe endpoint: `curl http://localhost:9000/probe`
