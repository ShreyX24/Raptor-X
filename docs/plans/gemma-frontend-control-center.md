# Gemma Frontend - Comprehensive Control Center Plan

## Overview

Transform the Gemma frontend into a **one-stop control center** that exposes every feature, status, control, and signal from across the entire Gemma project.

### User Direction
- **Priority**: Full Dashboard First - comprehensive overview with all service metrics
- **PM Frontend**: Keep both - Gemma shows summary, PM Frontend for deep preset management
- **SUT Interaction**: Via Workflow Builder - screenshots, OmniParser, input actions, game launch
- **UI Density**: Information dense - power user focused, maximum data on screen

---

## Current State

### Existing Gemma Frontend (`D:\Code\Gemma\Gemma\admin\`)
- **Tech Stack**: React 19, Vite 6, TypeScript, Tailwind CSS 4, Socket.io
- **Pages**: Dashboard, Devices, Games, Runs (4 pages)
- **Components**: StatusBadge, ServiceStatus, SUTCard, GameCard, RunCard, LogViewer (6 components)
- **Hooks**: useSystemStatus, useDevices, useGames, useRuns (4 hooks)
- **Limitations**:
  - No Queue Service integration
  - No Preset Manager integration
  - No OmniParser status/control
  - Limited real-time updates
  - No service management
  - No flow visualization

---

## Services & APIs Available

### 1. Queue Service (Port 9000)
| Endpoint | What We Can Show |
|----------|------------------|
| `GET /stats` | Queue depth, processed count, avg response time, throughput |
| `GET /jobs` | Job history with timing and status |
| `GET /queue-depth` | Historical queue depth for graphs |
| `GET /health` | Service health, worker state, uptime |

### 2. SUT Discovery Service (Port 5001)
| Endpoint | What We Can Show |
|----------|------------------|
| `GET /api/suts` | All SUTs with full details |
| `GET /api/suts/events` | SSE real-time SUT online/offline |
| `GET /api/discover/status` | Discovery status, WebSocket connections |
| `POST /api/suts/{id}/action` | Input actions (click, key, etc.) |
| `GET /api/suts/{id}/screenshot` | Live screenshot capture |
| `GET /api/suts/{id}/performance` | CPU, RAM, GPU utilization |

### 3. Preset Manager (Port 5002)
| Endpoint | What We Can Show |
|----------|------------------|
| `GET /api/games` | All games with preset info |
| `GET /api/games/stats` | Total games, presets, syncs |
| `GET /api/sync/stats` | Sync manager status |
| `GET /api/backups` | Backup inventory |
| `POST /api/sync/bulk` | Bulk preset sync |

### 4. Gemma Backend (Port 5000)
| Endpoint | What We Can Show |
|----------|------------------|
| `GET /api/status` | Full system status |
| `GET /api/runs` | Active/historical runs |
| `GET /api/runs/stats` | Run statistics |
| `GET /api/omniparser/status` | OmniParser server status |

---

## Proposed Feature Set

### A. Dashboard Overview (Enhanced)
1. **Service Health Grid** - All services with live status
   - Gemma Backend (running/stopped)
   - SUT Discovery Service (running/stopped)
   - Queue Service (running/stopped + queue depth)
   - Preset Manager (running/stopped)
   - OmniParser instances (1-5, each with status)

2. **Live Metrics Cards**
   - Online SUTs count (with trend)
   - Active automation runs
   - Queue depth (current + mini sparkline)
   - Total games configured
   - Presets synced today

3. **Flow Diagram** (from Service Manager)
   - Live service communication visualization
   - Animated connections when data flows
   - OmniParser instances display

### B. SUT Management (Status Display)
1. **Device Grid**
   - Real-time status (SSE-based)
   - CPU/GPU model display
   - Success rate badge
   - Current task indicator
   - Last seen timestamp
   - Pair/Unpair buttons

2. **Quick Links**
   - Jump to Workflow Builder with SUT selected
   - View installed games

### C. Queue Service Dashboard (NEW)
1. **Queue Stats**
   - Current queue depth
   - Processed count (total/success/failed/timeout)
   - Average processing time
   - Average wait time
   - Requests per minute

