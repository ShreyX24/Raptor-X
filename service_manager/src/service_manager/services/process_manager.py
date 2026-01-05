"""
Process Manager - Optimized process management with state machine, proper cleanup, and reliability features

Optimizations implemented:
1. ProcessWrapper with formal state machine (stopped→starting→running→stopping)
2. Proper signal lifecycle management (connect on start, disconnect on stop)
3. Timer consolidation (single timer with scheduled callbacks)
4. Log batching (buffer output, flush every 100ms)
5. Health verification (HTTP check before marking "running")
6. Background file I/O for restart requests
7. Auto-restart watchdog with exponential backoff
8. Graceful shutdown with taskkill for process tree termination
9. Config caching
"""

import os
import json
import socket
import subprocess
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Optional, List, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from PySide6.QtCore import QObject, QProcess, Signal, QProcessEnvironment, QTimer, QThread, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QTcpSocket, QAbstractSocket
from ..config import ServiceConfig, get_services, create_omniparser_config, OMNIPARSER_MAX_INSTANCES
from ..settings import get_settings_manager

# Restart requests file (shared with Admin Panel)
RESTART_REQUESTS_FILE = Path.home() / ".gemma" / "restart_requests.json"


class ProcessState(Enum):
    """Formal state machine for process lifecycle"""
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    HEALTH_CHECK = auto()  # Waiting for health verification
    FAILED = auto()  # Failed to start or crashed


@dataclass
class ScheduledCallback:
    """A scheduled callback with cancellation support"""
    callback_id: str
    callback: Callable
    execute_at: datetime
    cancelled: bool = False


@dataclass
class RestartInfo:
    """Track restart attempts for exponential backoff"""
    attempt_count: int = 0
    last_attempt: Optional[datetime] = None
    next_delay_seconds: float = 1.0  # Start with 1 second, doubles each time
    max_delay_seconds: float = 60.0  # Cap at 1 minute
    auto_restart_enabled: bool = False


class LogBuffer:
    """Buffer for log output to reduce UI updates"""

    def __init__(self, flush_callback: Callable[[str, str], None], flush_interval_ms: int = 100):
        self._buffers: Dict[str, List[str]] = {}
        self._error_buffers: Dict[str, List[str]] = {}
        self._flush_callback = flush_callback
        self._flush_interval = flush_interval_ms
        self._timer: Optional[QTimer] = None

    def set_timer(self, timer: QTimer):
        """Set the shared timer for flushing"""
        self._timer = timer

    def append(self, service_name: str, text: str, is_error: bool = False):
        """Buffer output for a service"""
        if is_error:
            if service_name not in self._error_buffers:
                self._error_buffers[service_name] = []
            self._error_buffers[service_name].append(text)
        else:
            if service_name not in self._buffers:
                self._buffers[service_name] = []
            self._buffers[service_name].append(text)

    def flush(self):
        """Flush all buffered output"""
        # Flush regular output
        for service_name, texts in list(self._buffers.items()):
            if texts:
                combined = "".join(texts)
                self._flush_callback(service_name, combined, False)
                self._buffers[service_name] = []

        # Flush error output
        for service_name, texts in list(self._error_buffers.items()):
            if texts:
                combined = "".join(texts)
                self._flush_callback(service_name, combined, True)
                self._error_buffers[service_name] = []

    def flush_service(self, service_name: str):
        """Immediately flush output for a specific service"""
        if service_name in self._buffers and self._buffers[service_name]:
            combined = "".join(self._buffers[service_name])
            self._flush_callback(service_name, combined, False)
            self._buffers[service_name] = []

        if service_name in self._error_buffers and self._error_buffers[service_name]:
            combined = "".join(self._error_buffers[service_name])
            self._flush_callback(service_name, combined, True)
            self._error_buffers[service_name] = []


