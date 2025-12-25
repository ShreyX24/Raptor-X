"""
Rich Terminal Dashboard - htop-style monitoring for Queue Service.
"""

import logging

# Suppress httpx ping logs (every 1s request would flood the terminal)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

import asyncio
import argparse
import sys
from datetime import datetime
from typing import Dict, Any, Optional

import httpx
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import BarColumn, Progress, TextColumn
from rich import box


console = Console()


class QueueDashboard:
    """Terminal dashboard for Queue Service monitoring."""

    def __init__(self, service_url: str = "http://localhost:9000"):
        self.service_url = service_url.rstrip("/")
        self.refresh_interval = 1.0  # seconds
        self._running = True

    async def fetch_stats(self) -> Optional[Dict[str, Any]]:
        """Fetch current stats from Queue Service."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.service_url}/stats")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def fetch_jobs(self, limit: int = 10) -> Optional[Dict[str, Any]]:
        """Fetch recent jobs from Queue Service."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.service_url}/jobs", params={"limit": limit})
                response.raise_for_status()
                return response.json()
        except Exception:
            return {"jobs": [], "count": 0}

    async def fetch_health(self) -> Optional[Dict[str, Any]]:
        """Fetch health status from Queue Service."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.service_url}/probe")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def create_header_panel(self, health: Dict[str, Any]) -> Panel:
        """Create the header panel with service info."""
        status = health.get("queue_service_status", "unknown")
        omniparser = health.get("omniparser_status", {})
        omni_status = omniparser.get("status", "unknown")

        status_color = "green" if status == "running" else "red"
        omni_color = "green" if omni_status == "healthy" else "red"

        header_text = Text()
        header_text.append("QUEUE SERVICE DASHBOARD", style="bold white")
        header_text.append(" | ")
        header_text.append(f"Service: ", style="dim")
        header_text.append(f"{status.upper()}", style=f"bold {status_color}")
        header_text.append(" | ")
        header_text.append(f"OmniParser: ", style="dim")
        header_text.append(f"{omni_status.upper()}", style=f"bold {omni_color}")
        header_text.append(" | ")
        header_text.append(f"Target: ", style="dim")
        header_text.append(omniparser.get("omniparser_server", "N/A"), style="cyan")

        return Panel(header_text, box=box.ROUNDED, style="blue")

    def create_stats_panel(self, stats: Dict[str, Any]) -> Panel:
        """Create the statistics panel."""
        if "error" in stats:
            return Panel(
                Text(f"Error: {stats['error']}", style="red"),
                title="[bold]Queue Statistics[/bold]",
                box=box.ROUNDED,
            )

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Label", style="dim")
        table.add_column("Value", style="bold")

        # Queue stats
        queue_size = stats.get("current_queue_size", 0)
        queue_color = "green" if queue_size < 10 else "yellow" if queue_size < 50 else "red"

        table.add_row("Queue Size", f"[{queue_color}]{queue_size}[/{queue_color}]")
        table.add_row("Worker Running", "[green]Yes[/green]" if stats.get("worker_running") else "[red]No[/red]")
        table.add_row("", "")  # Spacer

        # Request counts
        total = stats.get("total_requests", 0)
        success = stats.get("successful_requests", 0)
        failed = stats.get("failed_requests", 0)
        timeout = stats.get("timeout_requests", 0)

        table.add_row("Total Requests", str(total))
        table.add_row("Successful", f"[green]{success}[/green]")
        table.add_row("Failed", f"[red]{failed}[/red]" if failed > 0 else "0")
        table.add_row("Timeouts", f"[yellow]{timeout}[/yellow]" if timeout > 0 else "0")
        table.add_row("", "")  # Spacer

        # Performance
        table.add_row("Avg Processing", f"{stats.get('avg_processing_time', 0):.2f}s")
        table.add_row("Avg Queue Wait", f"{stats.get('avg_queue_wait_time', 0):.2f}s")
        table.add_row("Req/min", f"{stats.get('requests_per_minute', 0):.1f}")

        # Uptime
        uptime = stats.get("uptime_seconds", 0)
        hours, remainder = divmod(int(uptime), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        table.add_row("Uptime", uptime_str)

        return Panel(table, title="[bold]Queue Statistics[/bold]", box=box.ROUNDED)

    def create_queue_bar(self, stats: Dict[str, Any]) -> Panel:
        """Create a visual queue depth bar."""
        queue_size = stats.get("current_queue_size", 0)
        max_size = 100  # Default max

        # Create progress bar for queue depth
        filled = min(queue_size, max_size)
        bar_width = 40
        filled_width = int((filled / max_size) * bar_width)
        empty_width = bar_width - filled_width

        if queue_size < 10:
            color = "green"
        elif queue_size < 50:
            color = "yellow"
        else:
            color = "red"

        bar = Text()
        bar.append("Queue Depth: [")
        bar.append("=" * filled_width, style=f"bold {color}")
        bar.append(" " * empty_width)
        bar.append(f"] {queue_size}/{max_size}")

        return Panel(bar, box=box.ROUNDED)

    def create_jobs_panel(self, jobs_data: Dict[str, Any]) -> Panel:
        """Create the job history table."""
        jobs = jobs_data.get("jobs", [])

        table = Table(box=box.SIMPLE)
        table.add_column("Job ID", style="cyan", width=10)
        table.add_column("Time", style="dim", width=10)
        table.add_column("Status", width=8)
        table.add_column("Proc Time", justify="right", width=10)
        table.add_column("Wait Time", justify="right", width=10)
        table.add_column("Size", justify="right", width=8)

        for job in jobs[:10]:  # Show last 10 jobs
            status = job.get("status", "unknown")
            if status == "success":
                status_text = "[green]SUCCESS[/green]"
            elif status == "failed":
                status_text = "[red]FAILED[/red]"
            elif status == "timeout":
                status_text = "[yellow]TIMEOUT[/yellow]"
            else:
                status_text = status

            # Parse timestamp
            try:
                ts = datetime.fromisoformat(job.get("timestamp", ""))
                time_str = ts.strftime("%H:%M:%S")
            except:
                time_str = "N/A"

            # Format size
            size = job.get("image_size", 0)
            if size > 1024 * 1024:
                size_str = f"{size / (1024 * 1024):.1f}MB"
            elif size > 1024:
                size_str = f"{size / 1024:.1f}KB"
            else:
                size_str = f"{size}B"

            table.add_row(
                job.get("job_id", "N/A"),
                time_str,
                status_text,
                f"{job.get('processing_time', 0):.2f}s",
                f"{job.get('queue_wait_time', 0):.2f}s",
                size_str,
            )

        return Panel(table, title=f"[bold]Recent Jobs ({jobs_data.get('count', 0)} total)[/bold]", box=box.ROUNDED)

    def create_footer_panel(self) -> Panel:
        """Create the footer panel with help info."""
        footer = Text()
        footer.append("Press ", style="dim")
        footer.append("Ctrl+C", style="bold yellow")
        footer.append(" to exit | ", style="dim")
        footer.append("Refresh: 1s", style="dim")
        footer.append(" | ", style="dim")
        footer.append(f"Connected to: {self.service_url}", style="cyan")

        return Panel(footer, box=box.ROUNDED, style="dim")

    def create_layout(self) -> Layout:
        """Create the dashboard layout."""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )

        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=2),
        )

        layout["left"].split_column(
            Layout(name="stats"),
            Layout(name="queue_bar", size=3),
        )

        return layout

    async def update_layout(self, layout: Layout):
        """Update all panels with fresh data."""
        # Fetch data concurrently
        stats_task = asyncio.create_task(self.fetch_stats())
        jobs_task = asyncio.create_task(self.fetch_jobs())
        health_task = asyncio.create_task(self.fetch_health())

        stats, jobs, health = await asyncio.gather(stats_task, jobs_task, health_task)

        # Update panels
        layout["header"].update(self.create_header_panel(health))
        layout["stats"].update(self.create_stats_panel(stats))
        layout["queue_bar"].update(self.create_queue_bar(stats))
        layout["right"].update(self.create_jobs_panel(jobs))
        layout["footer"].update(self.create_footer_panel())

    async def run(self):
        """Run the dashboard."""
        layout = self.create_layout()

        console.print(f"\n[bold cyan]Connecting to Queue Service at {self.service_url}...[/bold cyan]\n")

        # Initial update
        await self.update_layout(layout)

        with Live(layout, console=console, refresh_per_second=1, screen=True):
            try:
                while self._running:
                    await self.update_layout(layout)
                    await asyncio.sleep(self.refresh_interval)
            except KeyboardInterrupt:
                self._running = False

        console.print("\n[bold yellow]Dashboard closed.[/bold yellow]")


def main():
    """Entry point for queue-dashboard command."""
    parser = argparse.ArgumentParser(description="Queue Service Terminal Dashboard")
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:9000",
        help="Queue Service URL (default: http://localhost:9000)"
    )
    parser.add_argument(
        "--refresh",
        type=float,
        default=1.0,
        help="Refresh interval in seconds (default: 1.0)"
    )

    args = parser.parse_args()

    dashboard = QueueDashboard(service_url=args.url)
    dashboard.refresh_interval = args.refresh

    try:
        asyncio.run(dashboard.run())
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Exiting...[/bold yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