2. **Queue Depth Chart**
   - Real-time line chart (last 50+ data points)
   - Historical view selector

3. **Job History Table**
   - Recent jobs (50)
   - Status, duration, image size
   - Error messages for failed jobs

4. **OmniParser Instances**
   - List of configured instances
   - Health status per instance
   - Current load indicator

### D. Preset Management (NEW)
1. **Games Grid**
   - All games with preset counts
   - Quick sync buttons
   - Preset level badges

2. **Preset Browser**
   - Navigate: Game > Preset Level > Files
   - File list with hashes
   - Download preset files

3. **Sync Operations**
   - Select SUTs
   - Select Game + Preset Level
   - Execute bulk sync
   - Sync history with results

4. **Backup Management**
   - Backups per game
   - Restore from backup
   - Cleanup old backups

### E. Automation Runs (Enhanced)
1. **Active Runs Grid**
   - Progress bars
   - Current step indicator
   - Iteration counter
   - Stop button

2. **Run History Table**
   - Filterable by status/game/SUT
   - Success rate column
   - Duration column

3. **Run Detail Modal**
   - Full progress breakdown
   - Step-by-step logs
   - Error details
   - Performance metrics

4. **Bulk Run Launcher**
   - Multi-SUT selection
   - Multi-game selection
   - Iteration count per game

### F. Settings & Configuration (NEW)
1. **Discovery Settings**
   - Discovery interval
   - Timeout values
   - Network ranges
   - Manual IP targets

2. **OmniParser Settings**
   - Server URLs
   - Enable/disable instances
   - Test connection

3. **Service URLs**
   - Queue Service URL
   - Preset Manager URL
   - Discovery Service URL

### G. Live Logs Panel (NEW)
1. **Service Logs**
   - Aggregated logs from all services
   - Filter by service
   - Filter by level (info/warn/error)
   - Search functionality

2. **Event Stream**
   - Real-time events (SUT online/offline, run start/complete)
   - Event type filtering

---

## Implementation Plan (Information Dense, Full Control)

### Phase 1: API Layer & Types
**Files to modify/create:**
- `src/api/index.ts` - Extend with all service APIs
- `src/api/queueService.ts` - NEW: Queue Service client
- `src/api/presetManager.ts` - NEW: Preset Manager client
- `src/api/sutActions.ts` - NEW: SUT control actions
- `src/types/index.ts` - Extend with all data models

**Queue Service APIs:**
```typescript
getQueueStats(): QueueStats
getQueueJobs(limit?): JobRecord[]
getQueueDepth(points?): QueueDepthPoint[]
getQueueHealth(): HealthStatus
```

**Preset Manager APIs:**
```typescript
getPresetGames(): PresetGame[]
getGamePresets(slug): PresetLevel[]
getSyncStats(): SyncStats
pushPreset(game, level, sutIds): SyncResult
```

**Workflow Builder APIs (SUT Interaction):**
```typescript
takeScreenshot(sutId): Blob
parseScreenshot(imageBlob): { elements[], annotated_image }
sendAction(sutId, action): ActionResult
launchGame(sutId, appId): LaunchResult
killProcess(sutId, processName): KillResult
testWorkflowStep(sutId, step): StepResult
runWorkflow(sutId, workflow): RunResult
```

### Phase 2: Data Hooks
**Files to create in `src/hooks/`:**

| Hook | Polling | Returns |
|------|---------|---------|
| `useQueueStats.ts` | 2s | stats, jobs, depth history |
| `usePresetManager.ts` | 30s | games, presets, sync stats |
| `useServiceHealth.ts` | 5s | all services health |
| `useWorkflowBuilder.ts` | on-demand | screenshot, parse, actions (for Workflow Builder) |
| `useSSE.ts` | real-time | generic SSE connection |

### Phase 3: Components (Information Dense Design)
**Files to create in `src/components/`:**

