# Raptor X Automation Sequence

Complete walkthrough of the automation pipeline from start to finish.

## Pre-Launch Phase

| # | Event | Description |
|---|-------|-------------|
| 1 | **Run Created** | Backend creates run record, assigns run_id |
| 2 | **Steam Account Acquired** | Selects available Steam account from pool |
| 3 | **Iteration Started** | Begins iteration 1/N |
| 4 | **SUT Connecting** | Connects to SUT Client on port 8080 |
| 5 | **SUT Connected** | Health check passed |
| 6 | **Resolution Detected** | Gets screen resolution (e.g., 1920x1080) |
| 7 | **OmniParser Connecting** | Connects to Queue Service -> OmniParser |
| 8 | **OmniParser Connected** | Vision AI ready |

## Steam Setup Phase

| # | Event | Description |
|---|-------|-------------|
| 9 | **Steam Login Check** | Verifies correct Steam account is logged in |
| 10 | **Steam Account Switch** | If needed, logs out and logs into correct account |

## Preset Phase

| # | Event | Description |
|---|-------|-------------|
| 11 | **Preset Syncing** | Calls Preset Manager to sync game settings |
| 12 | **Preset Applied** | Config files pushed to SUT |

## Game Launch Phase

| # | Event | Description |
|---|-------|-------------|
| 13 | **Game Launching** | Sends launch command to SUT Client |
| 14 | **Process Waiting** | Waits up to 90s for game process to appear |
| 15 | **Process Detected** | Game process found (e.g., F1_24.exe) |
| 16 | **Game Launched** | Launch confirmed successful |
| 17 | **Game Initializing** | Waits `startup_wait` seconds for game to load |

## Automation Steps Phase

| # | Event | Description |
|---|-------|-------------|
| 18 | **Step N Started** | For each step in game YAML config |
| - | Screenshot | Take screenshot on SUT |
| - | Parse | Send to OmniParser for element detection |
| - | Find | Find target element (text/icon matching) |
| - | Execute | Execute action (click/key/wait/scroll) |
| - | Delay | Wait `expected_delay` seconds |
| 19 | **Step N Completed** | Move to next step |
| 20 | **Step N Skipped** | If optional step fails, skip and continue |

## Benchmark Phase

| # | Event | Description |
|---|-------|-------------|
| 21 | **Wait Step** | Waits `benchmark_duration` for benchmark to run |
| 22 | **Results Collected** | Collects benchmark results (if configured) |

## Cleanup Phase

| # | Event | Description |
|---|-------|-------------|
| 23 | **Game Closing** | Executes quit steps (if in config) |
| 24 | **Iteration Completed** | Marks iteration success/fail |
| 25 | **Next Iteration** | If more iterations, repeat from step 13 |
| 26 | **Run Completed** | All iterations done, final status set |

## Post-Run

| # | Event | Description |
|---|-------|-------------|
| 27 | **Logs Saved** | Service logs collected to run folder |
| 28 | **Timeline Saved** | Full event timeline persisted |
| 29 | **Steam Account Released** | Returns account to pool |

---

## Future Plans

- [ ] Display this sequence in Raptor X Mission Control frontend
- [ ] Add to About/Help page with visual diagram
- [ ] Show real-time progress indicator matching these steps
- [ ] Add step-by-step tooltips in the Run Timeline component
