"""
RPX Service Profiler
====================
Monitors all RPX services for memory leaks, thread issues, and performance.

Usage:
    python service_profiler.py                    # Monitor for 10 minutes
    python service_profiler.py --duration 60     # Monitor for 60 minutes
    python service_profiler.py --interval 10     # Sample every 10 seconds
    python service_profiler.py --live            # Live console output
    python service_profiler.py --output my_run   # Custom output name

Output:
    profilers/results/<timestamp>_profile.json   # Raw data
    Open profilers/viewer.html to visualize      # Charts & analysis
"""

import argparse
import json
import os
import sys
import time
import platform
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import subprocess

try:
    import psutil
except ImportError:
    print("Installing psutil...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil", "-q"])
    import psutil


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class ServiceThresholds:
    """Thresholds for determining health status"""
    memory_mb_warning: float
    memory_mb_critical: float
    threads_warning: int
    threads_critical: int
    handles_warning: int
    handles_critical: int
    cpu_warning: float
    cpu_critical: float


# Service detection patterns and thresholds
SERVICE_CONFIG = {
    "service-manager": {
        "patterns": ["gemma-manager", "service_manager"],
        "exe": "python",
        "thresholds": ServiceThresholds(
            memory_mb_warning=200, memory_mb_critical=400,
            threads_warning=15, threads_critical=30,
            handles_warning=500, handles_critical=1000,
            cpu_warning=10, cpu_critical=30
        )
    },
    "gemma-backend": {
        "patterns": ["gemma", "backend"],
        "exe": "python",
        "port": 5000,
        "thresholds": ServiceThresholds(
            memory_mb_warning=300, memory_mb_critical=600,
            threads_warning=20, threads_critical=40,
            handles_warning=500, handles_critical=1000,
            cpu_warning=15, cpu_critical=50
        )
    },
    "gemma-frontend": {
        "patterns": ["vite", "admin"],
        "exe": "node",
        "port": 3000,
        "thresholds": ServiceThresholds(
            memory_mb_warning=300, memory_mb_critical=600,
            threads_warning=15, threads_critical=30,
            handles_warning=300, handles_critical=600,
            cpu_warning=10, cpu_critical=30
        )
    },
    "preset-manager": {
        "patterns": ["preset-manager", "preset_manager"],
        "exe": "python",
        "port": 5002,
        "thresholds": ServiceThresholds(
            memory_mb_warning=200, memory_mb_critical=400,
            threads_warning=15, threads_critical=30,
            handles_warning=400, handles_critical=800,
            cpu_warning=10, cpu_critical=30
        )
    },
    "pm-frontend": {
        "patterns": ["vite", "preset-manager/admin"],
        "exe": "node",
        "port": 3001,
        "thresholds": ServiceThresholds(
            memory_mb_warning=250, memory_mb_critical=500,
            threads_warning=15, threads_critical=30,
            handles_warning=300, handles_critical=600,
            cpu_warning=10, cpu_critical=30
        )
    },
    "sut-discovery": {
        "patterns": ["sut-discovery", "sut_discovery"],
        "exe": "python",
        "port": 5001,
        "thresholds": ServiceThresholds(
            memory_mb_warning=150, memory_mb_critical=300,
            threads_warning=10, threads_critical=20,
            handles_warning=300, handles_critical=600,
            cpu_warning=5, cpu_critical=20
        )
    },
    "queue-service": {
        "patterns": ["queue-service", "queue_service"],
        "exe": "python",
        "port": 9000,
        "thresholds": ServiceThresholds(
            memory_mb_warning=200, memory_mb_critical=400,
            threads_warning=15, threads_critical=30,
            handles_warning=400, handles_critical=800,
            cpu_warning=10, cpu_critical=30
        )
    },
    "omniparser": {
        "patterns": ["omniparser", "omniparserserver"],
        "exe": "python",
        "port": 8000,  # Can be 8000-8004
        "thresholds": ServiceThresholds(
            memory_mb_warning=4000, memory_mb_critical=6000,  # GPU models are heavy
            threads_warning=25, threads_critical=50,
            handles_warning=500, handles_critical=1000,
            cpu_warning=20, cpu_critical=60
        )
    },
}


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class ServiceSnapshot:
    """Single point-in-time measurement of a service"""
    timestamp: str
    pid: int
    memory_mb: float
    memory_percent: float
    threads: int
    handles: int
    cpu_percent: float
    status: str  # running, sleeping, etc.

    # Health assessment
    memory_health: str  # good, warning, critical
    threads_health: str
    handles_health: str
    cpu_health: str
    overall_health: str


