"""
RPX Service Profiler - GUI Version
===================================
Interactive profiler with Start/Stop controls.

Usage:
    python profiler_gui.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import json
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import queue

try:
    import psutil
except ImportError:
    print("Installing psutil...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil", "-q"])
    import psutil

# Import from main profiler
from service_profiler import (
    SERVICE_CONFIG, ServiceThresholds, discover_services,
    collect_snapshot, compute_service_summary, get_system_info,
    find_omniparser_instances
)


class ProfilerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("RPX Service Profiler")
        self.root.geometry("1000x700")
        self.root.configure(bg='#0d1117')

        # State
        self.is_running = False
        self.profiler_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.services_data: Dict = {}
        self.start_time: Optional[datetime] = None
        self.sample_count = 0
        self.update_queue = queue.Queue()

        # Style
        self.setup_styles()

        # Build UI
        self.build_ui()

        # Start UI update loop
        self.update_ui()

    def setup_styles(self):
        """Configure ttk styles for dark theme"""
        style = ttk.Style()
        style.theme_use('clam')

        # Colors
        bg_primary = '#0d1117'
        bg_secondary = '#161b22'
        bg_tertiary = '#21262d'
        border = '#30363d'
        text_primary = '#e6edf3'
        text_secondary = '#8b949e'
        accent = '#58a6ff'
        success = '#3fb950'
        warning = '#d29922'
        danger = '#f85149'

        # Configure styles
        style.configure('Dark.TFrame', background=bg_primary)
        style.configure('Card.TFrame', background=bg_secondary)
        style.configure('Dark.TLabel', background=bg_primary, foreground=text_primary)
        style.configure('Card.TLabel', background=bg_secondary, foreground=text_primary)
        style.configure('Muted.TLabel', background=bg_secondary, foreground=text_secondary)
        style.configure('Header.TLabel', background=bg_primary, foreground=text_primary, font=('Segoe UI', 16, 'bold'))
        style.configure('Good.TLabel', background=bg_secondary, foreground=success)
        style.configure('Warning.TLabel', background=bg_secondary, foreground=warning)
        style.configure('Critical.TLabel', background=bg_secondary, foreground=danger)

        style.configure('Start.TButton', font=('Segoe UI', 11, 'bold'))
        style.configure('Stop.TButton', font=('Segoe UI', 11, 'bold'))

    def build_ui(self):
        """Build the main UI"""
        # Main container
        main_frame = ttk.Frame(self.root, style='Dark.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header
        header_frame = ttk.Frame(main_frame, style='Dark.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(header_frame, text="RPX Service Profiler", style='Header.TLabel').pack(side=tk.LEFT)

        # Controls frame
        controls_frame = ttk.Frame(header_frame, style='Dark.TFrame')
        controls_frame.pack(side=tk.RIGHT)

        # Interval selector
        ttk.Label(controls_frame, text="Interval:", style='Dark.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        self.interval_var = tk.StringVar(value="1")
        interval_combo = ttk.Combobox(controls_frame, textvariable=self.interval_var, width=8,
                                       values=["1", "2", "3", "5", "10", "30"], state='readonly')
        interval_combo.pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(controls_frame, text="sec", style='Dark.TLabel').pack(side=tk.LEFT, padx=(0, 20))

        # Start/Stop buttons
        self.start_btn = tk.Button(controls_frame, text="▶ START", command=self.start_profiling,
                                    bg='#238636', fg='white', font=('Segoe UI', 10, 'bold'),
                                    padx=20, pady=5, relief=tk.FLAT, cursor='hand2')
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_btn = tk.Button(controls_frame, text="■ STOP", command=self.stop_profiling,
                                   bg='#da3633', fg='white', font=('Segoe UI', 10, 'bold'),
                                   padx=20, pady=5, relief=tk.FLAT, cursor='hand2', state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.save_btn = tk.Button(controls_frame, text="💾 SAVE", command=self.save_results,
                                   bg='#1f6feb', fg='white', font=('Segoe UI', 10, 'bold'),
                                   padx=20, pady=5, relief=tk.FLAT, cursor='hand2', state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT)

        # Status bar
        status_frame = ttk.Frame(main_frame, style='Card.TFrame')
        status_frame.pack(fill=tk.X, pady=(0, 15))

        self.status_label = ttk.Label(status_frame, text="● Stopped", style='Muted.TLabel')
        self.status_label.pack(side=tk.LEFT, padx=15, pady=10)

        self.duration_label = ttk.Label(status_frame, text="Duration: --:--", style='Muted.TLabel')
        self.duration_label.pack(side=tk.LEFT, padx=15, pady=10)

        self.samples_label = ttk.Label(status_frame, text="Samples: 0", style='Muted.TLabel')
        self.samples_label.pack(side=tk.LEFT, padx=15, pady=10)

        self.health_label = ttk.Label(status_frame, text="Health: --", style='Muted.TLabel')
        self.health_label.pack(side=tk.RIGHT, padx=15, pady=10)

        # Services table frame
        table_frame = ttk.Frame(main_frame, style='Card.TFrame')
        table_frame.pack(fill=tk.BOTH, expand=True)

        # Table header
        header_row = ttk.Frame(table_frame, style='Card.TFrame')
        header_row.pack(fill=tk.X, padx=10, pady=(10, 5))

        headers = [("Service", 150), ("PID", 60), ("Memory", 100), ("Threads", 70),
                   ("Handles", 70), ("CPU", 70), ("Health", 80), ("Trend", 100)]

        for text, width in headers:
            lbl = ttk.Label(header_row, text=text, style='Muted.TLabel', width=width//8)
            lbl.pack(side=tk.LEFT, padx=5)

        ttk.Separator(table_frame, orient='horizontal').pack(fill=tk.X, padx=10)

        # Scrollable services list
        canvas = tk.Canvas(table_frame, bg='#161b22', highlightthickness=0)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=canvas.yview)
        self.services_frame = ttk.Frame(canvas, style='Card.TFrame')

        self.services_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.services_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Service rows dict
        self.service_rows: Dict[str, Dict[str, ttk.Label]] = {}

        # Issues section
        issues_frame = ttk.Frame(main_frame, style='Card.TFrame')
        issues_frame.pack(fill=tk.X, pady=(15, 0))

        ttk.Label(issues_frame, text="Issues", style='Card.TLabel',
                  font=('Segoe UI', 11, 'bold')).pack(anchor=tk.W, padx=15, pady=(10, 5))

        self.issues_text = tk.Text(issues_frame, height=4, bg='#21262d', fg='#e6edf3',
                                    font=('Consolas', 10), relief=tk.FLAT, wrap=tk.WORD)
        self.issues_text.pack(fill=tk.X, padx=15, pady=(0, 10))
        self.issues_text.insert('1.0', "No issues detected")
        self.issues_text.configure(state=tk.DISABLED)

    def create_service_row(self, name: str) -> Dict[str, ttk.Label]:
        """Create a row for a service in the table"""
        row_frame = ttk.Frame(self.services_frame, style='Card.TFrame')
        row_frame.pack(fill=tk.X, pady=2)

        labels = {}

        # Service name
        labels['name'] = ttk.Label(row_frame, text=name, style='Card.TLabel', width=18)
        labels['name'].pack(side=tk.LEFT, padx=5)

        # PID
        labels['pid'] = ttk.Label(row_frame, text="--", style='Muted.TLabel', width=7)
        labels['pid'].pack(side=tk.LEFT, padx=5)

        # Memory
        labels['memory'] = ttk.Label(row_frame, text="-- MB", style='Card.TLabel', width=12)
        labels['memory'].pack(side=tk.LEFT, padx=5)

        # Threads
        labels['threads'] = ttk.Label(row_frame, text="--", style='Card.TLabel', width=8)
        labels['threads'].pack(side=tk.LEFT, padx=5)

        # Handles
        labels['handles'] = ttk.Label(row_frame, text="--", style='Card.TLabel', width=8)
        labels['handles'].pack(side=tk.LEFT, padx=5)

        # CPU
        labels['cpu'] = ttk.Label(row_frame, text="--%", style='Card.TLabel', width=8)
        labels['cpu'].pack(side=tk.LEFT, padx=5)

        # Health
        labels['health'] = ttk.Label(row_frame, text="--", style='Good.TLabel', width=9)
        labels['health'].pack(side=tk.LEFT, padx=5)

        # Trend
        labels['trend'] = ttk.Label(row_frame, text="--", style='Muted.TLabel', width=12)
        labels['trend'].pack(side=tk.LEFT, padx=5)

        return labels

    def start_profiling(self):
        """Start the profiling session"""
        self.is_running = True
        self.stop_event.clear()
        self.services_data = {}
        self.sample_count = 0
        self.start_time = datetime.now()

        # Update UI
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.save_btn.configure(state=tk.DISABLED)
        self.status_label.configure(text="● Running", foreground='#3fb950')

        # Clear service rows
        for widget in self.services_frame.winfo_children():
            widget.destroy()
        self.service_rows = {}

        # Start profiler thread
        interval = int(self.interval_var.get())
        self.profiler_thread = threading.Thread(target=self.profiling_loop, args=(interval,), daemon=True)
        self.profiler_thread.start()

    def stop_profiling(self):
        """Stop the profiling session"""
        self.stop_event.set()
        self.is_running = False

        # Update UI
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.save_btn.configure(state=tk.NORMAL)
        self.status_label.configure(text="● Stopped", foreground='#8b949e')

    def profiling_loop(self, interval: int):
        """Main profiling loop (runs in thread)"""
        while not self.stop_event.is_set():
            try:
                # Discover services
                services = discover_services()

                # Initialize new services
                for name, proc in services.items():
                    if name not in self.services_data:
                        config_name = "omniparser" if name.startswith("omniparser") else name
                        config = SERVICE_CONFIG.get(config_name, SERVICE_CONFIG["gemma-backend"])

                        self.services_data[name] = {
                            "name": name,
                            "exe": config["exe"],
                            "port": config.get("port"),
                            "pid": proc.pid,
                            "thresholds": config["thresholds"],
                            "snapshots": [],
                        }

                # Collect snapshots
                for name, proc in services.items():
                    config_name = "omniparser" if name.startswith("omniparser") else name
                    config = SERVICE_CONFIG.get(config_name, SERVICE_CONFIG["gemma-backend"])
                    thresholds = config["thresholds"]

                    snapshot = collect_snapshot(proc, thresholds)
                    if snapshot:
                        self.services_data[name]["snapshots"].append(snapshot.__dict__)
                        # Queue UI update
                        self.update_queue.put(('snapshot', name, snapshot))

                self.sample_count += 1
                self.update_queue.put(('sample_count', self.sample_count, None))

                # Wait for interval or stop
                self.stop_event.wait(interval)

            except Exception as e:
                self.update_queue.put(('error', str(e), None))

    def update_ui(self):
        """Process UI updates from the profiler thread"""
        try:
            while True:
                msg_type, data1, data2 = self.update_queue.get_nowait()

                if msg_type == 'snapshot':
                    name, snapshot = data1, data2
                    self.update_service_row(name, snapshot)

                elif msg_type == 'sample_count':
                    self.samples_label.configure(text=f"Samples: {data1}")

                elif msg_type == 'error':
                    print(f"Error: {data1}")

        except queue.Empty:
            pass

        # Update duration
        if self.is_running and self.start_time:
            duration = datetime.now() - self.start_time
            mins = int(duration.total_seconds() // 60)
            secs = int(duration.total_seconds() % 60)
            self.duration_label.configure(text=f"Duration: {mins:02d}:{secs:02d}")

        # Update health score
        self.update_overall_health()

        # Update issues
        self.update_issues()

        # Schedule next update
        self.root.after(500, self.update_ui)

    def update_service_row(self, name: str, snapshot):
        """Update a service row with new data"""
        if name not in self.service_rows:
            self.service_rows[name] = self.create_service_row(name)

        labels = self.service_rows[name]

        labels['pid'].configure(text=str(snapshot.pid))
        labels['memory'].configure(text=f"{snapshot.memory_mb:.1f} MB")
        labels['threads'].configure(text=str(snapshot.threads))
        labels['handles'].configure(text=str(snapshot.handles))
        labels['cpu'].configure(text=f"{snapshot.cpu_percent:.1f}%")

        # Health color
        health_styles = {'good': 'Good.TLabel', 'warning': 'Warning.TLabel', 'critical': 'Critical.TLabel'}
        labels['health'].configure(text=snapshot.overall_health.upper(), style=health_styles[snapshot.overall_health])

        # Calculate trend if we have enough data
        if name in self.services_data and len(self.services_data[name]['snapshots']) >= 3:
            memories = [s['memory_mb'] for s in self.services_data[name]['snapshots']]
            trend = self.calculate_trend(memories)
            trend_icons = {'growing': '↑ growing', 'shrinking': '↓ shrinking', 'stable': '→ stable'}
            labels['trend'].configure(text=trend_icons[trend])

            trend_styles = {'growing': 'Critical.TLabel', 'shrinking': 'Good.TLabel', 'stable': 'Muted.TLabel'}
            labels['trend'].configure(style=trend_styles[trend])

    def calculate_trend(self, values) -> str:
        """Calculate trend from values"""
        if len(values) < 3:
            return "stable"

        third = len(values) // 3
        first_avg = sum(values[:third]) / third
        last_avg = sum(values[-third:]) / third

        change_percent = ((last_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0

        if change_percent > 15:
            return "growing"
        elif change_percent < -15:
            return "shrinking"
        return "stable"

    def update_overall_health(self):
        """Update overall health score"""
        if not self.services_data:
            return

        health_scores = []
        for name, data in self.services_data.items():
            if data['snapshots']:
                last = data['snapshots'][-1]
                score = 100 if last['overall_health'] == 'good' else (50 if last['overall_health'] == 'warning' else 0)
                health_scores.append(score)

        if health_scores:
            avg = sum(health_scores) / len(health_scores)
            color = '#3fb950' if avg >= 80 else ('#d29922' if avg >= 50 else '#f85149')
            self.health_label.configure(text=f"Health: {avg:.0f}/100", foreground=color)

    def update_issues(self):
        """Update issues list"""
        issues = []

        for name, data in self.services_data.items():
            if len(data['snapshots']) >= 5:
                memories = [s['memory_mb'] for s in data['snapshots']]
                threads = [s['threads'] for s in data['snapshots']]
                handles = [s['handles'] for s in data['snapshots']]

                if self.calculate_trend(memories) == 'growing':
                    issues.append(f"⚠ {name}: Memory is growing - possible leak")
                if self.calculate_trend(threads) == 'growing':
                    issues.append(f"⚠ {name}: Thread count growing - possible thread leak")
                if self.calculate_trend(handles) == 'growing':
                    issues.append(f"⚠ {name}: Handle count growing - possible resource leak")

                # Check for critical states
                critical_count = sum(1 for s in data['snapshots'][-5:] if s['overall_health'] == 'critical')
                if critical_count >= 3:
                    issues.append(f"✗ {name}: Service in critical state")

        self.issues_text.configure(state=tk.NORMAL)
        self.issues_text.delete('1.0', tk.END)
        if issues:
            self.issues_text.insert('1.0', '\n'.join(issues))
        else:
            self.issues_text.insert('1.0', "✓ No issues detected")
        self.issues_text.configure(state=tk.DISABLED)

    def save_results(self):
        """Save profiling results to JSON"""
        if not self.services_data:
            messagebox.showwarning("No Data", "No profiling data to save")
            return

        # Compute summaries
        for name, data in self.services_data.items():
            # Convert thresholds to dict if needed
            if hasattr(data['thresholds'], '__dict__'):
                data['thresholds'] = data['thresholds'].__dict__
            data['summary'] = compute_service_summary(data['snapshots'])

        # Build session
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds() if self.start_time else 0

        session = {
            "session_id": self.start_time.strftime("%Y%m%d_%H%M%S") if self.start_time else "unknown",
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "interval_seconds": int(self.interval_var.get()),
            "sample_count": self.sample_count,
            "system_info": get_system_info(),
            "services": self.services_data,
            "summary": self.compute_overall_summary(),
        }

        # Ask for save location
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)

        default_name = f"{session['session_id']}_profile.json"
        filepath = filedialog.asksaveasfilename(
            initialdir=results_dir,
            initialfile=default_name,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )

        if filepath:
            with open(filepath, 'w') as f:
                json.dump(session, f, indent=2, default=str)
            messagebox.showinfo("Saved", f"Results saved to:\n{filepath}\n\nOpen viewer.html to visualize")

    def compute_overall_summary(self) -> Dict:
        """Compute overall summary"""
        all_issues = []
        health_scores = []

        for name, data in self.services_data.items():
            if "summary" in data:
                health_scores.append(data["summary"].get("health_score", 100))
                for issue in data["summary"].get("issues", []):
                    all_issues.append(f"{name}: {issue}")

        return {
            "total_services": len(self.services_data),
            "avg_health_score": round(sum(health_scores) / len(health_scores), 1) if health_scores else 0,
            "total_issues": len(all_issues),
            "issues": all_issues,
        }


def main():
    root = tk.Tk()
    root.configure(bg='#0d1117')

    # Set icon if available
    try:
        root.iconbitmap(default='')
    except:
        pass

    app = ProfilerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
