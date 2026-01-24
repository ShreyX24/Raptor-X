# Performance Results Extraction & Intel Tracing Integration

> **STATUS: PENDING** - Future feature for comprehensive benchmark result collection and hardware performance tracing

## Overview
Implement automated performance data collection from game benchmarks and integrate Intel hardware tracing tools (PTAT and SocWatch) for comprehensive system performance analysis during gaming workloads.

## Part 1: Benchmark Results Extraction

### Goal
Automatically collect and parse benchmark results from games after each run, storing them in a centralized database for analysis.

### Games with Parseable Results

| Game | Results Location | Format | Key Metrics |
|------|------------------|--------|-------------|
| F1 24 | `My Games\F1 24\benchmark\Benchmark_*.xml` | XML | Avg FPS, Min FPS, Max FPS, Frame Times |
| Shadow of the Tomb Raider | `My Games\Shadow of the Tomb Raider\Benchmark Results\*.csv` | CSV | Avg FPS, GPU/CPU frame times |
| Far Cry 6 | Unknown | TBD | FPS, Frame times |
| Cyberpunk 2077 | `REDprelauncher\Cyberpunk2077_benchmark.csv` | CSV | Avg FPS, 1% Low, Frame times |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Automation Orchestrator                   │
│  After game benchmark completes:                            │
│  1. Call results collector                                  │
│  2. Parse results based on game config                      │
│  3. Store in central database                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Results Collector Module                  │
│  - Locate results file on SUT (via SSH or SUT client)       │
│  - Parse XML/CSV/JSON based on game type                    │
│  - Extract key metrics                                      │
│  - Return structured data                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Results Database                          │
│  - SQLite or PostgreSQL                                     │
│  - Store per-run metrics                                    │
│  - Link to run ID, game config, preset, SUT                 │
│  - Support historical comparison                            │
└─────────────────────────────────────────────────────────────┘
```

### Game YAML Extensions

```yaml
metadata:
  game_name: "F1 24"
  # ... existing fields ...

  # Results extraction config
  results:
    enabled: true
    format: "xml"  # xml, csv, json
    location: "My Games\\F1 24\\benchmark"
    pattern: "Benchmark_*.xml"
    parser: "f1_24"  # Custom parser name
    metrics:
      - name: "avg_fps"
        xpath: "//AverageFrameRate"  # For XML
      - name: "min_fps"
        xpath: "//MinFrameRate"
      - name: "frame_times"
        xpath: "//FrameTimes/Frame"
```

### Implementation Steps

1. **Add results config to game YAML schema**
2. **Create ResultsCollector base class**
3. **Implement game-specific parsers**:
   - F1Parser (XML)
   - SOTRParser (CSV)
   - CyberpunkParser (CSV)
4. **Add SUT file retrieval endpoint** (`/read_file`)
5. **Create results database schema**
6. **Integrate with orchestrator post-run hook**

---

## Part 2: Intel PTAT Integration

### Intel Platform Telemetry Analysis Tool (PTAT)
PTAT collects low-level CPU telemetry including:
- Core frequencies
- Power consumption (Package/Core/Uncore)
- Thermal data
- C-state residencies
- Memory bandwidth

### Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SUT Client Extensions                     │
│  /start_ptat - Start PTAT collection                        │
│  /stop_ptat  - Stop and retrieve results                    │
│  /ptat_status - Check if PTAT is running                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    PTAT Process Management                   │
│  - Locate PTAT installation                                 │
│  - Configure collection profile (Gaming workload)           │
│  - Start collection before game launch                      │
│  - Stop collection after benchmark                          │
│  - Parse PTAT CSV output                                    │
└─────────────────────────────────────────────────────────────┘
```

### PTAT Configuration

```yaml
# In game YAML or global settings
tracing:
  ptat:
    enabled: true
    profile: "gaming"  # gaming, power, thermal
    metrics:
      - cpu_frequency
      - package_power
      - core_temps
      - c_state_residency
    sample_interval: 100  # ms
```

### SUT Client Endpoints

