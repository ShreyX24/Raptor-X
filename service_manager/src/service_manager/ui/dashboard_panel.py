"""
Dashboard Panel - Queue Service monitoring dashboard
"""

import json
from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QGroupBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor


class StatsCard(QFrame):
    """Card displaying a single statistic"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #808080; font-size: 9pt;")

        self.value_label = QLabel("--")
        self.value_label.setStyleSheet("color: #ffffff; font-size: 18pt; font-weight: bold;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str, color: str = "#ffffff"):
        self.value_label.setText(value)
        self.value_label.setStyleSheet(f"color: {color}; font-size: 18pt; font-weight: bold;")


class QueueDepthBar(QFrame):
    """Visual bar showing queue depth"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.max_queue_size = 100
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        self.title = QLabel("Queue Depth")
        self.title.setStyleSheet("font-weight: bold;")
        self.count_label = QLabel("0/100")
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.count_label)
        layout.addLayout(header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.max_queue_size)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self._set_bar_color("#4ec9b0")
        layout.addWidget(self.progress_bar)

    def _set_bar_color(self, color: str):
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                height: 20px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """)

    def set_depth(self, current: int, max_size: int = 100):
        self.max_queue_size = max_size
        self.progress_bar.setRange(0, max_size)
        self.progress_bar.setValue(min(current, max_size))
        self.count_label.setText(f"{current}/{max_size}")

        # Color based on fill level
        percentage = (current / max_size) * 100 if max_size > 0 else 0
        if percentage > 80:
            self._set_bar_color("#f48771")  # Red
        elif percentage > 50:
            self._set_bar_color("#dcdcaa")  # Yellow
        else:
            self._set_bar_color("#4ec9b0")  # Green


class OmniParserHealthWidget(QFrame):
    """Widget showing health status of OmniParser instances"""

    DOT_FILLED = "\u25CF"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel("OmniParser Instances")
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        self.instances_layout = QVBoxLayout()
        layout.addLayout(self.instances_layout)
        layout.addStretch()

    def update_instances(self, health_data: List[Dict[str, Any]]):
        """Update display with health data for each instance"""
        # Clear existing
        while self.instances_layout.count():
            item = self.instances_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not health_data:
            no_data = QLabel("No OmniParser servers configured")
            no_data.setStyleSheet("color: #808080; font-style: italic;")
            self.instances_layout.addWidget(no_data)
            return

        for instance in health_data:
            row = QHBoxLayout()

            status = instance.get("status", "unknown")
            colors = {
                "healthy": "#4ec9b0",
                "unhealthy": "#f48771",
                "unknown": "#808080",
            }
            color = colors.get(status, "#808080")

            dot = QLabel(self.DOT_FILLED)
            dot.setStyleSheet(f"color: {color}; font-size: 12pt;")
            dot.setFixedWidth(20)

            name = QLabel(instance.get("name", "Unknown"))
            url = QLabel(instance.get("url", ""))
            url.setStyleSheet("color: #808080;")

            row.addWidget(dot)
            row.addWidget(name)
            row.addWidget(url)
            row.addStretch()

            container = QWidget()
            container.setLayout(row)
            self.instances_layout.addWidget(container)


class JobsTable(QTableWidget):
    """Table displaying recent jobs"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels([
            "Job ID", "Status", "Queue Wait", "Process Time", "Timestamp"
        ])

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)

        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.verticalHeader().setVisible(False)

        self.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                gridline-color: #3d3d3d;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 4px;
                border: none;
                border-bottom: 1px solid #3d3d3d;
            }
        """)

    def update_jobs(self, jobs: List[Dict[str, Any]]):
        """Update table with job data"""
        self.setRowCount(len(jobs))

        status_colors = {
            "success": "#4ec9b0",
            "failed": "#f48771",
            "timeout": "#dcdcaa",
        }

        for row, job in enumerate(jobs):
            # Job ID
            job_id = job.get("job_id", "")
            if len(job_id) > 8:
                job_id = job_id[:8] + "..."
            self.setItem(row, 0, QTableWidgetItem(job_id))

            # Status
            status = job.get("status", "")
            status_item = QTableWidgetItem(status.capitalize())
            color = status_colors.get(status, "#ffffff")
            status_item.setForeground(QColor(color))
            self.setItem(row, 1, status_item)

            # Queue wait time
            wait = job.get("queue_wait_time", 0)
            self.setItem(row, 2, QTableWidgetItem(f"{wait:.2f}s"))

            # Process time
            process = job.get("processing_time", 0)
            self.setItem(row, 3, QTableWidgetItem(f"{process:.2f}s"))

            # Timestamp
            timestamp = job.get("timestamp", "")
            if timestamp:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    timestamp = dt.strftime("%H:%M:%S")
                except:
                    pass
            self.setItem(row, 4, QTableWidgetItem(timestamp))


class DashboardPanel(QWidget):
    """Main dashboard panel for queue service monitoring"""

    def __init__(self, queue_service_url: str = "http://localhost:9000", parent=None):
        super().__init__(parent)
        self.queue_service_url = queue_service_url
        self.network_manager = QNetworkAccessManager(self)

        self._setup_ui()
        self._setup_refresh_timer()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header with status indicator
        header = QHBoxLayout()

        self.service_status = QLabel("\u25CF Queue Service")
        self.service_status.setStyleSheet("color: #808080; font-weight: bold;")
        header.addWidget(self.service_status)

        header.addStretch()

        self.refresh_label = QLabel("Refreshing every 2s")
        self.refresh_label.setStyleSheet("color: #808080; font-size: 9pt;")
        header.addWidget(self.refresh_label)

        layout.addLayout(header)

        # Stats cards row
        stats_layout = QHBoxLayout()

        self.total_card = StatsCard("Total Requests")
        self.success_card = StatsCard("Successful")
        self.failed_card = StatsCard("Failed")
        self.rate_card = StatsCard("Req/min")

        stats_layout.addWidget(self.total_card)
        stats_layout.addWidget(self.success_card)
        stats_layout.addWidget(self.failed_card)
        stats_layout.addWidget(self.rate_card)

        layout.addLayout(stats_layout)

        # Queue depth bar
        self.queue_depth = QueueDepthBar()
        layout.addWidget(self.queue_depth)

        # Middle section: OmniParser health + timing stats
        middle_layout = QHBoxLayout()

        self.omniparser_health = OmniParserHealthWidget()
        middle_layout.addWidget(self.omniparser_health, 1)

        # Timing stats
        timing_group = QGroupBox("Performance")
        timing_layout = QVBoxLayout(timing_group)

        self.avg_process_label = QLabel("Avg Process Time: --")
        self.avg_queue_label = QLabel("Avg Queue Wait: --")
        self.uptime_label = QLabel("Uptime: --")
        self.worker_label = QLabel("Worker: --")

        timing_layout.addWidget(self.avg_process_label)
        timing_layout.addWidget(self.avg_queue_label)
        timing_layout.addWidget(self.uptime_label)
        timing_layout.addWidget(self.worker_label)
        timing_layout.addStretch()

        middle_layout.addWidget(timing_group, 1)

        layout.addLayout(middle_layout)

        # Jobs table
        jobs_group = QGroupBox("Recent Jobs")
        jobs_layout = QVBoxLayout(jobs_group)
        self.jobs_table = JobsTable()
        jobs_layout.addWidget(self.jobs_table)

        layout.addWidget(jobs_group, 1)

    def _setup_refresh_timer(self):
        """Setup auto-refresh timer"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_data)
        # Don't start automatically - will be started when dashboard is shown

    def set_queue_service_url(self, url: str):
        """Update the queue service URL"""
        self.queue_service_url = url

    def refresh_data(self):
        """Fetch fresh data from queue service"""
        self._fetch_stats()
        self._fetch_jobs()
        self._fetch_health()

    def _fetch_stats(self):
        """Fetch /stats endpoint"""
        url = QUrl(f"{self.queue_service_url}/stats")
        request = QNetworkRequest(url)
        request.setTransferTimeout(5000)

        reply = self.network_manager.get(request)
        reply.finished.connect(lambda: self._handle_stats_response(reply))

    def _fetch_jobs(self):
        """Fetch /jobs endpoint"""
        url = QUrl(f"{self.queue_service_url}/jobs?limit=10")
        request = QNetworkRequest(url)
        request.setTransferTimeout(5000)

        reply = self.network_manager.get(request)
        reply.finished.connect(lambda: self._handle_jobs_response(reply))

    def _fetch_health(self):
        """Fetch /probe endpoint for OmniParser health"""
        url = QUrl(f"{self.queue_service_url}/probe")
        request = QNetworkRequest(url)
        request.setTransferTimeout(5000)

        reply = self.network_manager.get(request)
        reply.finished.connect(lambda: self._handle_health_response(reply))

    def _handle_stats_response(self, reply: QNetworkReply):
        """Handle stats API response"""
        if reply.error() == QNetworkReply.NoError:
            try:
                data = json.loads(reply.readAll().data().decode())
                self._update_stats_display(data)
                self._set_service_connected(True)
            except Exception:
                self._set_service_connected(False)
        else:
            self._set_service_connected(False)
        reply.deleteLater()

    def _handle_jobs_response(self, reply: QNetworkReply):
        """Handle jobs API response"""
        if reply.error() == QNetworkReply.NoError:
            try:
                data = json.loads(reply.readAll().data().decode())
                jobs = data.get("jobs", [])
                self.jobs_table.update_jobs(jobs)
            except:
                pass
        reply.deleteLater()

    def _handle_health_response(self, reply: QNetworkReply):
        """Handle health/probe API response"""
        if reply.error() == QNetworkReply.NoError:
            try:
                data = json.loads(reply.readAll().data().decode())
                omniparser_status = data.get("omniparser_status", {})
                health_list = []

                # Handle multiple formats from queue-service
                if isinstance(omniparser_status, list):
                    # List of instances: [{"url": "...", "status": "..."}, ...]
                    for i, inst in enumerate(omniparser_status):
                        health_list.append({
                            "name": inst.get("name", f"Instance {i+1}"),
                            "url": inst.get("url") or inst.get("omniparser_server", ""),
                            "status": inst.get("status", "unknown"),
                        })
                elif isinstance(omniparser_status, dict):
                    if "omniparser_server" in omniparser_status:
                        # Single instance format
                        health_list.append({
                            "name": "Primary",
                            "url": omniparser_status.get("omniparser_server", ""),
                            "status": omniparser_status.get("status", "unknown"),
                        })
                    else:
                        # Dict keyed by URL or name
                        for key, value in omniparser_status.items():
                            if isinstance(value, dict):
                                health_list.append({
                                    "name": value.get("name", key[:20]),
                                    "url": value.get("url", key),
                                    "status": value.get("status", "unknown"),
                                })

                self.omniparser_health.update_instances(health_list)
            except:
                pass
        reply.deleteLater()

    def _update_stats_display(self, data: dict):
        """Update UI with stats data"""
        self.total_card.set_value(str(data.get("total_requests", 0)))
        self.success_card.set_value(
            str(data.get("successful_requests", 0)),
            "#4ec9b0"
        )

        failed = data.get("failed_requests", 0) + data.get("timeout_requests", 0)
        self.failed_card.set_value(
            str(failed),
            "#f48771" if failed > 0 else "#ffffff"
        )

        self.rate_card.set_value(f"{data.get('requests_per_minute', 0):.1f}")

        self.queue_depth.set_depth(
            data.get("current_queue_size", 0),
            100
        )

        self.avg_process_label.setText(
            f"Avg Process Time: {data.get('avg_processing_time', 0):.2f}s"
        )
        self.avg_queue_label.setText(
            f"Avg Queue Wait: {data.get('avg_queue_wait_time', 0):.2f}s"
        )

        uptime = data.get("uptime_seconds", 0)
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        self.uptime_label.setText(f"Uptime: {hours}h {minutes}m")

        worker_running = data.get("worker_running", False)
        self.worker_label.setText(
            f"Worker: {'Running' if worker_running else 'Stopped'}"
        )
        self.worker_label.setStyleSheet(
            f"color: {'#4ec9b0' if worker_running else '#f48771'};"
        )

    def _set_service_connected(self, connected: bool):
        """Update service connection status indicator"""
        if connected:
            self.service_status.setStyleSheet("color: #4ec9b0; font-weight: bold;")
            self.service_status.setText("\u25CF Queue Service Connected")
        else:
            self.service_status.setStyleSheet("color: #f48771; font-weight: bold;")
            self.service_status.setText("\u25CF Queue Service Disconnected")

    def start_refresh(self):
        """Start auto-refresh"""
        if not self.refresh_timer.isActive():
            self.refresh_data()  # Immediate refresh
            self.refresh_timer.start(2000)

    def stop_refresh(self):
        """Stop auto-refresh to save resources when hidden"""
        self.refresh_timer.stop()
