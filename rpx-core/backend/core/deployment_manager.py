# -*- coding: utf-8 -*-
"""
Deployment Manager — orchestrates push-based sut_client updates to SUTs.

Builds a zip archive of the sut_client source, pushes it to each SUT via
the /self-update HTTP endpoint, waits for restart, and runs preflight checks.
"""

import logging
import shutil
import tempfile
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .run_manager import RunManager
    from ..communication.sut_client import SUTClient
    from ..discovery.device_registry import DeviceRegistry

logger = logging.getLogger(__name__)


@dataclass
class SUTDeployStatus:
    """Per-SUT deployment tracking."""
    sut_ip: str
    device_id: str
    status: str = "pending"  # pending|pausing|pushing|restarting|preflight|completed|failed
    error: Optional[str] = None
    old_version: Optional[str] = None
    new_version: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "sut_ip": self.sut_ip,
            "device_id": self.device_id,
            "status": self.status,
            "error": self.error,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class DeploymentJob:
    """Overall deployment job tracking."""
    deploy_id: str
    status: str = "running"  # running|completed|partial_failure|failed
    sut_statuses: Dict[str, SUTDeployStatus] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    archive_path: Optional[str] = None
    version: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "deploy_id": self.deploy_id,
            "status": self.status,
            "version": self.version,
            "created_at": self.created_at,
            "suts": {ip: s.to_dict() for ip, s in self.sut_statuses.items()},
        }