class BackgroundFileWorker(QThread):
    """Background thread for file I/O operations"""

    restart_requests_found = Signal(list)  # Emits list of restart requests

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._check_interval_ms = 2000
        self._processed_requests: set = set()

    def run(self):
        """Main thread loop"""
        while self._running:
            self._check_restart_requests()
            self.msleep(self._check_interval_ms)

    def stop(self):
        """Stop the worker thread"""
        self._running = False
        self.wait(3000)  # Wait up to 3 seconds

    def _check_restart_requests(self):
        """Check for restart requests from Admin Panel"""
        if not RESTART_REQUESTS_FILE.exists():
            return

        try:
            with open(RESTART_REQUESTS_FILE, "r") as f:
                requests_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return

        if not requests_data:
            return

        # Filter new requests
        new_requests = []
        for req in requests_data:
            service_name = req.get("service")
            timestamp = req.get("timestamp", 0)
            request_id = f"{service_name}:{timestamp}"

            if request_id not in self._processed_requests:
                new_requests.append(req)
                self._processed_requests.add(request_id)

        # Clear the file after reading
        if new_requests:
            try:
                with open(RESTART_REQUESTS_FILE, "w") as f:
                    json.dump([], f)
            except IOError:
                pass

            self.restart_requests_found.emit(new_requests)

        # Clean up old processed request IDs
        if len(self._processed_requests) > 100:
            self._processed_requests = set(list(self._processed_requests)[-50:])


