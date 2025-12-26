"""
Process Manager - Manages QProcess instances for all services
"""

import os
from typing import Dict, Optional
from PySide6.QtCore import QObject, QProcess, Signal, QProcessEnvironment, QTimer
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtCore import QUrl
from ..config import ServiceConfig, SERVICES, create_omniparser_config, OMNIPARSER_MAX_INSTANCES
from ..settings import get_settings_manager


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
        self.network_manager = QNetworkAccessManager(self)

        for config in SERVICES:
            self.register_service(config)

        # Register OmniParser instances based on settings
        settings = get_settings_manager()
        self.register_omniparser_instances(settings.get_omniparser_instance_count())

        # Timer for health checks on remote services
        self.health_check_timer = QTimer(self)
        self.health_check_timer.timeout.connect(self._check_remote_services)
        self.health_check_timer.start(10000)  # Check every 10 seconds
    
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
        """Restart a service - stops then starts after a delay"""
        if name in self.processes and self.processes[name].state() != QProcess.NotRunning:
            self.stop_service(name)
            # Wait a bit for stop to complete, then start
            QTimer.singleShot(1500, lambda: self.start_service(name))
            return True
        else:
            return self.start_service(name)
    
    def start_all(self):
        started = set()
        def start_with_deps(n):
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
            self.start_service(n)
            started.add(n)
        for n in self.configs:
            start_with_deps(n)
    
    def stop_all(self):
        for name in reversed(list(self.processes.keys())):
            self.stop_service(name)
    
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
        self.output_received.emit(name, "--- Exited with code " + str(exit_code) + " ---")
        if name in self.processes:
            del self.processes[name]
        self.status_changed.emit(name, "stopped")
    
    def _handle_error(self, name: str, error: QProcess.ProcessError):
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
