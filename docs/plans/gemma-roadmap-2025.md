# Gemma E2E Automation - 2025 Roadmap

> **Created**: 2025-12-28
> **Status**: Active Development
> **Goal**: Transform Gemma into a production-ready multi-SUT benchmark automation platform

---

## Architecture Principles

### Frontend Communication Rules
**CRITICAL**: The frontend (Gemma Admin) must NEVER communicate directly with SUTs or other backend services.

```
┌─────────────┐      ┌─────────────────┐      ┌─────────────────────────┐
│   Frontend  │ ──── │  Gemma Backend  │ ──── │  SUT / Discovery /      │
│ (Admin UI)  │      │   (port 5000)   │      │  Queue / Preset Manager │
└─────────────┘      └─────────────────┘      └─────────────────────────┘
      │                      │
      │   /api/*             │   HTTP to services
      │   (proxied)          │
      └──────────────────────┘
```

**Rules**:
1. Frontend only knows about ONE backend: Gemma Backend (`/api/*`)
2. All SUT communication is proxied through Gemma Backend
3. All service communication (Discovery, Queue, Preset Manager) goes through Gemma Backend
4. Never expose SUT IPs/ports directly to browser (security + CORS)

**Endpoints for SUT access**:
- `GET /api/sut/<device_id>/status` - Status by device ID
- `GET /api/sut/<device_id>/system_info` - Hardware info by device ID
- `GET /api/sut/by-ip/<ip>/system_info` - Hardware info by IP (for run history)
- `GET /api/sut/<device_id>/screenshot` - Screenshot by device ID

---

## Current Sprint: Core Infrastructure

### 1. Persistent Run Logging Structure
**Priority**: Critical | **Status**: Planned
**Design Doc**: [run-logging-structure.md](run-logging-structure.md)

**Problem**: Runs are stored in-memory only, lost on restart. Current `logs/{game}/run_{id}/` structure is not meaningful.

**Solution**: Persistent, telemetry-rich directory structure:
```
logs/runs/{date}_{time}_{cpu}_{ip}_{type}-{game}/
├── manifest.json
├── perf-run-1/
│   ├── blackbox_perf-run1_{cpu}_{ip}_{game}.log
│   ├── screenshots/
│   └── results/
├── perf-run-2/
├── perf-run-3/
└── trace-run/  (optional: PTAT/SocWatch)
```

**Naming Convention**: `2025-12-28_163045_14600KF_192-168-0-103_single-BMW`

**Files to Create/Modify**:
```
Gemma/backend/core/run_storage.py       - NEW: RunStorageManager
Gemma/backend/core/run_manager.py       - Integrate storage
Gemma/backend/core/automation_orchestrator.py - Per-iteration logging
```

---

### 2. Fix Run Timestamps
**Priority**: Critical | **Status**: Completed

**Problem**: `started_at` and `completed_at` are null in automation runs, breaking:
- Recent runs sorting
- Duration calculation
- Time-based filtering

**Files to Modify**:
```
Gemma/backend/core/automation_orchestrator.py  - Set timestamps during execution
Gemma/backend/core/run_manager.py              - Ensure timestamps persisted
```

**Implementation**:
```python
# automation_orchestrator.py - At run start
run.started_at = datetime.utcnow().isoformat()
run_manager.update_run(run)

# At run completion
run.completed_at = datetime.utcnow().isoformat()
run_manager.update_run(run)
```

---

### 2. Windows Resolution Management
**Priority**: High | **Status**: Pending

**Problem**: Games can only render at Windows-supported resolutions. If SUT runs at 2K native but preset targets 1080p, the game won't see 1080p as an option.

**Solution**: Dynamically change Windows display resolution before game launch.

**Files to Create/Modify**:
```
sut_client/src/sut_client/display.py           - NEW: Windows resolution API
sut_client/src/sut_client/service.py           - Add /display/* endpoints
Gemma/modules/network.py                        - Add resolution methods
Gemma/backend/core/automation_orchestrator.py  - Set resolution before launch
```

**SUT Client Endpoints**:
```
GET  /display/resolutions  → List supported resolutions
GET  /display/current      → Current resolution
POST /display/resolution   → Set resolution {width, height}
```