**Metric Components:**
- `MetricCard.tsx` - Compact metric display (value + trend + label)
- `MetricGrid.tsx` - Grid of MetricCards
- `SparklineChart.tsx` - Tiny inline chart for trends
- `MiniGauge.tsx` - Circular progress gauge

**Service Components:**
- `ServiceHealthRow.tsx` - Compact service status row
- `ServiceHealthPanel.tsx` - All services in dense list
- `QueueDepthChart.tsx` - Real-time line chart
- `JobHistoryTable.tsx` - Compact job list with status badges

**SUT Components:**
- `SUTGridCard.tsx` - Dense SUT card with status and quick actions
- `SUTStatusBadge.tsx` - Online/offline/busy status indicator

**Preset Components:**
- `PresetSummaryCard.tsx` - Game + preset count + quick sync
- `SyncStatusBadge.tsx` - Sync result indicator

**Shared Components:**
- `DataTable.tsx` - Reusable dense table with sorting
- `StatusDot.tsx` - Tiny status indicator
- `RefreshButton.tsx` - Manual refresh with last-updated time
- `CollapsibleSection.tsx` - Expandable content section

### Phase 4: Dashboard Layout (Information Dense)

```
┌─────────────────────────────────────────────────────────────────┐
│ HEADER: Gemma Control Center          [Refresh All] [Settings]  │
├─────────────────────────────────────────────────────────────────┤
│ SERVICE HEALTH BAR (horizontal strip)                           │
│ [●Backend] [●Discovery] [●Queue:12] [●Preset] [●OP1] [●OP2]    │
├─────────────────────────────────────────────────────────────────┤
│ LEFT PANEL (40%)              │ RIGHT PANEL (60%)               │
│ ┌───────────────────────────┐ │ ┌─────────────────────────────┐ │
│ │ METRICS GRID (2x4)        │ │ │ QUEUE DEPTH CHART           │ │
│ │ ┌─────┐ ┌─────┐ ┌─────┐   │ │ │ [═══════════════▓▓▓▓]       │ │
│ │ │SUTs │ │Runs │ │Queue│   │ │ │ ~~~~~~~~~~~~~~~~~~~~~~~~~   │ │
│ │ │ 12  │ │ 3   │ │ 5   │   │ │ └─────────────────────────────┘ │
│ │ └─────┘ └─────┘ └─────┘   │ │ ┌─────────────────────────────┐ │
│ │ ┌─────┐ ┌─────┐ ┌─────┐   │ │ │ ACTIVE RUNS (compact)       │ │
│ │ │Games│ │Sync │ │Avg  │   │ │ │ Run#1 [████░░] 67% SUT-01   │ │
│ │ │ 24  │ │ 156 │ │1.2s │   │ │ │ Run#2 [██████] 100% SUT-02  │ │
│ │ └─────┘ └─────┘ └─────┘   │ │ └─────────────────────────────┘ │
│ └───────────────────────────┘ │ ┌─────────────────────────────┐ │
│ ┌───────────────────────────┐ │ │ JOB HISTORY (last 10)       │ │
│ │ ONLINE SUTS (compact)     │ │ │ ID    Time   Status  Size   │ │
│ │ ┌────┐ ┌────┐ ┌────┐      │ │ │ #45   1.2s   ✓      2.1MB  │ │
│ │ │PC1 │ │PC2 │ │PC3 │      │ │ │ #44   0.8s   ✓      1.8MB  │ │
│ │ │ ● ↗│ │ ● ◎│ │ ● ▶│      │ │ │ #43   2.1s   ✗      2.4MB  │ │
│ │ └────┘ └────┘ └────┘      │ │ └─────────────────────────────┘ │
│ │ [+ 9 more]                │ │                                 │
│ └───────────────────────────┘ │                                 │
├─────────────────────────────────────────────────────────────────┤
│ BOTTOM: QUICK ACTIONS                                           │
│ [Start All Runs] [Stop All] [Scan SUTs] [Sync Presets] [Logs]  │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 5: Page Structure

| Page | Path | Content |
|------|------|---------|
| Dashboard | `/` | Everything above - dense overview |
| Devices | `/devices` | Full SUT grid + detail panel + actions |
| Games | `/games` | Game configs + preset summary |
| Runs | `/runs` | Run history + bulk launcher |
| Queue | `/queue` | Full queue dashboard + job history |
| **Workflow** | `/workflow` | **NEW: Visual workflow builder** |
| Settings | `/settings` | Service URLs, discovery config |

### Phase 6: Workflow Builder (Web-based)

**Replaces desktop Tkinter app**: `D:\Code\Gemma\Gemma\workflow_builder.py`

The workflow builder allows creating game automation workflows visually:

```
┌─────────────────────────────────────────────────────────────────┐
│ WORKFLOW BUILDER                    [New] [Load] [Save] [Test]  │
├────────────────────────┬────────────────────────────────────────┤
│ CONNECTION             │ SCREENSHOT CANVAS                      │
│ SUT: [dropdown ▼]      │ ┌────────────────────────────────────┐ │
│ Status: ● Connected    │ │                                    │ │
│ [Take Screenshot]      │ │    [Screenshot with BBoxes]        │ │
│                        │ │    Click to select elements        │ │
│ GAME METADATA          │ │    ┌──────┐                        │ │
│ Name: [_________]      │ │    │ PLAY │ ← selected             │ │
│ Path: [_________]      │ │    └──────┘                        │ │
│ Process: [______]      │ │                                    │ │
│ Duration: [120]s       │ └────────────────────────────────────┘ │
│                        │ Zoom: [50%][75%][100%][125%]           │
├────────────────────────┼────────────────────────────────────────┤
│ WORKFLOW STEPS         │ ACTION DEFINITION                      │
│ [1] Click PLAY ✓       │ ┌────────────────────────────────────┐ │
│ [2] Wait 2s    ✓       │ │ Action Type: [Click ▼]             │ │
│ [3] Click CONT ✓       │ │ Element: [icon ▼]                  │ │
│ [+] Add Step           │ │ Text: [PLAY]                       │ │
│                        │ │ Match: [contains ▼]                │ │
│ [↑][↓][✕] Reorder      │ │ Delay: [2] sec                     │ │
│                        │ │ Timeout: [20] sec                  │ │
│                        │ │ [ ] Optional step                  │ │
│                        │ │                                    │ │
│                        │ │ [+ Add Verify Element]             │ │
│                        │ │ [Test Step] [Add to Workflow]      │ │
│                        │ └────────────────────────────────────┘ │
└────────────────────────┴────────────────────────────────────────┘
```

**Workflow Builder Components:**

| Component | Purpose |
|-----------|---------|
| `WorkflowBuilder.tsx` | Main page layout |
| `ScreenshotCanvas.tsx` | Interactive canvas with bbox overlay |
| `BoundingBoxOverlay.tsx` | Clickable element boxes |
| `StepList.tsx` | Draggable workflow step list |
| `StepEditor.tsx` | Step definition form |
| `ActionTypeSelector.tsx` | Click/Key/Text/Scroll/Wait selector |
| `MetadataPanel.tsx` | Game name, path, process config |
| `VerifyElementsEditor.tsx` | Success verification UI |
| `WorkflowYAMLExport.tsx` | Export to YAML |

**Action Types Supported:**
- `find_and_click` - Find element by text, click it
- `right_click`, `double_click`, `middle_click` - Mouse variants
- `key` - Press single key (Enter, Esc, Tab, etc.)
- `hotkey` - Key combo (Ctrl+S, Alt+F4)
- `text` - Type text into field
- `drag` - Drag element to coordinates
- `scroll` - Scroll up/down
- `wait` - Wait for duration
- `hold_key` - Hold key for duration
- `hold_click` - Hold click for duration

**API Integration:**
```typescript
// Take screenshot from SUT
POST /api/suts/{id}/screenshot → Blob

