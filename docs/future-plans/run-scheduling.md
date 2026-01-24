# Run Scheduling & Queue Management

## Status: Pending

## Overview

Enhance run management with scheduling, queueing, and dynamic reordering capabilities inspired by Spotify's queue system.

---

## Features

### 1. Schedule Runs on Busy SUT

**Problem**: When a SUT is already running an automation, you can't queue additional work for it.

**Solution**: Allow scheduling runs that will execute when the SUT becomes available.

```
User clicks "Start Run" on busy SUT
     │
     ▼
┌─────────────────────────────────────┐
│  SUT-X7 is currently busy           │
│  Running: Far Cry 6 (3/5 presets)   │
│                                     │
│  [Schedule for Later]  [Cancel]     │
└─────────────────────────────────────┘
     │
     ▼
Run added to SUT-X7's queue
Executes automatically when current run completes
```

**Implementation**:
- Add `scheduled_runs` table/storage
- SUT-specific run queues
- Auto-start next scheduled run on completion
- Show scheduled runs in SUT detail panel

---

### 2. Schedule Runs for Future Time/Event

**Problem**: No way to schedule runs for later (e.g., overnight, after driver install).

**Solution**: Time-based and event-based run scheduling.

**Time-based**:
```json
{
  "run_id": "abc123",
  "scheduled_for": "2026-01-15T02:00:00Z",
  "recurrence": null
}
```

**Event-based triggers**:
- After driver installation completes
- After system reboot
- After another run completes
- On SUT coming online
- On preset sync completion

**UI**:
```
┌─────────────────────────────────────┐
│  Schedule Run                        │
│                                      │
│  When: ○ Now                         │
│        ○ At specific time: [____]    │
│        ○ After event: [dropdown ▼]   │
│                                      │
│  Events:                             │
│    - SUT comes online                │
│    - After: Run XYZ completes        │
│    - After driver install            │
│                                      │
│  [Schedule]  [Cancel]                │
└─────────────────────────────────────┘
```

---

### 3. Add to Queue (Spotify-style)

**Inspiration**: Spotify's "Add to Queue" feature for songs.

**Current behavior**: Can only start one run at a time per SUT.

**Proposed behavior**:
- "Add to Queue" button alongside "Start Run"
- Visual queue showing upcoming runs
- Queue persists across service restarts

**Queue UI**:
```
┌────────────────────────────────────────────┐
│  SUT-X7 Run Queue                          │
├────────────────────────────────────────────┤
│  ▶ NOW PLAYING                             │
│    Far Cry 6 - Ultra preset (2/5)          │
│                                            │
│  ⏭ UP NEXT                                 │
│    1. Cyberpunk 2077 - High preset         │
│    2. Hitman 3 Dubai - All presets         │
│    3. AC Mirage - Medium preset            │
│                                            │
│  [+ Add to Queue]                          │
└────────────────────────────────────────────┘
```

---

### 4. Change Order of Execution On-the-fly

**Problem**: Can't reprioritize queued runs.

**Solution**: Drag-and-drop reordering of queue.

**Features**:
- Drag to reorder queued runs
- "Play Next" - move to top of queue
- "Remove from Queue" - cancel scheduled run
- Priority levels (Normal, High, Low)

**API Endpoints**:
```
POST /api/queue/reorder
{
  "sut_id": "sut-x7",
  "run_ids": ["run3", "run1", "run2"]  // New order
}

POST /api/queue/play-next
{
  "sut_id": "sut-x7",
  "run_id": "run5"
}

DELETE /api/queue/{run_id}
```

---

## Data Model

### ScheduledRun

```python
class ScheduledRun(BaseModel):
    id: str
    sut_id: str
    game_name: str
    preset_name: Optional[str]

    # Scheduling
    schedule_type: Literal["immediate", "time", "event"]
    scheduled_time: Optional[datetime]
    trigger_event: Optional[str]

    # Queue position
    position: int
    priority: Literal["low", "normal", "high"]

    # Status
    status: Literal["queued", "waiting", "running", "completed", "cancelled"]
    created_at: datetime
    started_at: Optional[datetime]
```

---

## Implementation Phases

### Phase 1: Basic Queue
- [ ] Add run queue storage (per SUT)
- [ ] "Add to Queue" button in frontend
- [ ] Display queue in SUT detail panel
- [ ] Auto-start next queued run on completion

### Phase 2: Scheduling
- [ ] Time-based scheduling with datetime picker
- [ ] Scheduled runs list view
- [ ] Cancel scheduled run functionality

### Phase 3: Reordering
- [ ] Drag-and-drop queue reordering (Motion library)
- [ ] "Play Next" action
- [ ] Priority levels

### Phase 4: Event Triggers
- [ ] Event system for triggers
- [ ] "After run X" scheduling
- [ ] "On SUT online" triggers

---

## Related

- See [automation-sequence.md](./automation-sequence.md) for run lifecycle
- See [ui-animations.md](./ui-animations.md) for drag-drop animations