**Windows API Implementation**:
```python
# display.py
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        # ... other fields
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
    ]

def get_supported_resolutions() -> list[dict]:
    """Enumerate all supported display modes"""
    resolutions = []
    dm = DEVMODE()
    dm.dmSize = ctypes.sizeof(DEVMODE)
    i = 0
    while user32.EnumDisplaySettingsW(None, i, ctypes.byref(dm)):
        res = {"width": dm.dmPelsWidth, "height": dm.dmPelsHeight, "refresh": dm.dmDisplayFrequency}
        if res not in resolutions:
            resolutions.append(res)
        i += 1
    return sorted(resolutions, key=lambda r: (r["width"], r["height"]), reverse=True)

def set_resolution(width: int, height: int) -> bool:
    """Change Windows display resolution"""
    dm = DEVMODE()
    dm.dmSize = ctypes.sizeof(DEVMODE)
    dm.dmPelsWidth = width
    dm.dmPelsHeight = height
    dm.dmFields = 0x00080000 | 0x00100000  # DM_PELSWIDTH | DM_PELSHEIGHT

    result = user32.ChangeDisplaySettingsW(ctypes.byref(dm), 0)
    return result == 0  # DISP_CHANGE_SUCCESSFUL
```

**Automation Flow**:
```
1. Read preset's target resolution from metadata
2. GET /display/resolutions from SUT
3. Verify target resolution is supported
4. POST /display/resolution to set it
5. Wait 2-3 seconds for display to settle
6. Launch game
7. After run, optionally restore original resolution
```

---

### 3. Steam Account Pool
**Priority**: High | **Status**: Pending (Saved plan exists)

**Problem**: Steam allows only 1 concurrent user per account. Multi-SUT automation needs account management.

**Solution**: Account pairs (A-F games / G-Z games) allocated per SUT session.

**Architecture**:
```
Service Manager UI
    └── Steam Account Pairs config (like OmniParser servers)
        └── STEAM_ACCOUNT_PAIRS env var
            └── Gemma Backend
                └── AccountPoolManager (singleton)
                    ├── acquire_account_pair(sut_id)
                    ├── release_account_pair(sut_id)
                    └── get_account_for_game(sut_id, game_name)
```

**Files to Create/Modify**:
```
service_manager/src/service_manager/settings.py          - SteamAccountPair dataclass
service_manager/src/service_manager/ui/settings_dialog.py - UI for account pairs
service_manager/src/service_manager/services/process_manager.py - Inject env var
Gemma/backend/core/account_pool.py                       - NEW: Pool manager
Gemma/backend/core/automation_orchestrator.py            - Acquire/release integration
```

**Account Assignment Logic**:
```python
def get_account_for_game(sut_id: str, game_name: str) -> tuple[str, str]:
    pair = allocations[sut_id]
    first_letter = game_name[0].upper()
    if 'A' <= first_letter <= 'F':
        return (pair.af_username, pair.af_password)
    else:
        return (pair.gz_username, pair.gz_password)
```

**Example Session**:
```
SUT-1 acquires Pair 1 (arlrauto / arlrauto1)
  → BMW (B) → uses arlrauto
  → Cyberpunk (C) → already on arlrauto, skip
  → SOTR (S) → switch to arlrauto1
  → RDR2 (R) → already on arlrauto1, skip
SUT-1 releases Pair 1
```

---

### 4. Multi-SUT Batch Runs
**Priority**: High | **Status**: Pending

**Goal**: Run same benchmark across multiple SUTs simultaneously with unified progress view.

**API Endpoints**:
```
POST /api/runs/batch
{
  "game_names": ["BMW", "RDR2", "SOTR"],
  "sut_ips": ["192.168.0.102", "192.168.0.103", "192.168.0.104"],
  "iterations": 3,
  "preset_level": "ppg-high-1080p",
  "continue_on_failure": true
}

GET /api/runs/batch/{batch_id}
{
  "batch_id": "abc123",
  "status": "running",
  "total_runs": 27,
  "completed": 12,
  "failed": 2,
  "runs": [...]
}
```

**Files to Create/Modify**:
```
Gemma/backend/api/routes.py              - Add batch endpoints
Gemma/backend/core/batch_manager.py      - NEW: Batch orchestration
Gemma/backend/core/run_manager.py        - Link runs to batch
Gemma/admin/src/pages/BatchRuns.tsx      - NEW: Batch progress UI
Gemma/admin/src/components/BatchCard.tsx - NEW: Batch progress card
```