// Parse screenshot with OmniParser (via Queue Service)
POST /api/omniparser/analyze → { elements[], annotated_image }

// Test action on SUT
POST /api/suts/{id}/action → ActionResult

// Run workflow
POST /api/runs { sut_ip, game_name, workflow }
```

### Phase 7: Implementation Order

1. **API Layer**
   - Queue Service API client
   - Preset Manager API client
   - Workflow Builder API client (screenshot, parse, actions, launch, kill)
   - All TypeScript types

2. **Core Hooks**
   - useQueueStats
   - useServiceHealth
   - useWorkflowBuilder
   - Extend useDevices

3. **Base Components**
   - MetricCard, MetricGrid
   - ServiceHealthRow/Panel
   - SparklineChart
   - DataTable, StatusDot

4. **Dashboard Overhaul**
   - Information dense layout
   - Service health bar
   - Metrics grid
   - Queue depth chart
   - Compact SUT cards
   - Quick actions bar

5. **Queue Page**
   - Full stats display
   - Job history table
   - Depth chart (full size)

6. **Workflow Builder Page** (Major Feature - SUT Interaction Hub)
   - ScreenshotCanvas with zoom/pan
   - BoundingBoxOverlay (clickable elements)
   - StepList with drag reorder
   - StepEditor (action definition)
   - MetadataPanel (game config)
   - YAML export/import
   - Test step on SUT
   - Run full workflow

7. **Polish & Integration**
   - Real-time SSE updates
   - Error handling
   - Loading states
   - Keyboard shortcuts

---

## Technical Notes

### File Locations
- Frontend: `D:\Code\Gemma\Gemma\admin\`
- API client: `src/api/index.ts`
- Types: `src/types/index.ts`
- Hooks: `src/hooks/`
- Components: `src/components/`
- Pages: `src/pages/`

### Service Ports
- Gemma Backend: 5000
- SUT Discovery: 5001
- Preset Manager: 5002
- Queue Service: 9000
- SUT Client: 8080
- OmniParser: 8000 (default)

---

## Critical Infrastructure: Windows Display Resolution Management

### Problem Statement

Games can only render at resolutions that Windows currently supports. If a SUT has a 2K monitor (2560x1600) running at native resolution, the game won't see 1920x1080 as an available option - **even if the preset files specify 1080p**.

**Root Cause**: Game settings files specify desired resolution, but the game can only use resolutions Windows offers.

### Solution: Dynamic Windows Resolution Switching

Before launching a game, the automation must:
1. Query SUT for supported Windows display resolutions
2. Set Windows display resolution to match the preset's target resolution
3. Launch game (which will now see the correct resolution)
4. After automation, optionally restore original resolution

### Implementation Requirements

#### 1. SUT Client Additions (`sut_client/`)

**New Endpoints:**
```
GET /display/resolutions
  → Returns list of supported resolutions for the primary monitor
  → { "supported": ["3840x2160", "2560x1440", "1920x1080", "1280x720"],
      "current": "2560x1600",
      "native": "2560x1600" }