@dataclass
class ServiceProfile:
    """Complete profile of a service over time"""
    name: str
    exe: str
    port: Optional[int]
    pid: int
    thresholds: Dict[str, Any]
    snapshots: List[Dict[str, Any]]

    # Summary stats (computed at end)
    memory_min: float = 0
    memory_max: float = 0
    memory_avg: float = 0
    memory_trend: str = "stable"  # stable, growing, shrinking

    threads_min: int = 0
    threads_max: int = 0
    threads_trend: str = "stable"

    handles_min: int = 0
    handles_max: int = 0
    handles_trend: str = "stable"

    health_score: float = 100.0  # 0-100
    issues: List[str] = None


@dataclass
class ProfileSession:
    """Complete profiling session"""
    session_id: str
    start_time: str
    end_time: str
    duration_seconds: float
    interval_seconds: int
    sample_count: int
    system_info: Dict[str, Any]
    services: Dict[str, Dict[str, Any]]
    summary: Dict[str, Any]


# =============================================================================
# Service Discovery
# =============================================================================

def get_system_info() -> Dict[str, Any]:
    """Get system information"""
    return {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "processor": platform.processor(),
        "cpu_count": psutil.cpu_count(),
        "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
        "python_version": platform.python_version(),
    }


def find_service_process(service_name: str, config: Dict) -> Optional[psutil.Process]:
    """Find a service process by its patterns"""
    patterns = config["patterns"]
    exe = config["exe"]

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            proc_name = proc.info['name'].lower()
            cmdline = ' '.join(proc.info['cmdline'] or []).lower()

            # Check if executable matches
            if exe not in proc_name:
                continue

            # Check if any pattern matches
            if any(pattern.lower() in cmdline for pattern in patterns):
                return proc

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return None


def find_omniparser_instances() -> List[psutil.Process]:
    """Find all OmniParser instances (can be multiple)"""
    instances = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            proc_name = proc.info['name'].lower()
            cmdline = ' '.join(proc.info['cmdline'] or []).lower()

            if 'python' in proc_name and 'omniparser' in cmdline:
                instances.append(proc)

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return instances


def discover_services() -> Dict[str, psutil.Process]:
    """Discover all running RPX services"""
    services = {}

    for name, config in SERVICE_CONFIG.items():
        if name == "omniparser":
            # Handle multiple OmniParser instances
            instances = find_omniparser_instances()
            for i, proc in enumerate(instances):
                instance_name = f"omniparser-{i}" if len(instances) > 1 else "omniparser"
                services[instance_name] = proc
        else:
            proc = find_service_process(name, config)
            if proc:
                services[name] = proc

    return services


# =============================================================================
# Metrics Collection
# =============================================================================

def assess_health(value: float, warning: float, critical: float) -> str:
    """Assess health based on thresholds"""
    if value >= critical:
        return "critical"
    elif value >= warning:
        return "warning"
    return "good"


def collect_snapshot(proc: psutil.Process, thresholds: ServiceThresholds) -> Optional[ServiceSnapshot]:
    """Collect a single snapshot of service metrics"""
    try:
        with proc.oneshot():
            memory_info = proc.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            memory_percent = proc.memory_percent()
            threads = proc.num_threads()

            # Handle count (Windows-specific)
            try:
                handles = proc.num_handles()
            except AttributeError:
                handles = 0  # Not available on non-Windows

            cpu_percent = proc.cpu_percent(interval=0.1)
            status = proc.status()

        # Assess health
        memory_health = assess_health(memory_mb, thresholds.memory_mb_warning, thresholds.memory_mb_critical)
        threads_health = assess_health(threads, thresholds.threads_warning, thresholds.threads_critical)
        handles_health = assess_health(handles, thresholds.handles_warning, thresholds.handles_critical)
        cpu_health = assess_health(cpu_percent, thresholds.cpu_warning, thresholds.cpu_critical)

        # Overall health is worst of all
        healths = [memory_health, threads_health, handles_health, cpu_health]
        if "critical" in healths:
            overall_health = "critical"
        elif "warning" in healths:
            overall_health = "warning"
        else:
            overall_health = "good"

        return ServiceSnapshot(
            timestamp=datetime.now().isoformat(),
            pid=proc.pid,
            memory_mb=round(memory_mb, 2),
            memory_percent=round(memory_percent, 2),
            threads=threads,
            handles=handles,
            cpu_percent=round(cpu_percent, 2),
            status=status,
            memory_health=memory_health,
            threads_health=threads_health,
            handles_health=handles_health,
            cpu_health=cpu_health,
            overall_health=overall_health
        )

    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None


