# RPX Service Profiler

Monitor all RPX services for memory leaks, thread issues, and performance problems.

## Quick Start

### GUI Version (Recommended)

```bash
# Install dependency (one-time)
pip install psutil

# Launch GUI with Start/Stop buttons
python profiler_gui.py
```

![GUI Preview](https://via.placeholder.com/800x400?text=Profiler+GUI+with+Start/Stop+buttons)

### Command Line Version

```bash
# Run profiler for 10 minutes with live output
python service_profiler.py --duration 10 --live

# Open viewer.html in browser
# Drag & drop the generated JSON file to visualize
```

## Usage

### Command Line Options

```bash
python service_profiler.py [options]

Options:
  --duration, -d    Duration in minutes (default: 10)
  --interval, -i    Sample interval in seconds (default: 30)
  --live, -l        Show live console output
  --output, -o      Custom output filename prefix
```

### Examples

```bash
# Quick 5-minute check with live output (1s intervals - default)
python service_profiler.py -d 5 -l

# During campaign run - captures every automation step
python service_profiler.py -d 30 -l

# Long stress test (1 hour, 5s intervals to reduce data volume)
python service_profiler.py -d 60 -i 5 -o stress_test
```

## Viewing Results

1. Open `viewer.html` in any browser
2. Click "Load Results JSON" or drag & drop the JSON file
3. Review the dashboard:
   - **Health Score**: 0-100 overall health
   - **Issues**: Detected problems and recommendations
   - **Service Cards**: Per-service metrics with charts

## Understanding the Metrics

### Health Score (0-100)

| Score | Status | Meaning |
|-------|--------|---------|
| 80-100 | ✓ Good | Service is healthy |
| 50-79 | ⚠ Warning | Some metrics elevated |
| 0-49 | ✗ Critical | Service needs attention |

### Memory Trends

| Trend | Indicator | Meaning |
|-------|-----------|---------|
| Stable | → | Memory usage consistent |
| Growing | ↑ | Memory increasing over time - **possible leak** |
| Shrinking | ↓ | Memory decreasing (normal after GC) |

### Default Thresholds

| Service | Memory Warning | Memory Critical | Threads Warning |
|---------|---------------|-----------------|-----------------|
| service-manager | 200 MB | 400 MB | 15 |
| gemma-backend | 300 MB | 600 MB | 20 |
| gemma-frontend | 300 MB | 600 MB | 15 |
| preset-manager | 200 MB | 400 MB | 15 |
| sut-discovery | 150 MB | 300 MB | 10 |
| queue-service | 200 MB | 400 MB | 15 |
| omniparser | 4000 MB | 6000 MB | 25 |

## Common Issues

### "Memory is growing over time"

This indicates a potential memory leak. To investigate:

1. Run a longer profiling session (30-60 min)
2. Check if growth continues or stabilizes
3. Look for patterns (grows during runs, stable otherwise)

### "Thread count is growing"

Threads not being cleaned up properly:

1. Check for background tasks not being cancelled
2. Look for worker pools without proper cleanup
3. Verify async tasks are being awaited

### "Handle count is growing"

File or socket handles not being closed:

1. Check for unclosed file handles
2. Verify HTTP connections are being closed
3. Look for database connection leaks

## Files

```
profilers/
├── profiler_gui.py       # GUI version with Start/Stop buttons
├── service_profiler.py   # Command-line profiler script
├── viewer.html           # Results visualization (charts)
├── README.md             # This file
└── results/              # Generated JSON files
    └── YYYYMMDD_HHMMSS_profile.json
```

## GUI Version Features

Launch with: `python profiler_gui.py`

- **▶ START** - Begin profiling all detected services
- **■ STOP** - Stop profiling at any time
- **💾 SAVE** - Export results to JSON for viewer.html

### Live Display
- Real-time metrics table (Memory, Threads, Handles, CPU)
- Health status per service (Good/Warning/Critical)
- Memory trend detection (Growing = potential leak)
- Issues panel with warnings

### Interval Selection
Choose sampling interval: 1s (default), 2s, 3s, 5s, 10s, or 30s

**Note**: 1-second intervals are recommended to capture fast operations like automation steps.

## Recommended Workflow

### During Development

```bash
# Quick check after code changes
python service_profiler.py -d 5 -i 15 -l
```

### Before Release

```bash
# Comprehensive stress test
python service_profiler.py -d 60 -i 30 -o pre_release
```

### Debugging Issues

```bash
# Fast sampling to catch spikes
python service_profiler.py -d 10 -i 5 -l
```

## Integration with py-spy

For deeper Python thread analysis:

```bash
# Install py-spy
pip install py-spy

# Get live thread view
py-spy top --pid <PID>

# Dump all stacks (for deadlock debugging)
py-spy dump --pid <PID>

# Generate flamegraph
py-spy record -o profile.svg --pid <PID> --duration 30
```

## Troubleshooting

### "No RPX services found"

Make sure services are running. Start them via Service Manager or manually.

### Permission errors

Run as Administrator on Windows for full access to process metrics.

### psutil not installed

```bash
pip install psutil
```
