# Run Logging Structure Design

> **Status**: Planned
> **Created**: 2025-12-28
> **Priority**: High

---

## Overview

Replace the current in-memory run storage with a persistent, meaningful directory structure that captures full telemetry per game, per iteration.

---

## Directory Structure

```
Gemma/logs/
└── runs/
    ├── {date}_{time}_{cpu}_{ip}_{type}-{game}/
    │   ├── manifest.json
    │   ├── perf-run-1/
    │   │   ├── blackbox_{type}_run1_{cpu}_{ip}_{game}.log
    │   │   ├── screenshots/
    │   │   │   ├── step_01_launch.png
    │   │   │   ├── step_02_settings.png
    │   │   │   └── ...
    │   │   └── results/
    │   │       └── benchmark.csv
    │   ├── perf-run-2/
    │   │   └── ...
    │   ├── perf-run-3/
    │   │   └── ...
    │   └── trace-run/           # Optional: Intel telemetry
    │       ├── blackbox_trace_{cpu}_{ip}_{game}.log
    │       ├── {game}_ptat.csv
    │       └── {game}_socwatch.csv
    └── index.json               # Run history index
```

---

## Naming Convention

### Run Folder Name
```
{YYYY-MM-DD}_{HHMMSS}_{cpu_model}_{ip_dashed}_{run_type}-{game}
```

**Examples:**
- `2025-12-28_163045_14600KF_192-168-0-103_single-BMW`
- `2025-12-28_170000_14600KF_192-168-0-103_bulk-BMW-RDR2-SOTR`
- `2025-12-28_180000_7800X3D_192-168-0-104_single-Cyberpunk2077`

**Components:**
| Component | Format | Example |
|-----------|--------|---------|
| date | YYYY-MM-DD | 2025-12-28 |
| time | HHMMSS | 163045 |
| cpu_model | Model number only | 14600KF, 7800X3D |
| ip_dashed | IP with dashes | 192-168-0-103 |
| run_type | single/bulk | single, bulk |
| game | Game short name | BMW, RDR2 |

### Run Types
- `single-{game}` - Single game run (any number of iterations)
- `bulk-{game1}-{game2}-...` - Multiple games in sequence

### Blackbox Log
```
blackbox_{perf-runN|trace}_{cpu}_{ip}_{type}-{game}.log
```

**Examples:**
- `blackbox_perf-run1_14600KF_192-168-0-103_single-BMW.log`
- `blackbox_perf-run2_14600KF_192-168-0-103_single-BMW.log`
- `blackbox_trace_14600KF_192-168-0-103_single-BMW.log`

### Screenshots
```
step_{NN}_{action}.png
```

**Examples:**
- `step_01_launch.png`
- `step_02_main-menu.png`
- `step_03_settings.png`
- `step_04_graphics.png`
- `step_05_run-benchmark.png`

### Results
```
benchmark.csv
{game}_results.xml
```

---

## manifest.json Schema