def calculate_trend(values: List[float]) -> str:
    """Calculate trend from a series of values"""
    if len(values) < 3:
        return "stable"

    # Compare first third average to last third average
    third = len(values) // 3
    first_avg = sum(values[:third]) / third
    last_avg = sum(values[-third:]) / third

    change_percent = ((last_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0

    if change_percent > 20:
        return "growing"
    elif change_percent < -20:
        return "shrinking"
    return "stable"


def compute_service_summary(snapshots: List[Dict]) -> Dict[str, Any]:
    """Compute summary statistics for a service"""
    if not snapshots:
        return {}

    memories = [s["memory_mb"] for s in snapshots]
    threads = [s["threads"] for s in snapshots]
    handles = [s["handles"] for s in snapshots]
    cpus = [s["cpu_percent"] for s in snapshots]

    # Count health occurrences
    health_counts = {"good": 0, "warning": 0, "critical": 0}
    for s in snapshots:
        health_counts[s["overall_health"]] += 1

    # Calculate health score (100 = all good, 0 = all critical)
    total = len(snapshots)
    health_score = (health_counts["good"] * 100 + health_counts["warning"] * 50) / total

    # Detect issues
    issues = []
    memory_trend = calculate_trend(memories)
    threads_trend = calculate_trend(threads)
    handles_trend = calculate_trend(handles)

    if memory_trend == "growing":
        issues.append("Memory is growing over time - possible memory leak")
    if threads_trend == "growing":
        issues.append("Thread count is growing - possible thread leak")
    if handles_trend == "growing":
        issues.append("Handle count is growing - possible resource leak")
    if health_counts["critical"] > 0:
        issues.append(f"Service was in critical state {health_counts['critical']} times")

    return {
        "memory_min": round(min(memories), 2),
        "memory_max": round(max(memories), 2),
        "memory_avg": round(sum(memories) / len(memories), 2),
        "memory_trend": memory_trend,
        "threads_min": min(threads),
        "threads_max": max(threads),
        "threads_avg": round(sum(threads) / len(threads), 1),
        "threads_trend": threads_trend,
        "handles_min": min(handles),
        "handles_max": max(handles),
        "handles_avg": round(sum(handles) / len(handles), 1),
        "handles_trend": handles_trend,
        "cpu_min": round(min(cpus), 2),
        "cpu_max": round(max(cpus), 2),
        "cpu_avg": round(sum(cpus) / len(cpus), 2),
        "health_score": round(health_score, 1),
        "health_counts": health_counts,
        "issues": issues,
    }


# =============================================================================
# Main Profiler
# =============================================================================

class ServiceProfiler:
    def __init__(self, duration_minutes: int = 10, interval_seconds: int = 1):
        self.duration_minutes = duration_minutes
        self.interval_seconds = interval_seconds
        self.results_dir = Path(__file__).parent / "results"
        self.results_dir.mkdir(exist_ok=True)

        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.start_time = None
        self.services_data: Dict[str, Dict] = {}

    def discover(self) -> Dict[str, psutil.Process]:
        """Discover and initialize service tracking"""
        services = discover_services()

        for name, proc in services.items():
            # Get config (use omniparser config for all omniparser instances)
            config_name = "omniparser" if name.startswith("omniparser") else name
            config = SERVICE_CONFIG.get(config_name, SERVICE_CONFIG["gemma-backend"])

            self.services_data[name] = {
                "name": name,
                "exe": config["exe"],
                "port": config.get("port"),
                "pid": proc.pid,
                "thresholds": asdict(config["thresholds"]),
                "snapshots": [],
            }

        return services

    def collect_all(self, services: Dict[str, psutil.Process], live: bool = False):
        """Collect metrics from all services"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        if live:
            print(f"\n[{timestamp}] Collecting metrics...")
            print(f"{'Service':<20} {'Memory MB':<12} {'Threads':<10} {'Handles':<10} {'CPU %':<10} {'Health':<10}")
            print("-" * 82)

        for name, proc in services.items():
            config_name = "omniparser" if name.startswith("omniparser") else name
            config = SERVICE_CONFIG.get(config_name, SERVICE_CONFIG["gemma-backend"])

            snapshot = collect_snapshot(proc, config["thresholds"])

            if snapshot:
                self.services_data[name]["snapshots"].append(asdict(snapshot))

                if live:
                    health_colors = {"good": "✓", "warning": "⚠", "critical": "✗"}
                    health_symbol = health_colors[snapshot.overall_health]
                    print(f"{name:<20} {snapshot.memory_mb:<12.1f} {snapshot.threads:<10} "
                          f"{snapshot.handles:<10} {snapshot.cpu_percent:<10.1f} {health_symbol} {snapshot.overall_health}")
            else:
                if live:
                    print(f"{name:<20} {'(process ended)':<50}")

    def run(self, live: bool = False, output_name: Optional[str] = None):
        """Run the profiling session"""
        print("=" * 60)
        print("RPX Service Profiler")
        print("=" * 60)

        # Discover services
        print("\nDiscovering services...")
        services = self.discover()

        if not services:
            print("No RPX services found running!")
            print("\nMake sure services are running. Expected services:")
            for name in SERVICE_CONFIG.keys():
                print(f"  - {name}")
            return None

        print(f"\nFound {len(services)} service(s):")
        for name, proc in services.items():
            print(f"  - {name} (PID: {proc.pid})")

        # Calculate iterations
        total_seconds = self.duration_minutes * 60
        iterations = total_seconds // self.interval_seconds

        print(f"\nProfiling for {self.duration_minutes} minutes "
              f"({iterations} samples at {self.interval_seconds}s intervals)")
        print("Press Ctrl+C to stop early\n")

        self.start_time = datetime.now()

        try:
            for i in range(iterations):
                self.collect_all(services, live=live)

                if not live:
                    progress = (i + 1) / iterations * 100
                    bar = "█" * int(progress / 2) + "░" * (50 - int(progress / 2))
                    print(f"\r[{bar}] {progress:.0f}% ({i+1}/{iterations})", end="", flush=True)

                if i < iterations - 1:
                    time.sleep(self.interval_seconds)

        except KeyboardInterrupt:
            print("\n\nStopped early by user")

        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        print(f"\n\nProfiling complete. Duration: {duration:.1f}s")

        # Compute summaries
        for name, data in self.services_data.items():
            data["summary"] = compute_service_summary(data["snapshots"])

        # Build session data
        session = {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "interval_seconds": self.interval_seconds,
            "sample_count": len(next(iter(self.services_data.values()))["snapshots"]) if self.services_data else 0,
            "system_info": get_system_info(),
            "services": self.services_data,
            "summary": self._compute_overall_summary(),
        }

        # Save results
        filename = f"{output_name or self.session_id}_profile.json"
        output_path = self.results_dir / filename

        with open(output_path, 'w') as f:
            json.dump(session, f, indent=2)

        print(f"\nResults saved to: {output_path}")
        print(f"Open viewer.html and load this file to visualize results")

        # Print summary
        self._print_summary(session)

        return session

    def _compute_overall_summary(self) -> Dict[str, Any]:
        """Compute overall session summary"""
        all_issues = []
        health_scores = []

        for name, data in self.services_data.items():
            if "summary" in data:
                health_scores.append(data["summary"]["health_score"])
                for issue in data["summary"].get("issues", []):
                    all_issues.append(f"{name}: {issue}")

        return {
            "total_services": len(self.services_data),
            "avg_health_score": round(sum(health_scores) / len(health_scores), 1) if health_scores else 0,
            "total_issues": len(all_issues),
            "issues": all_issues,
        }

    def _print_summary(self, session: Dict):
        """Print a summary of the profiling session"""
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)

        summary = session["summary"]
        print(f"\nOverall Health Score: {summary['avg_health_score']}/100")

        if summary["issues"]:
            print(f"\n⚠ Issues Found ({len(summary['issues'])}):")
            for issue in summary["issues"]:
                print(f"  - {issue}")
        else:
            print("\n✓ No issues detected")

        print("\nPer-Service Summary:")
        print(f"{'Service':<20} {'Health':<10} {'Memory Trend':<15} {'Thread Trend':<15}")
        print("-" * 60)

        for name, data in session["services"].items():
            s = data.get("summary", {})
            health = s.get("health_score", 0)
            mem_trend = s.get("memory_trend", "N/A")
            thread_trend = s.get("threads_trend", "N/A")

            health_str = f"{health:.0f}/100"
            if health >= 80:
                health_str = f"✓ {health_str}"
            elif health >= 50:
                health_str = f"⚠ {health_str}"
            else:
                health_str = f"✗ {health_str}"

            print(f"{name:<20} {health_str:<10} {mem_trend:<15} {thread_trend:<15}")


# =============================================================================
# Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="RPX Service Profiler - Monitor services for memory leaks and performance issues"
    )
    parser.add_argument(
        "--duration", "-d", type=int, default=10,
        help="Duration in minutes (default: 10)"
    )
    parser.add_argument(
        "--interval", "-i", type=int, default=1,
        help="Sample interval in seconds (default: 1)"
    )
    parser.add_argument(
        "--live", "-l", action="store_true",
        help="Show live output instead of progress bar"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Custom output filename prefix"
    )

    args = parser.parse_args()

    profiler = ServiceProfiler(
        duration_minutes=args.duration,
        interval_seconds=args.interval
    )

    profiler.run(live=args.live, output_name=args.output)


if __name__ == "__main__":
    main()