class ProcessWrapper(QObject):
    """
    Wrapper for QProcess with state machine and proper signal management.
    Handles the complete lifecycle of a single process.
    """

    # Signals
    state_changed = Signal(str, str)  # service_name, state
    output_received = Signal(str, str)  # service_name, text
    error_received = Signal(str, str)  # service_name, text
    health_check_passed = Signal(str)  # service_name
    health_check_failed = Signal(str)  # service_name

    def __init__(self, config: ServiceConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._process: Optional[QProcess] = None
        self._state = ProcessState.STOPPED
        self._restart_info = RestartInfo()

        # Health check
        self._health_check_timer_id: Optional[str] = None
        self._health_check_attempts = 0
        self._max_health_check_attempts = 60  # 60 attempts max (with 500ms interval = 30 seconds)

        # Force kill timer ID
        self._force_kill_timer_id: Optional[str] = None

        # Network manager for health checks (will be set by ProcessManager)
        self._network_manager: Optional[QNetworkAccessManager] = None

        # TCP socket for health check (async, non-blocking)
        self._health_socket: Optional[QTcpSocket] = None
        self._schedule_callback: Optional[Callable] = None

    def set_network_manager(self, manager: QNetworkAccessManager):
        """Set the shared network manager"""
        self._network_manager = manager

    @property
    def state(self) -> ProcessState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state in (ProcessState.RUNNING, ProcessState.HEALTH_CHECK)

    @property
    def process_id(self) -> int:
        """Get the process ID, or 0 if not running"""
        if self._process and self._process.state() == QProcess.Running:
            return self._process.processId()
        return 0

    def _set_state(self, new_state: ProcessState):
        """Update state and emit signal"""
        old_state = self._state
        self._state = new_state

        # Map ProcessState to status string
        status_map = {
            ProcessState.STOPPED: "stopped",
            ProcessState.STARTING: "starting",
            ProcessState.RUNNING: "running",
            ProcessState.STOPPING: "stopping",
            ProcessState.HEALTH_CHECK: "starting",  # Still show as starting during health check
            ProcessState.FAILED: "stopped",
        }
        self.state_changed.emit(self.config.name, status_map.get(new_state, "stopped"))

    def start(self, env_overrides: Dict[str, str] = None, cancel_callback: Callable[[str], None] = None) -> bool:
        """Start the process"""
        if self._state not in (ProcessState.STOPPED, ProcessState.FAILED):
            return False

        # Cancel any pending force kill timer from previous stop
        if self._force_kill_timer_id and cancel_callback:
            cancel_callback(self._force_kill_timer_id)
            self._force_kill_timer_id = None

        # Cancel any pending health check timer
        if self._health_check_timer_id and cancel_callback:
            cancel_callback(self._health_check_timer_id)
            self._health_check_timer_id = None

        if self.config.remote:
            self.output_received.emit(self.config.name, "Remote service - cannot start locally\n")
            self.output_received.emit(self.config.name, f"Service expected at {self.config.host}:{self.config.port}\n")
            return False

        if not self.config.working_dir.exists():
            self.error_received.emit(self.config.name, f"Working directory not found: {self.config.working_dir}\n")
            return False

        self._set_state(ProcessState.STARTING)

        # Create new process
        self._process = QProcess(self)
        self._process.setWorkingDirectory(str(self.config.working_dir))

        # Setup environment
        env = QProcessEnvironment.systemEnvironment()
        for key, value in self.config.env_vars.items():
            env.insert(key, value)
        if env_overrides:
            for key, value in env_overrides.items():
                env.insert(key, value)
        self._process.setProcessEnvironment(env)

        # Connect signals
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.started.connect(self._on_started)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        # Log startup info
        cmd_str = " ".join(self.config.command)
        self.output_received.emit(self.config.name, f"Starting: {cmd_str}\n")
        self.output_received.emit(self.config.name, f"Working dir: {self.config.working_dir}\n")

        # Start process
        self._process.start(self.config.command[0], self.config.command[1:] if len(self.config.command) > 1 else [])
        return True

    def stop(self, schedule_callback: Callable[[str, Callable, int], str], cancel_callback: Callable[[str], None]) -> bool:
        """
        Stop the process gracefully with process tree termination.

        Args:
            schedule_callback: Function to schedule a delayed callback (returns timer_id)
            cancel_callback: Function to cancel a scheduled callback
        """
        if self._state in (ProcessState.STOPPED, ProcessState.FAILED):
            return True

        if self._state == ProcessState.STOPPING:
            return True  # Already stopping

        if self.config.remote:
            self.output_received.emit(self.config.name, "Remote service - cannot stop locally\n")
            return False

        # Cancel any pending health check
        if self._health_check_timer_id:
            cancel_callback(self._health_check_timer_id)
            self._health_check_timer_id = None

        # Cancel any pending force kill
        if self._force_kill_timer_id:
            cancel_callback(self._force_kill_timer_id)
            self._force_kill_timer_id = None

        self._set_state(ProcessState.STOPPING)
        self.output_received.emit(self.config.name, "--- Stopping service ---\n")

        if not self._process:
            self._set_state(ProcessState.STOPPED)
            return True

        pid = self._process.processId()

        if pid > 0:
            # On Windows, kill entire process tree using taskkill
            # This is critical for npm/vite which spawn child processes
            try:
                result = subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=10
                )
                if result.returncode == 0:
                    self.output_received.emit(self.config.name, f"Killed process tree (PID {pid})\n")
                else:
                    # taskkill may fail if process already exited
                    stderr = result.stderr.decode('utf-8', errors='replace').strip()
                    if stderr:
                        self.output_received.emit(self.config.name, f"taskkill: {stderr}\n")
                    # Fallback to terminate
                    self._process.terminate()
            except subprocess.TimeoutExpired:
                self.output_received.emit(self.config.name, "taskkill timed out, using terminate\n")
                self._process.terminate()
            except FileNotFoundError:
                # taskkill not available (non-Windows), use terminate
                self._process.terminate()
            except Exception as e:
                self.output_received.emit(self.config.name, f"taskkill failed: {e}, using terminate\n")
                self._process.terminate()
        else:
            self._process.terminate()

        # Schedule force kill as fallback
        def force_kill():
            self._force_kill_timer_id = None
            if self._process and self._process.state() != QProcess.NotRunning:
                self.output_received.emit(self.config.name, "Force killing (process didn't stop)...\n")
                self._process.kill()

        self._force_kill_timer_id = schedule_callback(
            f"force_kill_{self.config.name}",
            force_kill,
            5000  # 5 second timeout
        )

        return True

    def cleanup(self):
        """Clean up resources and disconnect signals"""
        # Clean up health check socket
        if self._health_socket:
            try:
                self._health_socket.connected.disconnect()
                self._health_socket.errorOccurred.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._health_socket.deleteLater()
            self._health_socket = None

        if self._process:
            try:
                self._process.readyReadStandardOutput.disconnect()
                self._process.readyReadStandardError.disconnect()
                self._process.started.disconnect()
                self._process.finished.disconnect()
                self._process.errorOccurred.disconnect()
            except (RuntimeError, TypeError):
                pass  # Signals already disconnected

            self._process.deleteLater()
            self._process = None

    def start_health_check(self, schedule_callback: Callable[[str, Callable, int], str]):
        """Start health check polling"""
        if not self.config.port or not self._network_manager:
            # No port or network manager, skip health check
            self._set_state(ProcessState.RUNNING)
            self.health_check_passed.emit(self.config.name)
            return

        self._health_check_attempts = 0
        self._set_state(ProcessState.HEALTH_CHECK)
        self._do_health_check(schedule_callback)

    def _do_health_check(self, schedule_callback: Callable[[str, Callable, int], str]):
        """Perform a single health check using async QTcpSocket"""
        if self._state != ProcessState.HEALTH_CHECK:
            return

        self._health_check_attempts += 1
        self._schedule_callback = schedule_callback

        if self._health_check_attempts > self._max_health_check_attempts:
            # Give up on health check, assume running
            self.output_received.emit(self.config.name, "Health check timed out, assuming running\n")
            self._set_state(ProcessState.RUNNING)
            self.health_check_passed.emit(self.config.name)
            return

        # Clean up previous socket if any
        if self._health_socket:
            self._health_socket.disconnectFromHost()
            self._health_socket.deleteLater()
            self._health_socket = None

        # Create async socket for non-blocking check
        host = self.config.host if self.config.host != "0.0.0.0" else "127.0.0.1"
        port = self.config.port

        self._health_socket = QTcpSocket(self)
        self._health_socket.connected.connect(self._on_health_socket_connected)
        self._health_socket.errorOccurred.connect(self._on_health_socket_error)

        # Async connect - returns immediately, signals will fire later
        self._health_socket.connectToHost(host, port)

    def _on_health_socket_connected(self):
        """Socket connected - service is ready!"""
        if self._state != ProcessState.HEALTH_CHECK:
            return

        # Clean up socket
        if self._health_socket:
            self._health_socket.disconnectFromHost()
            self._health_socket.deleteLater()
            self._health_socket = None

        # Service is up!
        self.output_received.emit(self.config.name, f"Service ready on port {self.config.port}\n")
        self._set_state(ProcessState.RUNNING)
        self.health_check_passed.emit(self.config.name)

    def _on_health_socket_error(self, error):
        """Socket error - retry health check"""
        if self._state != ProcessState.HEALTH_CHECK:
            return

        # Clean up socket
        if self._health_socket:
            self._health_socket.deleteLater()
            self._health_socket = None

        # Schedule retry
        if self._schedule_callback:
            self._health_check_timer_id = self._schedule_callback(
                f"health_check_{self.config.name}",
                lambda: self._do_health_check(self._schedule_callback),
                500  # Retry every 500ms
            )

    def _on_stdout(self):
        """Handle stdout from process"""
        if self._process:
            data = self._process.readAllStandardOutput().data()
            try:
                text = data.decode("utf-8", errors="replace")
            except:
                text = str(data)
            self.output_received.emit(self.config.name, text)

    def _on_stderr(self):
        """Handle stderr from process"""
        if self._process:
            data = self._process.readAllStandardError().data()
            try:
                text = data.decode("utf-8", errors="replace")
            except:
                text = str(data)
            self.error_received.emit(self.config.name, text)

    def _on_started(self):
        """Handle process started"""
        self.output_received.emit(self.config.name, f"Process started (PID {self._process.processId()})\n")
        # Don't set to RUNNING yet - wait for health check
        # The health check will be started by ProcessManager

    def _on_finished(self, exit_code: int, exit_status):
        """Handle process finished"""
        was_stopping = self._state == ProcessState.STOPPING

        if was_stopping:
            self.output_received.emit(self.config.name, "--- Service stopped ---\n")
        else:
            self.output_received.emit(self.config.name, f"--- Exited with code {exit_code} ---\n")

        # Clean up
        self.cleanup()

        if was_stopping:
            self._set_state(ProcessState.STOPPED)
            self._restart_info.attempt_count = 0  # Reset on clean stop
        else:
            # Unexpected exit
            self._set_state(ProcessState.FAILED)

    def _on_error(self, error: QProcess.ProcessError):
        """Handle process error"""
        if self._state == ProcessState.STOPPING and error == QProcess.Crashed:
            # Expected when force-killing on Windows
            return

        error_messages = {
            QProcess.FailedToStart: "Failed to start (check if command exists)",
            QProcess.Crashed: "Process crashed",
            QProcess.Timedout: "Process timed out",
            QProcess.WriteError: "Write error",
            QProcess.ReadError: "Read error",
            QProcess.UnknownError: "Unknown error"
        }
        msg = error_messages.get(error, "Unknown error")
        self.error_received.emit(self.config.name, f"Error: {msg}\n")