POST /display/resolution
  → Sets Windows display resolution
  → Body: { "width": 1920, "height": 1080 }
  → Response: { "success": true, "previous": "2560x1600", "current": "1920x1080" }

GET /display/current
  → Returns current Windows display resolution
  → { "width": 2560, "height": 1600 }
```

**Implementation (Windows API):**
```python
# In sut_client/src/sut_client/display.py (NEW)
import ctypes
from ctypes import wintypes

def get_supported_resolutions() -> list[tuple[int, int]]:
    """Get all resolutions supported by the primary monitor"""
    # Use EnumDisplaySettings to enumerate all modes

def set_display_resolution(width: int, height: int) -> bool:
    """Change Windows display resolution"""
    # Use ChangeDisplaySettingsEx

def get_current_resolution() -> tuple[int, int]:
    """Get current Windows display resolution"""
    # Use GetSystemMetrics or EnumDisplaySettings
```

#### 2. Automation Orchestrator Changes (`automation_orchestrator.py`)

**Before game launch:**
```python
# In _execute_single_iteration(), before launching:

# 1. Get target resolution from preset
target_resolution = self._get_preset_resolution(game_config)  # e.g., (1920, 1080)

# 2. Check if SUT supports this resolution
supported = network.get_supported_resolutions()
if target_resolution not in supported:
    raise RuntimeError(f"SUT doesn't support {target_resolution}")

