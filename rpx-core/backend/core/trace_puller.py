"""
Trace Puller - Pulls trace files from SUT to Master via SSH/SCP

After automation completes, this module pulls PTAT and socwatch trace files
from the SUT to the Master's run storage directory.

Requires SSH key-based authentication to be set up between Master and SUTs.
"""

import subprocess
import logging
import os
import time
import socket
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class TracePuller:
    """Pulls trace files from SUT to Master via SSH/SCP"""

    # Default trace output directories on SUT
    DEFAULT_TRACE_DIRS = {
        "ptat": r"C:\OWR\PTAT",  # PTAT outputs files in its directory
        "socwatch": r"C:\Traces",  # Default socwatch output
    }

    # SSH options for reliable connections
    SSH_OPTIONS = [
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3",
        "-o", "TCPKeepAlive=yes",
        "-o", "ConnectionAttempts=2",
    ]

    def __init__(self, sut_ip: str, ssh_user: Optional[str] = None, ssh_timeout: int = 60,
                 max_retries: int = 3, retry_delay: int = 5):
        """
        Initialize trace puller.

        Args:
            sut_ip: IP address of the SUT
            ssh_user: SSH username (defaults to current user)
            ssh_timeout: SSH connection timeout in seconds (default: 60)
            max_retries: Maximum connection retry attempts (default: 3)
            retry_delay: Initial delay between retries in seconds (default: 5)
        """
        self.sut_ip = sut_ip
        self.ssh_user = ssh_user or os.getenv("USERNAME", os.getenv("USER", "user"))
        self.ssh_timeout = ssh_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def _get_ssh_options(self) -> List[str]:
        """Get SSH options with current timeout."""
        return self.SSH_OPTIONS + ["-o", f"ConnectTimeout={self.ssh_timeout}"]

    def diagnose_connection(self) -> dict:
        """
        Diagnose SSH connectivity issues to the SUT.

        Returns:
            Dict with diagnostic results
        """
        results = {
            "sut_ip": self.sut_ip,
            "ssh_user": self.ssh_user,
            "port_22_reachable": False,
            "tcp_connect_time_ms": None,
            "ssh_handshake": False,
            "ssh_error": None,
            "recommendations": []
        }

        # Test 1: TCP port 22 reachability
        logger.info(f"Testing TCP connectivity to {self.sut_ip}:22...")
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.sut_ip, 22))
            results["tcp_connect_time_ms"] = round((time.time() - start) * 1000)
            results["port_22_reachable"] = True
            sock.close()
            logger.info(f"TCP port 22 reachable ({results['tcp_connect_time_ms']}ms)")
        except socket.timeout:
            results["ssh_error"] = "TCP connection timed out - port 22 not responding"
            results["recommendations"].append("Check if OpenSSH Server is running on SUT: Get-Service sshd")
            results["recommendations"].append("Check Windows Firewall allows inbound TCP port 22")
            logger.error(f"TCP port 22 timeout: {self.sut_ip}")
            return results
        except socket.error as e:
            results["ssh_error"] = f"TCP connection failed: {e}"
            results["recommendations"].append("Verify SUT IP address is correct")
            results["recommendations"].append("Check network connectivity: ping " + self.sut_ip)
            logger.error(f"TCP connection error: {e}")
            return results

        # Test 2: SSH handshake with verbose output
        logger.info(f"Testing SSH handshake to {self.ssh_user}@{self.sut_ip}...")
        try:
            result = subprocess.run([
                "ssh", "-v",
                "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=no",
                "-o", f"ConnectTimeout={self.ssh_timeout}",
                f"{self.ssh_user}@{self.sut_ip}",
                "echo SSH_OK"
            ], capture_output=True, text=True, timeout=self.ssh_timeout + 10)

            if result.returncode == 0 and "SSH_OK" in result.stdout:
                results["ssh_handshake"] = True
                logger.info("SSH connection successful")
            else:
                # Parse verbose output for diagnosis
                stderr = result.stderr.lower()
                if "permission denied" in stderr:
                    results["ssh_error"] = "Permission denied - SSH key authentication failed"
                    results["recommendations"].append("Set up SSH key auth: ssh-copy-id " + f"{self.ssh_user}@{self.sut_ip}")
                    results["recommendations"].append("Verify SSH public key in SUT's ~/.ssh/authorized_keys")
                elif "connection refused" in stderr:
                    results["ssh_error"] = "Connection refused - OpenSSH server not accepting connections"
                    results["recommendations"].append("Restart OpenSSH Server on SUT: Restart-Service sshd")
                elif "connection timed out" in stderr or "operation timed out" in stderr:
                    results["ssh_error"] = "SSH handshake timed out"
                    results["recommendations"].append("Increase ssh_timeout or check SUT SSH server logs")
                else:
                    results["ssh_error"] = result.stderr.strip()[:200] or "Unknown SSH error"
                logger.error(f"SSH handshake failed: {results['ssh_error']}")
        except subprocess.TimeoutExpired:
            results["ssh_error"] = f"SSH command timed out after {self.ssh_timeout}s"
            results["recommendations"].append("SUT SSH server may be overloaded or hanging")
        except Exception as e:
            results["ssh_error"] = str(e)

        return results

    def test_connection(self, with_retry: bool = True) -> Tuple[bool, str]:
        """
        Test SSH connection to SUT with retry logic.

        Args:
            with_retry: Whether to retry on failure (default: True)

        Returns:
            Tuple of (success, message)
        """
        attempts = self.max_retries if with_retry else 1
        last_error = "Unknown error"

        for attempt in range(1, attempts + 1):
            try:
                logger.debug(f"SSH connection attempt {attempt}/{attempts} to {self.sut_ip}")

                result = subprocess.run(
                    ["ssh"] + self._get_ssh_options() + [
                        f"{self.ssh_user}@{self.sut_ip}",
                        "echo SSH_OK"
                    ],
                    capture_output=True, text=True, timeout=self.ssh_timeout + 10
                )

                if result.returncode == 0 and "SSH_OK" in result.stdout:
                    if attempt > 1:
                        logger.info(f"SSH connection succeeded on attempt {attempt}")
                    return True, "Connection successful"
                else:
                    last_error = result.stderr.strip() or "Connection failed"
                    logger.warning(f"SSH attempt {attempt} failed: {last_error}")

            except subprocess.TimeoutExpired:
                last_error = f"Connection timed out after {self.ssh_timeout}s"
                logger.warning(f"SSH attempt {attempt} timed out")
            except FileNotFoundError:
                return False, "SSH client not found - ensure OpenSSH is installed"
            except Exception as e:
                last_error = str(e)
                logger.warning(f"SSH attempt {attempt} error: {e}")

            # Wait before retry with exponential backoff
            if attempt < attempts:
                delay = self.retry_delay * (2 ** (attempt - 1))
                logger.info(f"Retrying in {delay}s...")
                time.sleep(delay)

        return False, last_error

    def list_remote_files(self, remote_dir: str, pattern: str = "*") -> List[str]:
        """
        List files in remote directory matching pattern.

        Args:
            remote_dir: Remote directory path
            pattern: File pattern to match (glob-style)

        Returns:
            List of filenames
        """
        # Use PowerShell on Windows SUT to list files
        cmd = f'powershell -Command "Get-ChildItem -Path \'{remote_dir}\' -Filter \'{pattern}\' -File -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name"'

        for attempt in range(1, self.max_retries + 1):
            try:
                result = subprocess.run(
                    ["ssh"] + self._get_ssh_options() + [
                        f"{self.ssh_user}@{self.sut_ip}",
                        cmd
                    ],
                    capture_output=True, text=True, timeout=self.ssh_timeout + 30
                )

                if result.returncode == 0:
                    files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
                    return files
                else:
                    logger.warning(f"Failed to list remote files (attempt {attempt}): {result.stderr}")

            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout listing remote files (attempt {attempt})")
            except Exception as e:
                logger.error(f"Error listing remote files (attempt {attempt}): {e}")

            if attempt < self.max_retries:
                time.sleep(self.retry_delay)

        return []

    def pull_file(self, remote_path: str, local_path: str, file_timeout: int = 300) -> bool:
        """
        Pull a single file from SUT with retry logic.

        Args:
            remote_path: Full path to file on SUT
            local_path: Local destination path
            file_timeout: Timeout for file transfer in seconds (default: 5 min)

        Returns:
            True if successful
        """
        # Ensure local directory exists
        local_dir = Path(local_path).parent
        local_dir.mkdir(parents=True, exist_ok=True)

        for attempt in range(1, self.max_retries + 1):
            try:
                # Use SCP to copy file
                result = subprocess.run(
                    ["scp"] + self._get_ssh_options() + [
                        f"{self.ssh_user}@{self.sut_ip}:{remote_path}",
                        local_path
                    ],
                    capture_output=True, text=True, timeout=file_timeout
                )

                if result.returncode == 0:
                    logger.info(f"Successfully pulled: {remote_path} -> {local_path}")
                    return True
                else:
                    logger.warning(f"SCP failed (attempt {attempt}): {result.stderr}")

            except subprocess.TimeoutExpired:
                logger.warning(f"SCP timed out for {remote_path} (attempt {attempt})")
            except Exception as e:
                logger.error(f"Error pulling file (attempt {attempt}): {e}")

            if attempt < self.max_retries:
                delay = self.retry_delay * attempt
                logger.info(f"Retrying SCP in {delay}s...")
                time.sleep(delay)

        logger.error(f"Failed to pull {remote_path} after {self.max_retries} attempts")
        return False

    def pull_directory(self, remote_dir: str, local_dir: str, dir_timeout: int = 600) -> int:
        """
        Pull entire directory from SUT with retry logic.

        Args:
            remote_dir: Remote directory path
            local_dir: Local destination directory
            dir_timeout: Timeout for directory transfer in seconds (default: 10 min)

        Returns:
            Number of files pulled
        """
        # Ensure local directory exists
        Path(local_dir).mkdir(parents=True, exist_ok=True)

        for attempt in range(1, self.max_retries + 1):
            try:
                # Use SCP -r for recursive copy
                result = subprocess.run(
                    ["scp", "-r"] + self._get_ssh_options() + [
                        f"{self.ssh_user}@{self.sut_ip}:{remote_dir}/*",
                        local_dir
                    ],
                    capture_output=True, text=True, timeout=dir_timeout
                )

                if result.returncode == 0:
                    # Count pulled files
                    pulled = len(list(Path(local_dir).glob("*")))
                    logger.info(f"Successfully pulled {pulled} files from {remote_dir}")
                    return pulled
                else:
                    logger.warning(f"SCP recursive failed (attempt {attempt}): {result.stderr}")

            except subprocess.TimeoutExpired:
                logger.warning(f"SCP timed out for directory {remote_dir} (attempt {attempt})")
            except Exception as e:
                logger.error(f"Error pulling directory (attempt {attempt}): {e}")

            if attempt < self.max_retries:
                delay = self.retry_delay * attempt
                logger.info(f"Retrying SCP in {delay}s...")
                time.sleep(delay)

        logger.error(f"Failed to pull directory {remote_dir} after {self.max_retries} attempts")
        return 0

    def pull_traces(self, run_id: str, game_name: str, trace_output_dir: str,
                    local_storage_dir: str, trace_agents: List[str] = None) -> dict:
        """
        Pull all trace files for a run.

        Args:
            run_id: Run ID for organizing files
            game_name: Game name for filename matching
            trace_output_dir: Remote trace output directory on SUT
            local_storage_dir: Local storage directory for the run
            trace_agents: List of trace agents to pull (default: all)

        Returns:
            Dict with results per agent: {"ptat": {"files": [...], "success": True}, ...}
        """
        results = {}
        trace_agents = trace_agents or ["ptat", "socwatch"]

        # Test connection first
        connected, conn_msg = self.test_connection()
        if not connected:
            logger.error(f"Cannot pull traces - SSH connection failed: {conn_msg}")
            return {"error": conn_msg, "success": False}

        # Create traces subdirectory in run storage
        traces_dir = Path(local_storage_dir) / "traces"
        traces_dir.mkdir(parents=True, exist_ok=True)

        # Pull traces for each agent
        for agent in trace_agents:
            agent_results = {"files": [], "success": False}

            try:
                # Determine remote path pattern based on agent
                # Trace files are named: {sut_ip}_{date}_{agent}_{game_name}.*
                date_pattern = datetime.now().strftime("%Y%m%d")

                if agent == "ptat":
                    # PTAT files are in the output directory with .csv extension
                    file_pattern = f"*{agent}*{game_name.replace('-', '')}*.csv"
                    remote_search_dir = trace_output_dir or self.DEFAULT_TRACE_DIRS["ptat"]
                elif agent == "socwatch":
                    # socwatch creates a directory with multiple files
                    file_pattern = f"*{agent}*{game_name.replace('-', '')}*"
                    remote_search_dir = trace_output_dir or self.DEFAULT_TRACE_DIRS["socwatch"]
                else:
                    logger.warning(f"Unknown trace agent: {agent}")
                    continue

                logger.info(f"Searching for {agent} traces in {remote_search_dir} with pattern {file_pattern}")

                # List matching files
                files = self.list_remote_files(remote_search_dir, file_pattern)

                if not files:
                    # Try broader pattern
                    files = self.list_remote_files(remote_search_dir, f"*{agent}*")

                if files:
                    logger.info(f"Found {len(files)} {agent} trace files")

                    # Create agent subdirectory
                    agent_dir = traces_dir / agent
                    agent_dir.mkdir(exist_ok=True)

                    # Pull each file
                    for filename in files:
                        remote_path = f"{remote_search_dir}\\{filename}"
                        local_path = str(agent_dir / filename)

                        if self.pull_file(remote_path, local_path):
                            agent_results["files"].append(filename)

                    agent_results["success"] = len(agent_results["files"]) > 0
                else:
                    logger.warning(f"No {agent} trace files found in {remote_search_dir}")

            except Exception as e:
                logger.error(f"Error pulling {agent} traces: {e}")
                agent_results["error"] = str(e)

            results[agent] = agent_results

        # Summary
        total_files = sum(len(r.get("files", [])) for r in results.values())
        results["total_files"] = total_files
        results["success"] = total_files > 0
        results["storage_dir"] = str(traces_dir)

        logger.info(f"Trace pulling complete: {total_files} files pulled to {traces_dir}")

        return results


