"""
Process Manager - Manages QProcess instances for all services
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional
from PySide6.QtCore import QObject, QProcess, Signal, QProcessEnvironment, QTimer
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtCore import QUrl
from ..config import ServiceConfig, get_services, create_omniparser_config, OMNIPARSER_MAX_INSTANCES
from ..settings import get_settings_manager

# Restart requests file (shared with Admin Panel)
RESTART_REQUESTS_FILE = Path.home() / ".gemma" / "restart_requests.json"


class ProcessManager(QObject):
    """Manages QProcess instances for all services"""

    output_received = Signal(str, str)
    error_received = Signal(str, str)
    status_changed = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.processes: Dict[str, QProcess] = {}
        self.configs: Dict[str, ServiceConfig] = {}
        self.remote_statuses: Dict[str, str] = {}  # Track remote service status
        self._stopping_services: set = set()  # Track services being intentionally stopped
        self.network_manager = QNetworkAccessManager(self)

        for config in get_services():
            self.register_service(config)

        # Register OmniParser instances based on settings
        settings = get_settings_manager()
        self.register_omniparser_instances(settings.get_omniparser_instance_count())

        # Timer for health checks on remote services
        self.health_check_timer = QTimer(self)
        self.health_check_timer.timeout.connect(self._check_remote_services)
        self.health_check_timer.start(10000)  # Check every 10 seconds

        # Timer for restart requests from Admin Panel
        self.restart_request_timer = QTimer(self)
        self.restart_request_timer.timeout.connect(self._check_restart_requests)
        self.restart_request_timer.start(2000)  # Check every 2 seconds
        self._processed_requests: set = set()  # Track processed request timestamps
    
    def register_service(self, config: ServiceConfig):
        self.configs[config.name] = config

    def unregister_service(self, name: str):
        """Remove a service from the manager"""
        # Stop the service first if running
        if name in self.processes and self.processes[name].state() == QProcess.Running:
            self.stop_service(name)
        # Remove from configs
        if name in self.configs:
            del self.configs[name]
        # Clean up remote status if any
        if name in self.remote_statuses:
            del self.remote_statuses[name]

    def register_omniparser_instances(self, count: int):
        """Register OmniParser instances based on settings.

        Args:
            count: Number of instances to register (0 = none, 1-5 = create that many)
        """
        # First, remove all existing omniparser-* services
        omniparser_services = [name for name in self.configs if name.startswith("omniparser-")]
        for name in omniparser_services:
            self.unregister_service(name)

        # Create and register new configs based on count
        for i in range(count):
            config = create_omniparser_config(i)
            self.register_service(config)

    def get_omniparser_services(self) -> list:
        """Get list of registered OmniParser service names"""
        return [name for name in self.configs if name.startswith("omniparser-")]

    def refresh_service_configs(self):
        """Refresh service configs from current settings (e.g., after project dir change)"""
        for config in get_services():
            if config.name in self.configs:
                # Update the working_dir and other settings that may have changed
                self.configs[config.name].working_dir = config.working_dir
                self.configs[config.name].host = config.host
                self.configs[config.name].port = config.port
                self.configs[config.name].remote = config.remote
                self.configs[config.name].enabled = config.enabled
                self.configs[config.name].env_vars = config.env_vars

    def is_running(self, name: str) -> bool:
        return name in self.processes and self.processes[name].state() == QProcess.Running
    
    def get_status(self, name: str) -> str:
        if name not in self.processes:
            return "stopped"
        state = self.processes[name].state()
        if state == QProcess.Running:
            return "running"
        elif state == QProcess.Starting:
            return "starting"
        return "stopped"
    
    def start_service(self, name: str) -> bool:
        if name in self.processes and self.processes[name].state() == QProcess.Running:
            return True
        config = self.configs.get(name)
        if not config:
            self.error_received.emit(name, "Service not found")
            return False

        # Remote services cannot be started locally
        if config.remote:
            self.output_received.emit(name, "Remote service - cannot start locally\n")
            self.output_received.emit(name, f"Service expected at {config.host}:{config.port}\n")
            self._check_single_remote(name)
            return False

        if not config.working_dir.exists():
            self.error_received.emit(name, "Working directory not found")
            return False
        
        process = QProcess(self)
        process.setWorkingDirectory(str(config.working_dir))
        env = QProcessEnvironment.systemEnvironment()
        for key, value in config.env_vars.items():
            env.insert(key, value)

        # Special handling for queue-service: inject OmniParser server URLs
        if name == "queue-service":
            settings = get_settings_manager()
            omniparser_urls = settings.get_omniparser_urls_env()
            if omniparser_urls:
                env.insert("OMNIPARSER_URLS", omniparser_urls)
                self.output_received.emit(name, f"OmniParser URLs: {omniparser_urls}\n")

        # Special handling for gemma-backend: inject Steam account pairs and timeout
        if name == "gemma-backend":
            settings = get_settings_manager()
            steam_accounts = settings.get_steam_accounts_env()
            if steam_accounts:
                env.insert("STEAM_ACCOUNT_PAIRS", steam_accounts)
                # Don't log the actual credentials, just the count
                pair_count = steam_accounts.count("|") + 1
                self.output_received.emit(name, f"Steam account pairs: {pair_count} configured\n")

            # Inject Steam login timeout
            steam_timeout = settings.get_steam_login_timeout()
            env.insert("STEAM_LOGIN_TIMEOUT", str(steam_timeout))
            self.output_received.emit(name, f"Steam login timeout: {steam_timeout}s\n")

        process.setProcessEnvironment(env)
        
        process.readyReadStandardOutput.connect(lambda p=process, n=name: self._handle_stdout(n, p))
        process.readyReadStandardError.connect(lambda p=process, n=name: self._handle_stderr(n, p))
        process.started.connect(lambda n=name: self._handle_started(n))
        process.finished.connect(lambda exit_code, exit_status, n=name: self._handle_finished(n, exit_code))
        process.errorOccurred.connect(lambda error, n=name: self._handle_error(n, error))
        
        self.processes[name] = process
        self.status_changed.emit(name, "starting")
        
        cmd_str = " ".join(config.command)
        self.output_received.emit(name, "Starting: " + cmd_str + "\n")
        self.output_received.emit(name, "Working dir: " + str(config.working_dir) + "\n")
        
        process.start(config.command[0], config.command[1:] if len(config.command) > 1 else [])
        return True
    
    def stop_service(self, name: str, force_kill_timeout: int = 5000) -> bool:
        config = self.configs.get(name)

        # Remote services cannot be stopped locally
        if config and config.remote:
            self.output_received.emit(name, "Remote service - cannot stop locally\n")
            return False

        process = self.processes.get(name)
        if not process:
            return True
        if process.state() == QProcess.NotRunning:
            if name in self.processes:
                del self.processes[name]
            return True

        self._stopping_services.add(name)  # Mark as intentionally stopping
        self.status_changed.emit(name, "stopping")
        self.output_received.emit(name, "--- Stopping service ---\n")

        # Use terminate first (graceful shutdown)
        process.terminate()

        # Set up a timer to force kill if process doesn't stop gracefully
        def force_kill():
            if name in self.processes and self.processes[name].state() != QProcess.NotRunning:
                self.output_received.emit(name, "Force killing...\n")
                self.processes[name].kill()

        QTimer.singleShot(force_kill_timeout, force_kill)
        return True
    
    def restart_service(self, name: str) -> bool:
        """Restart a service - stops then starts when fully stopped"""
        if name in self.processes and self.processes[name].state() != QProcess.NotRunning:
            process = self.processes[name]

            # Connect to finished signal to start after stop completes
            def on_finished():
                # Disconnect to avoid multiple triggers
                try:
                    process.finished.disconnect(on_finished)
                except RuntimeError:
                    pass  # Already disconnected
                # Small delay to ensure cleanup, then start
                QTimer.singleShot(500, lambda: self.start_service(name))

            process.finished.connect(on_finished)
            self.stop_service(name)
            return True
        else:
            return self.start_service(name)
    
    def start_all(self):
        """Start all services respecting dependencies and startup delays"""
        started = set()
        delay_ms = 0

        def schedule_start(name: str, delay: int):
            """Schedule a service start after delay milliseconds"""
            if delay > 0:
                QTimer.singleShot(delay, lambda: self.start_service(name))
            else:
                self.start_service(name)

        def start_with_deps(n):
            nonlocal delay_ms
            if n in started:
                return
            cfg = self.configs.get(n)
            if not cfg:
                return
            # Skip disabled services
            if not cfg.enabled:
                started.add(n)
                return
            # Skip remote services
            if cfg.remote:
                started.add(n)
                self._check_single_remote(n)
                return
            for dep in cfg.depends_on:
                if dep not in started:
                    start_with_deps(dep)

            # Apply startup_delay for services that need it (e.g., frontends)
            if cfg.startup_delay > 0:
                delay_ms += int(cfg.startup_delay * 1000)

            schedule_start(n, delay_ms)
            started.add(n)

            # Add base delay between services to let them initialize
            delay_ms += 500  # 500ms between each service

        for n in self.configs:
            start_with_deps(n)

    def stop_all(self):
        """Stop all services"""
        for name in reversed(list(self.processes.keys())):
            self.stop_service(name)

    def restart_all(self):
        """Restart all services - waits for all to stop before starting"""
        running_count = self.get_running_count()
        if running_count == 0:
            # Nothing running, just start all
            self.start_all()
            return

        # Track how many services we're waiting to stop
        self._restart_pending = True
        self._services_to_stop = set(
            name for name, proc in self.processes.items()
            if proc.state() == QProcess.Running
        )

        # Connect to finished signals to track when all are stopped
        def on_service_stopped(name: str):
            if not self._restart_pending:
                return
            self._services_to_stop.discard(name)
            if len(self._services_to_stop) == 0:
                # All services stopped, now start them
                self._restart_pending = False
                QTimer.singleShot(500, self.start_all)

        # Temporarily connect to status changes
        def check_stopped(name: str, status: str):
            if status == "stopped":
                on_service_stopped(name)

        self._restart_status_handler = check_stopped
        self.status_changed.connect(check_stopped)

        # Stop all services
        self.stop_all()

        # Fallback: if services don't stop within 10 seconds, force start anyway
        def fallback_start():
            if self._restart_pending:
                self._restart_pending = False
                try:
                    self.status_changed.disconnect(self._restart_status_handler)
                except:
                    pass
                self.start_all()

        QTimer.singleShot(10000, fallback_start)
    
    def get_running_count(self) -> int:
        return sum(1 for p in self.processes.values() if p.state() == QProcess.Running)
    
    def get_total_count(self) -> int:
        """Count only enabled services"""
        return sum(1 for c in self.configs.values() if c.enabled)
    
    def _handle_stdout(self, name: str, process: QProcess):
        data = process.readAllStandardOutput().data()
        try:
            text = data.decode("utf-8", errors="replace")
        except:
            text = str(data)
        self.output_received.emit(name, text)
    
    def _handle_stderr(self, name: str, process: QProcess):
        data = process.readAllStandardError().data()
        try:
            text = data.decode("utf-8", errors="replace")
        except:
            text = str(data)
        self.error_received.emit(name, text)
    
    def _handle_started(self, name: str):
        self.status_changed.emit(name, "running")
        config = self.configs.get(name)
        if config and config.port:
            self.output_received.emit(name, "Service running on port " + str(config.port) + "")
    
    def _handle_finished(self, name: str, exit_code: int):
        # Check if this was an intentional stop
        was_stopping = name in self._stopping_services
        if was_stopping:
            self._stopping_services.discard(name)
            self.output_received.emit(name, "--- Service stopped ---\n")
        else:
            self.output_received.emit(name, "--- Exited with code " + str(exit_code) + " ---\n")

        if name in self.processes:
            del self.processes[name]
        self.status_changed.emit(name, "stopped")

    def _handle_error(self, name: str, error: QProcess.ProcessError):
        # Don't show error if we're intentionally stopping the service
        if name in self._stopping_services and error == QProcess.Crashed:
            # This is expected when force-killing on Windows, don't show error
            return

        error_messages = {
            QProcess.FailedToStart: "Failed to start",
            QProcess.Crashed: "Process crashed",
            QProcess.Timedout: "Process timed out",
            QProcess.WriteError: "Write error",
            QProcess.ReadError: "Read error",
            QProcess.UnknownError: "Unknown error"
        }
        msg = error_messages.get(error, "Unknown error")
        self.error_received.emit(name, "Error: " + msg + "\n")

    def _check_remote_services(self):
        """Check health of all remote services"""
        for name, config in self.configs.items():
            if config.remote and config.port:
                self._check_single_remote(name)

    def _check_single_remote(self, name: str):
        """Check health of a single remote service"""
        config = self.configs.get(name)
        if not config or not config.port:
            return

        url = QUrl(f"http://{config.host}:{config.port}/")
        request = QNetworkRequest(url)
        request.setTransferTimeout(5000)  # 5 second timeout

        reply = self.network_manager.get(request)
        reply.finished.connect(lambda: self._handle_health_check(name, reply))

    def _handle_health_check(self, name: str, reply: QNetworkReply):
        """Handle health check response"""
        old_status = self.remote_statuses.get(name, "unknown")

        if reply.error() == QNetworkReply.NoError:
            new_status = "connected"
        else:
            new_status = "unreachable"

        self.remote_statuses[name] = new_status

        # Only emit if status changed
        if old_status != new_status:
            self.status_changed.emit(name, new_status)

        reply.deleteLater()

    def get_remote_status(self, name: str) -> str:
        """Get the status of a remote service"""
        return self.remote_statuses.get(name, "unknown")

    def _check_restart_requests(self):
        """Check for restart requests from Admin Panel and process them"""
        if not RESTART_REQUESTS_FILE.exists():
            return

        try:
            with open(RESTART_REQUESTS_FILE, "r") as f:
                requests_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return

        if not requests_data:
            return

        # Process each request
        processed_any = False
        remaining_requests = []

        for req in requests_data:
            service_name = req.get("service")
            timestamp = req.get("timestamp", 0)
            request_id = f"{service_name}:{timestamp}"

            # Skip already processed requests
            if request_id in self._processed_requests:
                continue

            # Skip if service doesn't exist
            if service_name not in self.configs:
                self._processed_requests.add(request_id)
                continue

            # Process the restart request
            self.output_received.emit(
                service_name,
                f"[Admin Panel] Restart requested\n"
            )
            self.restart_service(service_name)
            self._processed_requests.add(request_id)
            processed_any = True

        # Clear the file after processing
        if processed_any:
            try:
                with open(RESTART_REQUESTS_FILE, "w") as f:
                    json.dump([], f)
            except IOError:
                pass

        # Clean up old processed request IDs (keep last 100)
        if len(self._processed_requests) > 100:
            self._processed_requests = set(list(self._processed_requests)[-50:])