# 3. Set Windows resolution if needed
current = network.get_current_resolution()
if current != target_resolution:
    logger.info(f"Changing SUT display from {current} to {target_resolution}")
    network.set_display_resolution(*target_resolution)
    time.sleep(3)  # Allow Windows to settle

# 4. Now launch game
```

#### 3. Frontend: Resolution-Aware Preset Selection

**Device Card Enhancement:**
- Show supported resolutions: "Supports: 4K, 2K, 1080p, 720p"
- Current resolution indicator

**Run Launcher:**
- When selecting SUT + Game + Preset:
  - Check if preset's resolution is supported by selected SUT
  - Gray out / disable incompatible presets
  - Show warning: "This SUT doesn't support 4K resolution"

**Devices Page:**
```
┌─────────────────────────────────────────┐
│ SUT: ZEL-X2 (192.168.0.103)             │
│ Status: ● Online                         │
│ Display: 2560x1600 (native 2K)          │
│ Supported: 4K, 2K, 1080p, 720p          │ ← NEW
│ GPU: RTX 4090                            │
└─────────────────────────────────────────┘
```

**Preset Selection with SUT Context:**
```
Select Preset:
┌─────────────────────────────────────────┐
│ ● ppg-high-1080p     (1920x1080) ✓      │ ← Supported
│ ○ ppg-high-1440p     (2560x1440) ✓      │ ← Supported
│ ○ ppg-high-4k        (3840x2160) ⚠      │ ← Warning: May not be supported
│ ○ ppg-ultra-1080p    (1920x1080) ✓      │
└─────────────────────────────────────────┘
```

#### 4. Preset Metadata Enhancement

Add resolution to preset metadata:
```json
// presets/black-myth-wukong/ppg-high-1080p/preset.json
{
  "resolution": {
    "width": 1920,
    "height": 1080
  },
  "quality_level": "high",
  "description": "PPG High preset at 1080p"
}
```

### Automation Flow (Updated)

```
SINGLE RUN:
1. User selects: SUT + Game + Preset + [✓] Restore resolution after
2. Frontend validates: Does SUT support preset's resolution?
3. If not supported: Show warning, prevent run
4. If supported: Start automation run
5. Orchestrator:
   a. Save current Windows resolution as "original"
   b. Sync preset files to SUT
   c. If needed, change to target resolution (e.g., 1080p)
   d. Wait for display to settle (2-3 seconds)
   e. Launch game
   f. Run automation steps
   g. If "restore" option enabled: Restore original resolution

BATCH RUN (12 games × 3 iterations):
1. User selects: Multiple SUTs + Games + Preset + [✓] Restore after ALL complete
2. Frontend validates all combinations
3. Orchestrator:
   a. Save original resolution ONCE at batch start
   b. Set target resolution ONCE (if all games use same resolution)
   c. For each game/iteration: Run automation (no resolution changes between runs)
   d. After ALL runs complete: If "restore" enabled, restore original resolution