def pull_run_traces(sut_ip: str, run_id: str, game_name: str,
                    trace_output_dir: str, local_storage_dir: str,
                    trace_agents: List[str] = None, ssh_user: str = None,
                    ssh_timeout: int = 60, max_retries: int = 3) -> dict:
    """
    Convenience function to pull traces for a run.

    Args:
        sut_ip: SUT IP address
        run_id: Run ID
        game_name: Game name
        trace_output_dir: Remote trace output directory
        local_storage_dir: Local run storage directory
        trace_agents: List of agents to pull traces for
        ssh_user: SSH username (optional)
        ssh_timeout: SSH connection timeout in seconds (default: 60)
        max_retries: Maximum retry attempts (default: 3)

    Returns:
        Result dict with pulled files and status
    """
    puller = TracePuller(sut_ip, ssh_user, ssh_timeout=ssh_timeout, max_retries=max_retries)
    return puller.pull_traces(run_id, game_name, trace_output_dir,
                              local_storage_dir, trace_agents)


def diagnose_sut_ssh(sut_ip: str, ssh_user: str = None) -> dict:
    """
    Diagnose SSH connectivity to a SUT.

    Args:
        sut_ip: SUT IP address
        ssh_user: SSH username (optional)

    Returns:
        Diagnostic results dict
    """
    puller = TracePuller(sut_ip, ssh_user)
    return puller.diagnose_connection()