**Execution Model**:
```
BatchManager
├── Creates N AutomationRun objects (one per SUT × game × iteration)
├── Runs in parallel per SUT (sequential per game on same SUT)
├── Tracks overall batch progress
├── Handles failures (continue or abort)
└── Reports batch-level metrics
```

**Frontend UI**:
```
┌─────────────────────────────────────────────────────────────┐
│ Batch Run: abc123                      Status: Running      │
│ Games: BMW, RDR2, SOTR (3 iterations each)                 │
├────────────────────┬────────────────────┬──────────────────┤
│ 192.168.0.102      │ 192.168.0.103      │ 192.168.0.104    │
├────────────────────┼────────────────────┼──────────────────┤
│ ✅ BMW (3/3)       │ ✅ BMW (3/3)       │ 🔄 BMW (2/3)     │
│ 🔄 RDR2 (1/3)      │ ⏳ RDR2           │ ⏳ RDR2          │
│ ⏳ SOTR            │ ⏳ SOTR           │ ⏳ SOTR          │
├────────────────────┴────────────────────┴──────────────────┤
│ Progress: 12/27 (44%)    ETA: 2h 15m                       │
│ ████████████████░░░░░░░░░░░░░░░░░░░░                       │
└─────────────────────────────────────────────────────────────┘
```

---

### 5. Real-time Automation Timeline
**Priority**: Medium | **Status**: Pending

**Goal**: Show step-by-step progress during automation with timestamps, status, and screenshots.

**Backend Changes**:
```python
# New WebSocket events
AUTOMATION_STEP_STARTED = "automation_step_started"
AUTOMATION_STEP_COMPLETED = "automation_step_completed"
AUTOMATION_STEP_FAILED = "automation_step_failed"

# Step progress payload
{
  "run_id": "abc123",
  "step_number": 3,
  "step_description": "Click GRAPHICS button",
  "status": "in_progress",
  "started_at": "2025-12-28T10:23:45",
  "screenshot_url": "/api/runs/abc123/screenshots/step_3.png"
}
```

**Files to Create/Modify**:
```
Gemma/backend/core/automation_orchestrator.py     - Emit step events
Gemma/backend/communication/websocket_handler.py  - New event types
Gemma/admin/src/components/AutomationTimeline.tsx - NEW: Timeline UI
Gemma/admin/src/components/TimelineStep.tsx       - NEW: Step node
Gemma/admin/src/components/StepScreenshot.tsx     - NEW: Screenshot preview
Gemma/admin/src/hooks/useRunProgress.ts           - NEW: WebSocket subscription
```

**Frontend Timeline UI**:
```
┌─────────────────────────────────────────────────────────────┐
│ Run: BMW on 192.168.0.102                 Status: Running   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ●────●────●────◐────○────○────○────○                      │
│  │    │    │    │                                          │
│ Launch Settings Graphics [Running] Benchmark Wait Exit      │
│ 10:20  10:22   10:24   10:26                               │
│                                                             │
│ Current: Step 4 - Click RUN BENCHMARK                       │
│ ETA: 5m 30s remaining                                       │
├─────────────────────────────────────────────────────────────┤
│ Screenshot Preview          [Full Screen]                   │
│ ┌─────────────────────────────────────────────────────────┐│
│ │                                                         ││
│ │              [Latest Screenshot]                        ││
│ │                                                         ││
│ └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

### 6. Run Scheduler
**Priority**: Medium | **Status**: Pending

**Goal**: Schedule automation runs for specific times (overnight, specific windows).

**Features**:
- One-time scheduled runs
- Recurring schedules (daily, weekly)
- Time window constraints (e.g., only run 10pm-6am)
- Queue management (pause during work hours)

**Database Schema**:
```sql
CREATE TABLE scheduled_runs (
    id TEXT PRIMARY KEY,
    name TEXT,
    game_names TEXT,          -- JSON array
    sut_ips TEXT,             -- JSON array
    iterations INTEGER,
    preset_level TEXT,

    schedule_type TEXT,       -- 'once', 'daily', 'weekly'
    scheduled_time TEXT,      -- ISO timestamp or cron expression
    time_window_start TEXT,   -- Optional: only run after this time
    time_window_end TEXT,     -- Optional: only run before this time

    status TEXT,              -- 'pending', 'running', 'completed', 'cancelled'
    last_run_at TEXT,
    next_run_at TEXT,
    created_at TEXT
);
```

**Files to Create/Modify**:
```
Gemma/backend/core/scheduler.py           - NEW: APScheduler integration
Gemma/backend/api/routes.py               - Schedule CRUD endpoints
Gemma/admin/src/pages/Scheduler.tsx       - NEW: Schedule management UI
Gemma/admin/src/components/ScheduleCard.tsx - NEW: Schedule display
```

**API Endpoints**:
```
GET    /api/schedules           - List all schedules
POST   /api/schedules           - Create schedule
GET    /api/schedules/{id}      - Get schedule details
PUT    /api/schedules/{id}      - Update schedule
DELETE /api/schedules/{id}      - Delete schedule
POST   /api/schedules/{id}/run  - Trigger immediate run
```

**Implementation**:
```python
# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

class RunScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._load_schedules_from_db()

    def schedule_run(self, schedule: ScheduledRun):
        if schedule.schedule_type == 'once':
            trigger = DateTrigger(run_date=schedule.scheduled_time)
        elif schedule.schedule_type == 'daily':
            trigger = CronTrigger(hour=schedule.hour, minute=schedule.minute)
        elif schedule.schedule_type == 'weekly':
            trigger = CronTrigger(day_of_week=schedule.day, hour=schedule.hour)

        self.scheduler.add_job(
            self._execute_scheduled_run,
            trigger=trigger,
            args=[schedule.id],
            id=schedule.id
        )
```

---

## Future Features (Backlog)

### Performance & Results
| Feature | Description | Priority |
|---------|-------------|----------|
| Benchmark Results Extraction | Parse F1 24 XML, SOTR CSV, Cyberpunk CSV | Medium |
| Results Database | SQLite/PostgreSQL for benchmark metrics | Medium |
| Intel PTAT Integration | CPU telemetry during benchmarks | Low |
| Intel SocWatch Integration | System power/thermal analysis | Low |
| Intel MEInfo Integration | Platform info extraction (ME version, SKU, etc.) | Low |
| Results Dashboard | Charts, comparisons, trends | Low |

### Frontend Enhancements
| Feature | Description | Priority |
|---------|-------------|----------|
| Workflow Builder (Web) | Replace Tkinter workflow builder | Medium |
| Live SUT Screenshot | Real-time screen view from dashboard | Medium |
| Preset Comparison | Compare results across presets | Low |
| GPU/CPU Utilization Charts | Real-time monitoring | Low |
| Export Reports | PDF/CSV benchmark reports | Low |

### Infrastructure
| Feature | Description | Priority |
|---------|-------------|----------|
| OmniParser Server Management | Start/stop from Service Manager | Medium |
| Email/Slack Notifications | Alerts on run completion/failure | Low |
| SSH-based SUT Communication | Alternative to HTTP client | Low |
| Multi-Resolution Presets | 720p, 1080p, 2K, 4K preset matrix | Low |

---

## Implementation Order

### Phase 1: Data Integrity (Week 1)
1. ✅ Fix Recent Runs table (sort, search)
2. ✅ Fix run timestamps (started_at/completed_at)
3. ✅ Expandable run details with SUT hardware info (CPU codename, GPU, RAM, OS)

### Phase 2: Multi-SUT Foundation (Week 2-3)
3. Steam Account Pool
4. Windows Resolution Management

### Phase 3: Batch Operations (Week 3-4)
5. Multi-SUT Batch Runs API
6. Batch progress UI

### Phase 4: Real-time Feedback (Week 4-5)
7. Real-time Automation Timeline
8. Step screenshots

### Phase 5: Automation (Week 5-6)
9. Run Scheduler
10. Time windows and recurring schedules

---

## Success Criteria

1. **Run timestamps working** - Duration and "When" columns show real data
2. **Resolution switching** - 1080p presets work on 2K/4K monitors
3. **3 SUTs concurrent** - Account pool prevents Steam conflicts
4. **Batch 12 games × 3 SUTs** - Unified progress view
5. **Step-by-step visibility** - See current step during automation
6. **Overnight runs** - Schedule benchmarks for off-hours

---

## Revision History

| Date | Changes |
|------|---------|
| 2025-12-28 | Initial roadmap created from doc/plans consolidation |
| 2025-12-28 | Completed: timestamps fix, expandable run details with CPU codenames, added MEInfo to backlog |