```

### Frontend: Resolution Restore Option

**Run Launcher UI:**
```
┌─────────────────────────────────────────────────────────┐
│ AUTOMATION RUN                                          │
│                                                         │
│ SUT: [ZEL-X2 ▼]  Game: [BMW ▼]  Preset: [1080p-High ▼] │
│ Iterations: [3]                                         │
│                                                         │
│ [✓] Restore original resolution after automation        │ ← NEW
│     (Current: 2560x1600 → Will use: 1920x1080)         │
│                                                         │
│                              [Cancel] [Start Run]       │
└─────────────────────────────────────────────────────────┘
```

**Batch Run UI:**
```
┌─────────────────────────────────────────────────────────┐
│ BATCH AUTOMATION                                        │
│                                                         │
│ SUTs: [ZEL-X2, PC-01, PC-02]                           │
│ Games: [BMW, SOTR, RDR2] × 3 iterations each           │
│ Preset: [1080p-High]                                    │
│                                                         │
│ Total runs: 27 (3 SUTs × 3 games × 3 iterations)       │
│                                                         │
│ [✓] Restore original resolution after ENTIRE batch     │ ← NEW
│                                                         │
│                              [Cancel] [Start Batch]     │
└─────────────────────────────────────────────────────────┘
```

### Files to Modify/Create

| File | Changes |
|------|---------|
| `sut_client/src/sut_client/display.py` | NEW: Windows resolution management |
| `sut_client/src/sut_client/service.py` | Add `/display/*` endpoints |
| `Gemma/modules/network.py` | Add resolution API calls |
| `Gemma/backend/core/automation_orchestrator.py` | Resolution check/set before launch |
| `preset-manager/configs/presets/*/metadata.json` | Add resolution field |
| `Gemma/admin/src/types/index.ts` | Add resolution types |
| `Gemma/admin/src/components/SUTCard.tsx` | Show supported resolutions |
| `Gemma/admin/src/pages/Runs.tsx` | Preset compatibility filtering |

---

## Future Plans

### Multi-Resolution Support

**Current State**: 1080p High (PPG Settings)

**Target**: Support all common gaming resolutions and quality presets

**Prerequisite**: Windows Display Resolution Management (see above)

#### Resolution Matrix

| Resolution | Dimensions | Status |
|------------|------------|--------|
| 720p | 1280x720 | Planned |
| 1080p | 1920x1080 | **Current (Working)** |
| 2K/1440p | 2560x1440 | Planned |
| 4K/2160p | 3840x2160 | Planned |

#### Graphics Presets Matrix

| Preset | 720p | 1080p | 2K | 4K |
|--------|------|-------|----|----|
| Low | Planned | Planned | Planned | Planned |
| Medium | Planned | Planned | Planned | Planned |
| High | Planned | **Current** | Planned | Planned |
| Ultra | Planned | Planned | Planned | Planned |

**Total Combinations**: 16 (4 resolutions × 4 presets)

#### OmniParser Resolution Considerations

1. **720p**
   - Text appears larger relative to image
   - Detection should work well out-of-box
   - May need adjusted `BOX_THRESHOLD` for smaller UI elements

2. **1080p** (Baseline)
   - Current working configuration
   - `BOX_THRESHOLD: 0.05`, `IOU_THRESHOLD: 0.1`
   - `ocr_text_threshold: 0.8`

3. **2K/1440p**
   - Larger image = longer processing time
   - UI elements may be smaller (game-dependent)
   - May need lower `BOX_THRESHOLD` for small icons

4. **4K/2160p**
   - Significantly larger images
   - Text may be too small for OCR without preprocessing
   - **Consider**: Resize to 1080p before OmniParser, scale coords back
   - Processing time will be higher

#### Preset Manager Expansion

**Current Workflow**:
1. Master presets stored in Preset Manager
2. Presets are complete config file replacements (not individual setting changes)
3. Sync pushes entire preset to SUT

**Expansion Needed**:
```
presets/
├── shadow_of_the_tomb_raider/
│   ├── 720p/
│   │   ├── low/
│   │   ├── medium/
│   │   ├── high/
│   │   └── ultra/
│   ├── 1080p/
│   │   ├── low/
│   │   ├── medium/
│   │   ├── high/      ← Current
│   │   └── ultra/
│   ├── 1440p/
│   │   └── ...
│   └── 2160p/
│       └── ...
└── other_games/
    └── ...
```

#### Implementation Priority

1. **Phase 1**: Get 1080p High working end-to-end (Current Focus)
2. **Phase 2**: Add 1080p Low/Medium/Ultra presets
3. **Phase 3**: Add 720p support (all presets)
4. **Phase 4**: Add 2K support (all presets)
5. **Phase 5**: Add 4K support with OmniParser optimizations

#### Frontend Changes Needed

1. **Dashboard**: Show current resolution/preset selection
2. **Settings**: Resolution selector for test runs
3. **Run Launcher**: Preset level dropdown (Low/Medium/High/Ultra)
4. **Workflow Builder**: Resolution-aware coordinate handling