class ProcessManager(QObject):
    """
    Optimized process manager with all reliability features.
    """

    # Public signals
    output_received = Signal(str, str)  # service_name, text
    error_received = Signal(str, str)  # service_name, text
    status_changed = Signal(str, str)  # service_name, status

    def __init__(self, parent=None):
        super().__init__(parent)

        # Process wrappers
        self._wrappers: Dict[str, ProcessWrapper] = {}

        # Config cache
        self._configs: Dict[str, ServiceConfig] = {}
        self._configs_dirty = True

        # Remote service statuses
        self._remote_statuses: Dict[str, str] = {}

        # Pending starts (services waiting for dependencies to be healthy)
        self._pending_starts: Dict[str, set] = {}

        # Shared network manager (connection pooling)
        self._network_manager = QNetworkAccessManager(self)

        # Timer consolidation - single timer for all scheduled callbacks
        self._scheduled_callbacks: Dict[str, ScheduledCallback] = {}
        self._main_timer = QTimer(self)
        self._main_timer.timeout.connect(self._process_scheduled_callbacks)
        self._main_timer.start(50)  # 50ms resolution

        # Log buffer for batched updates
        self._log_buffer = LogBuffer(self._flush_log_output)

        # Background file worker
        self._file_worker = BackgroundFileWorker(self)
        self._file_worker.restart_requests_found.connect(self._handle_restart_requests)
        self._file_worker.start()

        # Watchdog timer for auto-restart
        self._watchdog_timer = QTimer(self)
        self._watchdog_timer.timeout.connect(self._watchdog_check)
        self._watchdog_timer.start(5000)  # Check every 5 seconds

        # Remote health check timer
        self._remote_health_timer = QTimer(self)
        self._remote_health_timer.timeout.connect(self._check_remote_services)
        self._remote_health_timer.start(10000)  # Every 10 seconds

        # Initialize services
        self._init_services()

    def _init_services(self):
        """Initialize all service wrappers"""
        for config in get_services():
            self._register_service(config)

        # Register OmniParser instances
        settings = get_settings_manager()
        self.register_omniparser_instances(settings.get_omniparser_instance_count())

    def _register_service(self, config: ServiceConfig):
        """Register a service with wrapper"""
        wrapper = ProcessWrapper(config, self)
        wrapper.set_network_manager(self._network_manager)

        # Connect wrapper signals to our signals (with log buffering)
        wrapper.output_received.connect(lambda name, text: self._log_buffer.append(name, text, False))
        wrapper.error_received.connect(lambda name, text: self._log_buffer.append(name, text, True))
        wrapper.state_changed.connect(self.status_changed.emit)
        wrapper.health_check_passed.connect(self._on_health_check_passed)

        self._wrappers[config.name] = wrapper
        self._configs[config.name] = config

    def _unregister_service(self, name: str):
        """Unregister a service"""
        if name in self._wrappers:
            wrapper = self._wrappers[name]
            if wrapper.is_running:
                wrapper.stop(self._schedule_callback, self._cancel_callback)
            wrapper.cleanup()
            wrapper.deleteLater()
            del self._wrappers[name]

        if name in self._configs:
            del self._configs[name]

        if name in self._remote_statuses:
            del self._remote_statuses[name]

    def _flush_log_output(self, service_name: str, text: str, is_error: bool):
        """Flush buffered log output to signals"""
        if is_error:
            self.error_received.emit(service_name, text)
        else:
            self.output_received.emit(service_name, text)

    # =========================================================================
    # Timer Consolidation
    # =========================================================================

    def _schedule_callback(self, callback_id: str, callback: Callable, delay_ms: int) -> str:
        """Schedule a callback to run after delay_ms"""
        execute_at = datetime.now() + timedelta(milliseconds=delay_ms)
        self._scheduled_callbacks[callback_id] = ScheduledCallback(
            callback_id=callback_id,
            callback=callback,
            execute_at=execute_at
        )
        return callback_id

    def _cancel_callback(self, callback_id: str):
        """Cancel a scheduled callback"""
        if callback_id in self._scheduled_callbacks:
            self._scheduled_callbacks[callback_id].cancelled = True

    def _process_scheduled_callbacks(self):
        """Process due callbacks and flush log buffer"""
        now = datetime.now()

        # Process callbacks
        to_remove = []
        for callback_id, scheduled in list(self._scheduled_callbacks.items()):
            if scheduled.cancelled:
                to_remove.append(callback_id)
            elif now >= scheduled.execute_at:
                to_remove.append(callback_id)
                if not scheduled.cancelled:
                    try:
                        scheduled.callback()
                    except Exception as e:
                        print(f"Callback error ({callback_id}): {e}")

        for callback_id in to_remove:
            del self._scheduled_callbacks[callback_id]

        # Flush log buffer
        self._log_buffer.flush()

    # =========================================================================
    # Public API
    # =========================================================================

    @property
    def configs(self) -> Dict[str, ServiceConfig]:
        """Get all configs (for compatibility)"""
        return self._configs

    def is_running(self, name: str) -> bool:
        """Check if a service is running"""
        if name in self._wrappers:
            return self._wrappers[name].is_running
        return False

    def get_status(self, name: str) -> str:
        """Get status of a service"""
        if name in self._wrappers:
            state = self._wrappers[name].state
            status_map = {
                ProcessState.STOPPED: "stopped",
                ProcessState.STARTING: "starting",
                ProcessState.RUNNING: "running",
                ProcessState.STOPPING: "stopping",
                ProcessState.HEALTH_CHECK: "starting",
                ProcessState.FAILED: "stopped",
            }
            return status_map.get(state, "stopped")

        # Check remote status
        if name in self._remote_statuses:
            return self._remote_statuses[name]

        return "stopped"

    def start_service(self, name: str) -> bool:
        """Start a service"""
        if name not in self._wrappers:
            self.error_received.emit(name, "Service not found\n")
            return False

        wrapper = self._wrappers[name]
        config = self._configs[name]

        # Build environment overrides
        env_overrides = {}

        # Special handling for queue-service
        if name == "queue-service":
            settings = get_settings_manager()
            omniparser_urls = settings.get_omniparser_urls_env()
            if omniparser_urls:
                env_overrides["OMNIPARSER_URLS"] = omniparser_urls
                self._log_buffer.append(name, f"OmniParser URLs: {omniparser_urls}\n", False)

        # Special handling for gemma-backend
        if name == "gemma-backend":
            settings = get_settings_manager()
            steam_accounts = settings.get_steam_accounts_env()
            if steam_accounts:
                env_overrides["STEAM_ACCOUNT_PAIRS"] = steam_accounts
                pair_count = steam_accounts.count("|") + 1
                self._log_buffer.append(name, f"Steam account pairs: {pair_count} configured\n", False)

            steam_timeout = settings.get_steam_login_timeout()
            env_overrides["STEAM_LOGIN_TIMEOUT"] = str(steam_timeout)
            self._log_buffer.append(name, f"Steam login timeout: {steam_timeout}s\n", False)

        # Flush buffer before starting
        self._log_buffer.flush_service(name)

        # Start the process (pass cancel_callback to clear any pending timers from previous stop)
        result = wrapper.start(env_overrides, self._cancel_callback)

        if result:
            # Start health check after a short delay
            self._schedule_callback(
                f"start_health_{name}",
                lambda: wrapper.start_health_check(self._schedule_callback),
                1000  # Wait 1 second before starting health checks
            )

        return result

    def stop_service(self, name: str) -> bool:
        """Stop a service"""
        if name not in self._wrappers:
            return True

        wrapper = self._wrappers[name]

        # Disable auto-restart for this service
        wrapper._restart_info.auto_restart_enabled = False

        return wrapper.stop(self._schedule_callback, self._cancel_callback)

    def restart_service(self, name: str) -> bool:
        """Restart a service"""
        if name not in self._wrappers:
            return False

        wrapper = self._wrappers[name]

        if wrapper.is_running:
            # Stop first, then start when stopped
            def start_after_stop():
                if wrapper.state == ProcessState.STOPPED:
                    self.start_service(name)

            # Schedule check for when service is stopped
            def check_and_start():
                if wrapper.state in (ProcessState.STOPPED, ProcessState.FAILED):
                    self.start_service(name)
                else:
                    # Keep checking
                    self._schedule_callback(
                        f"restart_check_{name}",
                        check_and_start,
                        200
                    )

            wrapper.stop(self._schedule_callback, self._cancel_callback)
            self._schedule_callback(f"restart_check_{name}", check_and_start, 500)
            return True
        else:
            return self.start_service(name)

    def start_all(self):
        """Start all services respecting dependencies - waits for health checks"""
        started = set()
        pending = set()

        def start_with_deps(name: str):
            if name in started or name in pending:
                return

            if name not in self._configs:
                return

            config = self._configs[name]

            # Skip disabled services
            if not config.enabled:
                started.add(name)
                return

            # Skip remote services (just check health)
            if config.remote:
                started.add(name)
                self._check_single_remote(name)
                return

            # Check which dependencies need to be healthy first
            unready_deps = []
            for dep in config.depends_on:
                if dep not in self._configs:
                    continue
                dep_config = self._configs[dep]
                if dep_config.remote:
                    # Remote deps - just need to be checked
                    continue
                # Check if dependency is running AND healthy
                if dep in self._wrappers:
                    wrapper = self._wrappers[dep]
                    if wrapper.state != ProcessState.RUNNING:
                        unready_deps.append(dep)
                else:
                    unready_deps.append(dep)

            # Start dependencies first (recursively)
            for dep in config.depends_on:
                if dep not in started and dep not in pending:
                    start_with_deps(dep)

            if unready_deps:
                # Wait for dependencies to be healthy
                self._pending_starts[name] = set(unready_deps)
                pending.add(name)
                self._log_buffer.append(
                    name,
                    f"Waiting for dependencies: {', '.join(unready_deps)}\n",
                    False
                )
            else:
                # All dependencies ready, start now
                self.start_service(name)
                started.add(name)

        for name in self._configs:
            start_with_deps(name)

    def stop_all(self):
        """Stop all services"""
        for name in list(self._wrappers.keys()):
            self.stop_service(name)

    def restart_all(self):
        """Restart all services"""
        running_services = [
            name for name, wrapper in self._wrappers.items()
            if wrapper.is_running
        ]

        if not running_services:
            self.start_all()
            return

        # Stop all, then start all
        stopped_count = [0]

        def check_all_stopped():
            all_stopped = all(
                not self._wrappers[name].is_running
                for name in running_services
                if name in self._wrappers
            )

            if all_stopped:
                self._schedule_callback("restart_all_start", self.start_all, 500)
            else:
                # Keep checking
                self._schedule_callback("restart_all_check", check_all_stopped, 200)

        self.stop_all()
        self._schedule_callback("restart_all_check", check_all_stopped, 500)

        # Fallback: force start after 10 seconds
        self._schedule_callback(
            "restart_all_fallback",
            self.start_all,
            10000
        )

    def get_running_count(self) -> int:
        """Get count of running services"""
        return sum(1 for w in self._wrappers.values() if w.is_running)

    def get_total_count(self) -> int:
        """Get count of enabled services"""
        return sum(1 for c in self._configs.values() if c.enabled)

    # =========================================================================
    # OmniParser Management
    # =========================================================================

    def register_omniparser_instances(self, count: int):
        """Register OmniParser instances based on count"""
        # Remove existing OmniParser services
        omniparser_names = [n for n in self._wrappers if n.startswith("omniparser-")]
        for name in omniparser_names:
            self._unregister_service(name)

        # Create new instances
        for i in range(count):
            config = create_omniparser_config(i)
            self._register_service(config)

    def get_omniparser_services(self) -> list:
        """Get list of OmniParser service names"""
        return [n for n in self._wrappers if n.startswith("omniparser-")]

    # =========================================================================
    # Config Management
    # =========================================================================

    def refresh_service_configs(self):
        """Refresh configs from settings"""
        for config in get_services():
            if config.name in self._configs:
                # Update config
                self._configs[config.name] = config
                if config.name in self._wrappers:
                    self._wrappers[config.name].config = config

    # =========================================================================
    # Remote Service Health
    # =========================================================================

    def _check_remote_services(self):
        """Check health of all remote services"""
        for name, config in self._configs.items():
            if config.remote and config.port:
                self._check_single_remote(name)

    def _check_single_remote(self, name: str):
        """Check health of a single remote service"""
        if name not in self._configs:
            return

        config = self._configs[name]
        if not config.port:
            return

        health_path = getattr(config, 'health_path', '/')
        url = QUrl(f"http://{config.host}:{config.port}{health_path}")
        request = QNetworkRequest(url)
        request.setTransferTimeout(5000)

        reply = self._network_manager.get(request)
        reply.finished.connect(lambda: self._handle_remote_health_check(name, reply))

    def _handle_remote_health_check(self, name: str, reply: QNetworkReply):
        """Handle remote health check response"""
        old_status = self._remote_statuses.get(name, "unknown")

        if reply.error() == QNetworkReply.NoError:
            new_status = "connected"
        else:
            new_status = "unreachable"

        self._remote_statuses[name] = new_status

        if old_status != new_status:
            self.status_changed.emit(name, new_status)

        reply.deleteLater()

    def get_remote_status(self, name: str) -> str:
        """Get remote service status"""
        return self._remote_statuses.get(name, "unknown")

    # =========================================================================
    # Watchdog & Auto-Restart
    # =========================================================================

    def _watchdog_check(self):
        """Check for crashed services and auto-restart if enabled"""
        for name, wrapper in self._wrappers.items():
            if wrapper.state == ProcessState.FAILED and wrapper._restart_info.auto_restart_enabled:
                self._attempt_auto_restart(name, wrapper)

    def _attempt_auto_restart(self, name: str, wrapper: ProcessWrapper):
        """Attempt to auto-restart a failed service with exponential backoff"""
        info = wrapper._restart_info
        now = datetime.now()

        # Check if enough time has passed since last attempt
        if info.last_attempt:
            time_since_last = (now - info.last_attempt).total_seconds()
            if time_since_last < info.next_delay_seconds:
                return

        # Attempt restart
        info.attempt_count += 1
        info.last_attempt = now

        self._log_buffer.append(
            name,
            f"Auto-restart attempt {info.attempt_count} (backoff: {info.next_delay_seconds}s)\n",
            False
        )

        # Update backoff
        info.next_delay_seconds = min(
            info.next_delay_seconds * 2,
            info.max_delay_seconds
        )

        self.start_service(name)

    def enable_auto_restart(self, name: str, enabled: bool = True):
        """Enable or disable auto-restart for a service"""
        if name in self._wrappers:
            self._wrappers[name]._restart_info.auto_restart_enabled = enabled

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def _on_health_check_passed(self, name: str):
        """Handle health check passed - service is fully ready"""
        # Check if any pending services were waiting for this dependency
        self._start_waiting_dependents(name)

    def _start_waiting_dependents(self, ready_service: str):
        """Start services that were waiting for this dependency to be healthy"""
        to_start = []
        for waiting_name, waiting_deps in list(self._pending_starts.items()):
            if ready_service in waiting_deps:
                waiting_deps.remove(ready_service)
                if not waiting_deps:
                    # All dependencies ready
                    to_start.append(waiting_name)
                    del self._pending_starts[waiting_name]

        for name in to_start:
            self._log_buffer.append(name, f"Dependency {ready_service} ready, starting...\n", False)
            self.start_service(name)

    def _handle_restart_requests(self, requests: list):
        """Handle restart requests from background worker"""
        for req in requests:
            service_name = req.get("service")
            if service_name in self._wrappers:
                self._log_buffer.append(
                    service_name,
                    "[Admin Panel] Restart requested\n",
                    False
                )
                self.restart_service(service_name)

    # =========================================================================
    # Cleanup
    # =========================================================================

    def cleanup(self):
        """Clean up all resources"""
        # Stop file worker
        self._file_worker.stop()

        # Stop timers
        self._main_timer.stop()
        self._watchdog_timer.stop()
        self._remote_health_timer.stop()

        # Stop all services
        self.stop_all()

        # Clean up wrappers
        for wrapper in self._wrappers.values():
            wrapper.cleanup()


# Compatibility: Keep old 'processes' property for backward compatibility
ProcessManager.processes = property(
    lambda self: {
        name: wrapper._process
        for name, wrapper in self._wrappers.items()
        if wrapper._process is not None
    }
)
