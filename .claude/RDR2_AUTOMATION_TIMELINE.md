# RDR2 Automation Timeline Simulation

## Overview

This document details every timeout, wait, and delay in the RDR2 automation flow from start to finish.

---

## Phase 1: Initialization (T+0s to T+1s)

| Action | Timeout | Typical Duration |
|--------|---------|------------------|
| Frontend POST /api/runs | - | ~100ms |
| Create run in memory | - | ~10ms |
| Emit `run_started` WebSocket event | - | ~10ms |
| Start background thread | - | ~50ms |

---

## Phase 2: SUT Connection (T+0.2s)

| Action | Timeout | Typical Duration |
|--------|---------|------------------|
| `GET /status` (connection check) | 5s | ~200ms |
| Timeline: "Connecting to SUT" | - | - |
| Timeline: "SUT Connected" | - | - |

---

## Phase 3: Resolution Detection (T+0.4s)

| Action | Timeout | Typical Duration |
|--------|---------|------------------|
| `GET /display/current` | 5s | ~150ms |
| Timeline: "Detected resolution" | - | - |

---

## Phase 4: OmniParser Connection (T+0.6s)

| Action | Timeout | Typical Duration |
|--------|---------|------------------|
| Initialize OmniParser client | - | ~50ms |
| Timeline: "OmniParser connected" | - | - |

---

## Phase 5: Preset Sync (T+0.7s)

| Action | Timeout | Typical Duration |
|--------|---------|------------------|
| Sync preset to SUT | 30s | 2-5s |
| Timeline: "Syncing preset..." | - | - |

*Skipped if no preset configured (~0s)*

---

## Phase 6: Resolution Change (T+5s)

| Action | Timeout | Typical Duration |
|--------|---------|------------------|
| `POST /display/set` | 15s | ~1s |
| **Display settle wait (HARDCODED)** | - | **5s** |
| Timeline: "Resolution changed" | - | - |

*Skipped if resolution already matches (~0s)*

---

## Phase 7: Steam Login (T+11s)

| Action | Timeout | Typical Duration |
|--------|---------|------------------|
| `GET /steam/current` | 10s | ~200ms |
| `POST /login_steam` | **180s** | 5-15s |

*Skipped if already logged in with correct account (~200ms)*

---

## Phase 8: Game Launch - THE BOTTLENECK

### Backend Side (`network.py`)

| Config | Value | Source |
|--------|-------|--------|
| HTTP timeout | `max(120, startup_wait + 60)` | For RDR2: 150s |

### SUT Side (`launcher.py`) - Current Flow

| Step | Timeout | Code Location |
|------|---------|---------------|
| Initial spawn wait | **3s** | `launcher.py:447` |
| Process detection loop | **60s** (was hardcoded, now uses startup_wait) | `launcher.py:458-476` |
| Window visibility (pywinauto) | **120s** | `launcher.py:485` `visible_timeout` |
| Window ready (pywinauto) | **30s** | `launcher.py:489` `ready_timeout` |
| Foreground detection | **5s** | `launcher.py:494` |
| Foreground retry loop | **9 retries × 10s = 90s** | `launcher.py:499-521` |

### Worst Case Launch Time

```
3s (spawn) + 60s (process) + 120s (visible) + 30s (ready) + 90s (retries) = 303s (5+ min)
```

### Expected Launch Time (RDR2)

Based on manual testing:
- Steam → Rockstar Launcher: ~42s
- Rockstar → Main Menu: ~25s
- **Total: ~67s**

---

## Phase 9: Automation Steps

### Per-Step Flow

```
┌─────────────────────────────────────────────────┐
│ Step N                                          │
├─────────────────────────────────────────────────┤
│ 1. Check game process running     ~200ms        │
│ 2. Focus game window              ~200ms-15s    │
│ 3. Post-focus delay               200ms         │
│ 4. Capture screenshot             ~500ms        │
│ 5. Send to OmniParser             1-5s          │
│ 6. Find UI element                ~100ms        │
│ 7. Execute action                 ~500ms        │
│ 8. Expected delay (from config)   2-4s          │
│                                                 │
│ Per-step typical: 5-10s                         │
│ Per-step worst (3 retries): ~36s                │
└─────────────────────────────────────────────────┘
```

### RDR2 Steps (from config)

| Step | Description | timeout | expected_delay |
|------|-------------|---------|----------------|
| 1 | Press Z for Settings | 30s | 3s |
| 2 | Click GRAPHICS | 20s | 2s |
| 3 | Enter GRAPHICS | 20s | 3s |
| 4 | Hold X for Benchmark | 30s | 4s |
| 5 | Confirm benchmark | 20s | 4s |
| 6 | **WAIT 320s** (benchmark) | 30s | 4s |
| 7 | Exit results | 30s | 4s |
| 8 | Navigate quit | 20s | 3s |
| 9 | Click Quit | 20s | 3s |
| 10 | Confirm exit | 20s | 4s |

---

## Summary: Total Expected Time

| Phase | Best Case | Typical | Worst Case |
|-------|-----------|---------|------------|
| Initialization | 0.2s | 0.5s | 1s |
| SUT Connection | 0.2s | 0.5s | 5s |
| Resolution + Preset | 0s | 10s | 50s |
| Steam Login | 0.2s | 10s | 180s |
| **Game Launch** | 30s | **60s** | **300s** |
| Steps 1-5 | 25s | 40s | 180s |
| Benchmark | 320s | 320s | 320s |
| Steps 7-10 | 20s | 30s | 120s |
| Cleanup | 1s | 5s | 15s |
| **TOTAL** | ~6.5 min | **~8 min** | **~20 min** |

---

## Known Issues

### Issue 1: Excessive Window Detection Timeouts

The `visible_timeout=120s` and `ready_timeout=30s` in pywinauto detection are too high. If pywinauto fails to detect the window, it waits the full timeout before retrying.

### Issue 2: Retry Loop Too Aggressive

`retry_count = startup_wait // 10` means RDR2 (startup_wait=90) gets 9 retries with 10s intervals = 90s of potential waiting even after the game is ready.

### Issue 3: No Early Exit

The code doesn't check if the window is already in foreground before starting all the detection/retry loops.

---

## Fixes Applied

1. **Process detection timeout** - Now uses `startup_wait` from game config instead of hardcoded 60s
2. **Game closure detection** - Added `_is_game_running()` check to fail fast when game closes

## Fixes Needed

1. Reduce `visible_timeout` from 120s to 30-60s
2. Reduce `ready_timeout` from 30s to 10-15s
3. Add early exit when window already focused
4. Make timeouts configurable per-game

---

## Manual Test Baseline (RDR2)

| Phase | Duration |
|-------|----------|
| Steam → Click Play | instant |
| Rockstar Launcher loading | 42s |
| RDR2 Launch → Main Menu | 25s |
| **Total** | **~67s** |

Automation should target < 90s for game launch, not 300s+.