```json
{
  "version": "1.0",
  "run_id": "abc123-def456",
  "created_at": "2025-12-28T16:30:45Z",
  "completed_at": "2025-12-28T16:45:30Z",
  "status": "completed",

  "sut": {
    "ip": "192.168.0.103",
    "hostname": "ZEL-X7",
    "device_id": "sut_ZEL-X7_b7a0a0b216da",
    "cpu": {
      "brand_string": "Intel(R) Core(TM) i5-14600KF",
      "model": "14600KF",
      "codename": "Raptor Lake"
    },
    "gpu": {
      "name": "NVIDIA GeForce RTX 4070 SUPER",
      "short": "RTX 4070 SUPER"
    },
    "ram_gb": 32,
    "os": {
      "name": "Windows",
      "version": "11",
      "build": "10.0.26100"
    },
    "resolution": {
      "width": 1920,
      "height": 1080
    },
    "bios": {
      "name": "...",
      "version": "..."
    }
  },

  "run_config": {
    "type": "single",
    "games": ["BMW"],
    "iterations": 3,
    "preset_level": "ppg-high-1080p",
    "trace_enabled": false
  },

  "iterations": [
    {
      "number": 1,
      "type": "perf",
      "status": "completed",
      "started_at": "2025-12-28T16:30:45Z",
      "completed_at": "2025-12-28T16:35:30Z",
      "duration_seconds": 285,
      "screenshots_count": 12,
      "results_file": "perf-run-1/results/benchmark.csv"
    },
    {
      "number": 2,
      "type": "perf",
      "status": "completed",
      "started_at": "2025-12-28T16:36:00Z",
      "completed_at": "2025-12-28T16:40:45Z",
      "duration_seconds": 285
    },
    {
      "number": 3,
      "type": "perf",
      "status": "completed",
      "started_at": "2025-12-28T16:41:15Z",
      "completed_at": "2025-12-28T16:45:30Z",
      "duration_seconds": 255
    }
  ],

  "trace_run": null,

  "summary": {
    "total_duration_seconds": 895,
    "successful_iterations": 3,
    "failed_iterations": 0,
    "avg_benchmark_fps": 85.3,
    "min_benchmark_fps": 82.1,
    "max_benchmark_fps": 88.7
  },

  "errors": []
}
```

---

## Bulk Run Structure

For bulk runs (multiple games), each game gets its own subfolder:

```
2025-12-28_163045_14600KF_192-168-0-103_bulk-BMW-RDR2-SOTR/
├── manifest.json           # Overall bulk run manifest
├── BMW/
│   ├── game_manifest.json  # Per-game manifest
│   ├── perf-run-1/
│   ├── perf-run-2/
│   ├── perf-run-3/
│   └── trace-run/
├── RDR2/
│   ├── game_manifest.json
│   ├── perf-run-1/
│   ├── perf-run-2/
│   └── perf-run-3/
└── SOTR/
    ├── game_manifest.json
    ├── perf-run-1/
    ├── perf-run-2/
    └── perf-run-3/
```

---

## index.json Schema

Run history index for quick loading without scanning all folders:

```json
{
  "version": "1.0",
  "last_updated": "2025-12-28T16:45:30Z",
  "runs": [
    {
      "folder": "2025-12-28_163045_14600KF_192-168-0-103_single-BMW",
      "run_id": "abc123",
      "created_at": "2025-12-28T16:30:45Z",
      "sut_ip": "192.168.0.103",
      "cpu": "14600KF",
      "type": "single",
      "games": ["BMW"],
      "status": "completed",
      "iterations": 3
    }
  ]
}
```

---

## Implementation Tasks

### Phase 1: Core Structure
1. Create `RunStorageManager` class
2. Implement folder name generation from telemetry
3. Fetch SUT system_info at run start
4. Create manifest.json on run start
5. Update manifest.json on run completion

### Phase 2: Blackbox Logging
1. Create per-iteration log files
2. Redirect automation logs to blackbox files
3. Include timestamps and step markers

### Phase 3: Screenshots
1. Save screenshots per iteration
2. Name with step number and action
3. Link in manifest.json

### Phase 4: Results
1. Copy/parse benchmark results
2. Extract metrics to manifest summary
3. Support multiple result formats (CSV, XML)

### Phase 5: History Loading
1. Scan runs/ folder on startup
2. Load/rebuild index.json
3. Expose in API for frontend

### Phase 6: Trace Integration (Future)
1. Intel PTAT integration
2. Intel SocWatch integration
3. Trace run support

---

## Files to Create/Modify

```
Gemma/backend/core/run_storage.py       - NEW: RunStorageManager class
Gemma/backend/core/run_manager.py       - Integrate with RunStorageManager
Gemma/backend/core/automation_orchestrator.py - Save screenshots/logs per iteration
Gemma/backend/api/routes.py             - Serve run artifacts (screenshots, logs)
```

---

## Migration

Existing `logs/{game_name}/run_{run_id}/` structure will be deprecated.
New runs will use `logs/runs/{naming_convention}/` structure.