```python
# sut_client/src/sut_client/tracing.py

@app.route('/start_ptat', methods=['POST'])
def start_ptat():
    """Start PTAT collection"""
    data = request.get_json()
    profile = data.get('profile', 'gaming')
    output_file = data.get('output_file', 'ptat_results.csv')

    # Launch PTAT with specified profile
    cmd = f'"{PTAT_PATH}" -profile {profile} -output {output_file}'
    subprocess.Popen(cmd, shell=True)

    return jsonify({"status": "started"})

@app.route('/stop_ptat', methods=['POST'])
def stop_ptat():
    """Stop PTAT and return results"""
    # Stop PTAT process
    # Parse results
    # Return metrics
```

---

## Part 3: Intel SocWatch Integration

### Intel SocWatch
SocWatch provides system-level power and performance analysis:
- Package/Platform power states
- GPU metrics (Intel Arc)
- Memory power states
- Thermal throttling events
- Display power states

### Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator Tracing Hooks               │
│  Pre-launch:                                                │
│    - Start PTAT/SocWatch collection                        │
│  Post-benchmark:                                            │
│    - Stop collection                                        │
│    - Retrieve and parse results                             │
│    - Store in database                                      │
└─────────────────────────────────────────────────────────────┘
```

### SocWatch Configuration

```yaml
tracing:
  socwatch:
    enabled: true
    features:
      - package_cstates
      - gpu_activity
      - thermal_events
      - power_consumption
    duration: "benchmark"  # Match benchmark duration
```

---

## Part 4: Unified Tracing System

### Combined Data Flow

```
                    ┌───────────────────┐
                    │  Automation Start │
                    └─────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌─────────┐     ┌─────────┐     ┌─────────┐
        │  PTAT   │     │SocWatch │     │  Game   │
        │  Start  │     │  Start  │     │ Launch  │
        └────┬────┘     └────┬────┘     └────┬────┘
             │               │               │
             └───────────────┼───────────────┘
                             │
                    ┌────────▼────────┐
                    │   Benchmark     │
                    │    Running      │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌─────────┐    ┌─────────┐    ┌─────────┐
        │  PTAT   │    │SocWatch │    │  Game   │
        │  Stop   │    │  Stop   │    │ Results │
        └────┬────┘    └────┬────┘    └────┬────┘
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                    ┌───────────────┐
                    │ Results Store │
                    │  (Database)   │
                    └───────────────┘
```

### Database Schema

```sql
CREATE TABLE benchmark_runs (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL,
    sut_id TEXT NOT NULL,
    game_name TEXT NOT NULL,
    preset TEXT,
    resolution TEXT,
    timestamp DATETIME,

    -- Game benchmark metrics
    avg_fps REAL,
    min_fps REAL,
    max_fps REAL,
    p1_low REAL,
    p01_low REAL,

    -- PTAT metrics (averages)
    avg_cpu_freq_mhz REAL,
    avg_package_power_w REAL,
    max_cpu_temp_c REAL,
    avg_c0_residency REAL,

    -- SocWatch metrics
    avg_gpu_power_w REAL,
    thermal_throttle_events INTEGER,
    avg_memory_bandwidth_gbps REAL
);

CREATE TABLE frame_times (
    run_id INTEGER REFERENCES benchmark_runs(id),
    frame_num INTEGER,
    frame_time_ms REAL
);
```

---

## Implementation Priority

1. **Phase 1**: Benchmark results extraction (F1 24, SOTR)
2. **Phase 2**: PTAT integration
3. **Phase 3**: SocWatch integration
4. **Phase 4**: Unified dashboard for results visualization

---

## Files to Create/Modify

### New Files
- `Gemma/modules/results_collector.py` - Base results collection
- `Gemma/modules/parsers/` - Game-specific result parsers
- `Gemma/backend/core/tracing_manager.py` - PTAT/SocWatch management
- `sut_client/src/sut_client/tracing.py` - SUT tracing endpoints

### Modified Files
- `Gemma/backend/core/automation_orchestrator.py` - Add tracing hooks
- `Gemma/backend/core/game_manager.py` - Add results config to GameConfig
- `sut_client/src/sut_client/service.py` - Register tracing endpoints

---

## Prerequisites

- Intel PTAT installed on SUT (Windows)
- Intel SocWatch installed on SUT (Windows)
- SSH access to SUT for file retrieval OR extended SUT client file API

---

## Revision History

| Date | Changes |
|------|---------|
| 2025-12-27 | Initial plan created |