class DeploymentManager:
    """Orchestrates push-based sut_client deployments to SUT devices."""

    def __init__(
        self,
        run_manager: 'RunManager',
        sut_client: 'SUTClient',
        device_registry: 'DeviceRegistry',
        post_update_delay: int = 0,
        restart_timeout: int = 120,
        preflight_checks: bool = True,
    ):
        self.run_manager = run_manager
        self.sut_client = sut_client
        self.device_registry = device_registry

        self.post_update_delay = post_update_delay
        self.restart_timeout = restart_timeout
        self.preflight_checks = preflight_checks

        self._current_job: Optional[DeploymentJob] = None
        self._job_lock = threading.Lock()

    # ── Archive builder ──────────────────────────────────────────────────

    def build_archive(self) -> str:
        """Build a zip archive of the sut_client package.

        Returns:
            Path to the temporary zip file.
        """
        # Navigate from rpx-core/backend/core/ up to repo root, then into sut_client/
        sut_client_dir = Path(__file__).resolve().parent.parent.parent.parent / "sut_client"

        if not sut_client_dir.is_dir():
            raise FileNotFoundError(f"sut_client directory not found at {sut_client_dir}")

        if not (sut_client_dir / "pyproject.toml").is_file():
            raise FileNotFoundError(f"pyproject.toml not found in {sut_client_dir}")

        tmp = tempfile.mktemp(suffix=".zip", prefix="sut_deploy_")
        skip_patterns = {"__pycache__", ".pyc", ".git", ".egg-info"}

        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in sut_client_dir.rglob("*"):
                # Skip unwanted paths
                parts = file_path.relative_to(sut_client_dir).parts
                if any(skip in part for part in parts for skip in skip_patterns):
                    continue
                if file_path.is_file():
                    arcname = str(file_path.relative_to(sut_client_dir))
                    zf.write(file_path, arcname)

        size_mb = round(Path(tmp).stat().st_size / (1024 * 1024), 2)
        logger.info(f"Built deploy archive: {tmp} ({size_mb} MB)")
        return tmp

    def _get_version_from_source(self) -> str:
        """Read __version__ from sut_client source."""
        init_file = Path(__file__).resolve().parent.parent.parent.parent / "sut_client" / "src" / "sut_client" / "__init__.py"
        try:
            for line in init_file.read_text().splitlines():
                if line.startswith("__version__"):
                    # __version__ = "0.3.0"
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception as e:
            logger.warning(f"Could not read sut_client version: {e}")
        return "unknown"

    # ── Per-SUT deployment ───────────────────────────────────────────────

    def deploy_to_sut(self, sut_ip: str, device_id: str, archive_path: str, version: str) -> SUTDeployStatus:
        """Run the full deploy sequence for a single SUT.

        Steps:
        1. Pause SUT queue
        2. Wait for SUT to become idle
        3. Get current version
        4. Push archive
        5. Wait for SUT to restart
        6. Preflight check
        7. Resume SUT queue
        """
        status = SUTDeployStatus(sut_ip=sut_ip, device_id=device_id, new_version=version)
        status.started_at = datetime.now().isoformat()

        try:
            # Step 1: Pause SUT queue immediately to prevent new runs
            status.status = "pausing"
            self.run_manager.pause_sut(sut_ip)

            # Step 2: Wait for any active run to finish
            if not self.run_manager.is_sut_idle(sut_ip):
                logger.info(f"[Deploy {sut_ip}] Waiting for active run to finish...")
                if not self.run_manager.wait_for_sut_idle(sut_ip, timeout=300):
                    raise RuntimeError(f"SUT {sut_ip} did not become idle within 300s")

            # Step 3: Get current version
            ver_result = self.sut_client.get_update_status(sut_ip, 8080)
            if ver_result.success and ver_result.data:
                status.old_version = ver_result.data.get("version", "unknown")
            else:
                status.old_version = "unknown"

            # Step 4: Push archive
            status.status = "pushing"
            logger.info(f"[Deploy {sut_ip}] Pushing archive (version {version})...")
            push_result = self.sut_client.push_update(sut_ip, 8080, archive_path, version)
            if not push_result.success:
                raise RuntimeError(f"Push failed: {push_result.error}")

            # Step 5: Wait for SUT to go offline then come back
            status.status = "restarting"
            logger.info(f"[Deploy {sut_ip}] Waiting for SUT to restart...")
            time.sleep(10)  # Give SUT time to begin restart

            ready_result = self.sut_client.wait_for_sut_ready(
                sut_ip, 8080, timeout=self.restart_timeout, interval=5
            )
            if not ready_result.success:
                raise RuntimeError(f"SUT did not come back: {ready_result.error}")

            wait_secs = ready_result.data.get("wait_seconds", "?") if ready_result.data else "?"
            logger.info(f"[Deploy {sut_ip}] SUT back online after {wait_secs}s")

            # Step 6: Preflight check
            if self.preflight_checks:
                status.status = "preflight"
                health = self.sut_client.health_check(sut_ip, 8080)
                if not health.success:
                    raise RuntimeError(f"Preflight health check failed: {health.error}")

                ver_check = self.sut_client.get_update_status(sut_ip, 8080)
                if ver_check.success and ver_check.data:
                    actual_version = ver_check.data.get("version", "unknown")
                    if actual_version != version:
                        logger.warning(
                            f"[Deploy {sut_ip}] Version mismatch: expected {version}, got {actual_version}"
                        )
                    else:
                        logger.info(f"[Deploy {sut_ip}] Version verified: {actual_version}")

            # Optional post-update delay
            if self.post_update_delay > 0:
                logger.info(f"[Deploy {sut_ip}] Post-update delay: {self.post_update_delay}s")
                time.sleep(self.post_update_delay)

            status.status = "completed"
            status.completed_at = datetime.now().isoformat()
            logger.info(f"[Deploy {sut_ip}] Deployment completed successfully")

        except Exception as e:
            status.status = "failed"
            status.error = str(e)
            status.completed_at = datetime.now().isoformat()
            logger.error(f"[Deploy {sut_ip}] Deployment failed: {e}")

        finally:
            # Always resume SUT queue
            self.run_manager.resume_sut(sut_ip)

        return status

    # ── Multi-SUT deployment ─────────────────────────────────────────────

    def deploy_to_all(self, sut_ips: Optional[List[str]] = None, post_update_delay: int = None) -> DeploymentJob:
        """Deploy to all online paired SUTs (or specific list).

        Args:
            sut_ips: Specific IPs to deploy to, or None for all online paired SUTs.
            post_update_delay: Override the default post-update delay.

        Returns:
            DeploymentJob with results.
        """
        if post_update_delay is not None:
            self.post_update_delay = post_update_delay

        # Build the archive
        archive_path = self.build_archive()
        version = self._get_version_from_source()

        # Determine target SUTs
        if sut_ips:
            targets = []
            for ip in sut_ips:
                device = self.device_registry.get_device_by_ip(ip)
                if device:
                    targets.append((ip, device.unique_id))
                else:
                    targets.append((ip, "unknown"))
        else:
            online_devices = self.device_registry.get_online_devices()
            paired_online = [d for d in online_devices if d.is_paired]
            targets = [(d.ip, d.unique_id) for d in paired_online]

        if not targets:
            job = DeploymentJob(
                deploy_id=str(uuid.uuid4())[:8],
                status="failed",
                archive_path=archive_path,
                version=version,
            )
            logger.warning("No target SUTs found for deployment")
            return job

        # Create job
        job = DeploymentJob(
            deploy_id=str(uuid.uuid4())[:8],
            archive_path=archive_path,
            version=version,
        )
        for ip, device_id in targets:
            job.sut_statuses[ip] = SUTDeployStatus(sut_ip=ip, device_id=device_id, new_version=version)

        with self._job_lock:
            self._current_job = job

        logger.info(f"Starting deployment {job.deploy_id} to {len(targets)} SUT(s), version={version}")

        # Deploy in parallel
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(self.deploy_to_sut, ip, device_id, archive_path, version): ip
                for ip, device_id in targets
            }

            for future in as_completed(futures):
                ip = futures[future]
                try:
                    result = future.result()
                    job.sut_statuses[ip] = result
                except Exception as e:
                    logger.error(f"[Deploy {ip}] Unexpected error: {e}")
                    job.sut_statuses[ip].status = "failed"
                    job.sut_statuses[ip].error = str(e)

        # Determine overall status
        statuses = [s.status for s in job.sut_statuses.values()]
        if all(s == "completed" for s in statuses):
            job.status = "completed"
        elif all(s == "failed" for s in statuses):
            job.status = "failed"
        else:
            job.status = "partial_failure"

        # Clean up archive
        try:
            Path(archive_path).unlink(missing_ok=True)
        except Exception:
            pass

        logger.info(f"Deployment {job.deploy_id} finished: {job.status}")
        return job

    # ── Status ───────────────────────────────────────────────────────────

    def get_deploy_status(self) -> Optional[dict]:
        """Return current deployment job status, or None."""
        with self._job_lock:
            if self._current_job:
                return self._current_job.to_dict()
        return None
