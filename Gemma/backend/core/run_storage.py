# -*- coding: utf-8 -*-
"""
Run Storage Manager - Persistent storage for automation runs

Handles:
- Meaningful folder naming with telemetry
- manifest.json creation and updates
- Per-iteration folder management (perf-run-1, perf-run-2, etc.)
- Screenshot, log, and results storage
- Run history loading from disk
"""

import json
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class SUTInfo:
    """SUT hardware and system information"""
    ip: str
    hostname: str = ""
    device_id: str = ""
    cpu_brand: str = ""
    cpu_model: str = ""  # Short model like "14600KF"
    cpu_codename: str = ""  # Like "Raptor Lake"
    gpu_name: str = ""
    gpu_short: str = ""
    ram_gb: int = 0
    os_name: str = ""
    os_version: str = ""
    os_build: str = ""
    resolution_width: int = 0
    resolution_height: int = 0
    bios_name: str = ""
    bios_version: str = ""

    @classmethod
    def from_system_info(cls, ip: str, system_info: Dict[str, Any]) -> 'SUTInfo':
        """Create SUTInfo from /system_info API response"""
        cpu = system_info.get('cpu', {})
        gpu = system_info.get('gpu', {})
        ram = system_info.get('ram', {})
        os_info = system_info.get('os', {})
        screen = system_info.get('screen', {})
        bios = system_info.get('bios', {})

        # Extract CPU model (e.g., "14600KF" from "Intel(R) Core(TM) i5-14600KF")
        cpu_brand = cpu.get('brand_string', '')
        cpu_model = cls._extract_cpu_model(cpu_brand)
        cpu_codename = cls._get_cpu_codename(cpu_brand)

        # Extract GPU short name
        gpu_name = gpu.get('name', '')
        gpu_short = cls._extract_gpu_short(gpu_name)

        return cls(
            ip=ip,
            hostname=system_info.get('hostname', ''),
            device_id=system_info.get('device_id', ''),
            cpu_brand=cpu_brand,
            cpu_model=cpu_model,
            cpu_codename=cpu_codename,
            gpu_name=gpu_name,
            gpu_short=gpu_short,
            ram_gb=ram.get('total_gb', 0),
            os_name=os_info.get('name', ''),
            os_version=os_info.get('version', ''),
            os_build=os_info.get('build', ''),
            resolution_width=screen.get('width', 0),
            resolution_height=screen.get('height', 0),
            bios_name=bios.get('name', ''),
            bios_version=bios.get('version', ''),
        )

    @staticmethod
    def _extract_cpu_model(brand_string: str) -> str:
        """Extract short CPU model from brand string"""
        if not brand_string:
            return "Unknown"

        # Intel patterns: i5-14600KF, i7-13700K, etc.
        intel_match = re.search(r'i[3579]-(\d{4,5}[A-Z]*)', brand_string, re.IGNORECASE)
        if intel_match:
            return intel_match.group(1)

        # Intel Core Ultra patterns
        ultra_match = re.search(r'Ultra\s+[3579]\s+(\d{3}[A-Z]*)', brand_string, re.IGNORECASE)
        if ultra_match:
            return f"Ultra-{ultra_match.group(1)}"

        # AMD patterns: Ryzen 9 7950X, Ryzen 7 7800X3D, etc.
        amd_match = re.search(r'Ryzen\s+[3579]\s+(\d{4}[A-Z\d]*)', brand_string, re.IGNORECASE)
        if amd_match:
            return amd_match.group(1)

        # Fallback: last word
        parts = brand_string.split()
        return parts[-1] if parts else "Unknown"

    @staticmethod
    def _get_cpu_codename(brand_string: str) -> str:
        """Get Intel/AMD codename from brand string"""
        if not brand_string:
            return "Unknown"

        # Intel codenames
        if re.search(r'i[3579]-15\d{2,3}', brand_string, re.IGNORECASE):
            return "Arrow Lake"
        if re.search(r'i[3579]-14\d{2,3}', brand_string, re.IGNORECASE):
            return "Raptor Lake"
        if re.search(r'i[3579]-13\d{2,3}', brand_string, re.IGNORECASE):
            return "Raptor Lake"
        if re.search(r'i[3579]-12\d{2,3}', brand_string, re.IGNORECASE):
            return "Alder Lake"
        if re.search(r'i[3579]-11\d{2,3}', brand_string, re.IGNORECASE):
            return "Rocket Lake"
        if re.search(r'i[3579]-10\d{2,3}', brand_string, re.IGNORECASE):
            return "Comet Lake"
        if re.search(r'Core Ultra [579] 2\d{2}', brand_string, re.IGNORECASE):
            return "Arrow Lake"
        if re.search(r'Core Ultra [579] 1\d{2}', brand_string, re.IGNORECASE):
            return "Meteor Lake"

        # AMD codenames
        if re.search(r'Ryzen [3579] 9\d{3}', brand_string, re.IGNORECASE):
            return "Granite Ridge"
        if re.search(r'Ryzen [3579] 7\d{3}', brand_string, re.IGNORECASE):
            return "Raphael"
        if re.search(r'Ryzen [3579] 5\d{3}', brand_string, re.IGNORECASE):
            return "Vermeer"
        if re.search(r'Ryzen [3579] 3\d{3}', brand_string, re.IGNORECASE):
            return "Matisse"

        return "Unknown"

    @staticmethod
    def _extract_gpu_short(gpu_name: str) -> str:
        """Extract short GPU name"""
        if not gpu_name:
            return "Unknown"

        # Remove common prefixes
        short = gpu_name
        short = re.sub(r'^NVIDIA\s+', '', short, flags=re.IGNORECASE)
        short = re.sub(r'^GeForce\s+', '', short, flags=re.IGNORECASE)
        short = re.sub(r'^AMD\s+', '', short, flags=re.IGNORECASE)
        short = re.sub(r'^Radeon\s+', '', short, flags=re.IGNORECASE)

        return short.strip() or gpu_name


@dataclass
class RunConfig:
    """Run configuration"""
    run_type: str  # "single" or "bulk"
    games: List[str] = field(default_factory=list)
    iterations: int = 3
    preset_level: str = ""
    trace_enabled: bool = False


@dataclass
class IterationInfo:
    """Information about a single iteration"""
    number: int
    iteration_type: str  # "perf" or "trace"
    status: str = "pending"  # pending, running, completed, failed
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: int = 0
    screenshots_count: int = 0
    results_file: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class RunManifest:
    """Complete run manifest stored as manifest.json"""
    version: str = "1.0"
    run_id: str = ""
    folder_name: str = ""
    created_at: str = ""
    completed_at: Optional[str] = None
    status: str = "running"  # running, completed, failed, stopped

    sut: Optional[SUTInfo] = None
    config: Optional[RunConfig] = None
    iterations: List[IterationInfo] = field(default_factory=list)

    summary: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'version': self.version,
            'run_id': self.run_id,
            'folder_name': self.folder_name,
            'created_at': self.created_at,
            'completed_at': self.completed_at,
            'status': self.status,
            'sut': asdict(self.sut) if self.sut else None,
            'config': asdict(self.config) if self.config else None,
            'iterations': [asdict(i) for i in self.iterations],
            'summary': self.summary,
            'errors': self.errors,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RunManifest':
        """Create RunManifest from dictionary"""
        manifest = cls(
            version=data.get('version', '1.0'),
            run_id=data.get('run_id', ''),
            folder_name=data.get('folder_name', ''),
            created_at=data.get('created_at', ''),
            completed_at=data.get('completed_at'),
            status=data.get('status', 'unknown'),
            summary=data.get('summary', {}),
            errors=data.get('errors', []),
        )

        if data.get('sut'):
            manifest.sut = SUTInfo(**data['sut'])
        if data.get('config'):
            manifest.config = RunConfig(**data['config'])
        if data.get('iterations'):
            manifest.iterations = [IterationInfo(**i) for i in data['iterations']]

        return manifest


class RunStorageManager:
    """
    Manages persistent storage of automation runs.

    Directory structure:
    logs/runs/{date}_{time}_{cpu}_{ip}_{type}-{game}/
    ├── manifest.json
    ├── perf-run-1/
    │   ├── blackbox_perf-run1_{cpu}_{ip}_{game}.log
    │   ├── screenshots/
    │   └── results/
    ├── perf-run-2/
    ├── perf-run-3/
    └── trace-run/
    """

    def __init__(self, base_dir: str = None):
        """
        Initialize RunStorageManager.

        Args:
            base_dir: Base directory for logs. Defaults to Gemma/logs/runs/
        """
        if base_dir is None:
            # Default to Gemma/logs/runs/
            gemma_dir = Path(__file__).parent.parent.parent
            base_dir = gemma_dir / "logs" / "runs"

        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self._run_cache: Dict[str, RunManifest] = {}

        logger.info(f"RunStorageManager initialized with base_dir: {self.base_dir}")

    def generate_folder_name(
        self,
        sut_info: SUTInfo,
        run_type: str,
        games: List[str],
        timestamp: datetime = None
    ) -> str:
        """
        Generate meaningful folder name from telemetry.

        Format: {YYYY-MM-DD}_{HHMMSS}_{cpu}_{ip}_{type}-{game(s)}
        Example: 2025-12-28_163045_14600KF_192-168-0-103_single-BMW

        Args:
            sut_info: SUT hardware information
            run_type: "single" or "bulk"
            games: List of game names
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Folder name string
        """
        if timestamp is None:
            timestamp = datetime.now()

        date_str = timestamp.strftime("%Y-%m-%d")
        time_str = timestamp.strftime("%H%M%S")
        cpu = sut_info.cpu_model or "Unknown"
        ip_dashed = sut_info.ip.replace('.', '-')

        if run_type == "single" or len(games) == 1:
            game_str = f"single-{games[0]}" if games else "single-Unknown"
        else:
            # Bulk run with multiple games
            game_str = f"bulk-{'-'.join(games[:3])}"  # Limit to 3 games in name
            if len(games) > 3:
                game_str += f"-and{len(games)-3}more"

        folder_name = f"{date_str}_{time_str}_{cpu}_{ip_dashed}_{game_str}"

        # Sanitize folder name (remove invalid chars)
        folder_name = re.sub(r'[<>:"/\\|?*]', '', folder_name)

        return folder_name

    def create_run(
        self,
        run_id: str,
        sut_info: SUTInfo,
        config: RunConfig,
        timestamp: datetime = None
    ) -> RunManifest:
        """
        Create a new run with folder structure and manifest.

        Args:
            run_id: Unique run identifier
            sut_info: SUT hardware information
            config: Run configuration
            timestamp: Optional timestamp

        Returns:
            RunManifest object
        """
        if timestamp is None:
            timestamp = datetime.now()

        folder_name = self.generate_folder_name(
            sut_info=sut_info,
            run_type=config.run_type,
            games=config.games,
            timestamp=timestamp
        )

        run_dir = self.base_dir / folder_name
        run_dir.mkdir(parents=True, exist_ok=True)

        # Create iteration folders
        iterations = []
        for i in range(1, config.iterations + 1):
            iter_folder = run_dir / f"perf-run-{i}"
            iter_folder.mkdir(exist_ok=True)
            (iter_folder / "screenshots").mkdir(exist_ok=True)
            (iter_folder / "results").mkdir(exist_ok=True)

            iterations.append(IterationInfo(
                number=i,
                iteration_type="perf",
                status="pending"
            ))

        # Create trace-run folder if enabled
        if config.trace_enabled:
            trace_folder = run_dir / "trace-run"
            trace_folder.mkdir(exist_ok=True)
            (trace_folder / "screenshots").mkdir(exist_ok=True)
            (trace_folder / "results").mkdir(exist_ok=True)

            iterations.append(IterationInfo(
                number=config.iterations + 1,
                iteration_type="trace",
                status="pending"
            ))

        # Create manifest
        manifest = RunManifest(
            run_id=run_id,
            folder_name=folder_name,
            created_at=timestamp.isoformat(),
            status="running",
            sut=sut_info,
            config=config,
            iterations=iterations,
        )

        # Save manifest
        self._save_manifest(manifest)

        # Cache it
        self._run_cache[run_id] = manifest

        logger.info(f"Created run storage: {folder_name}")

        return manifest

    def get_run_dir(self, run_id: str) -> Optional[Path]:
        """Get the run directory path for a run ID"""
        manifest = self._run_cache.get(run_id)
        if manifest:
            return self.base_dir / manifest.folder_name
        return None

    def get_iteration_dir(self, run_id: str, iteration: int) -> Optional[Path]:
        """Get the iteration directory path"""
        run_dir = self.get_run_dir(run_id)
        if run_dir:
            return run_dir / f"perf-run-{iteration}"
        return None

    def start_iteration(self, run_id: str, iteration: int) -> bool:
        """Mark an iteration as started"""
        manifest = self._run_cache.get(run_id)
        if not manifest:
            return False

        for iter_info in manifest.iterations:
            if iter_info.number == iteration:
                iter_info.status = "running"
                iter_info.started_at = datetime.now().isoformat()
                self._save_manifest(manifest)
                return True

        return False

    def complete_iteration(
        self,
        run_id: str,
        iteration: int,
        success: bool = True,
        error_message: str = None,
        results_file: str = None
    ) -> bool:
        """Mark an iteration as completed"""
        manifest = self._run_cache.get(run_id)
        if not manifest:
            return False

        for iter_info in manifest.iterations:
            if iter_info.number == iteration:
                iter_info.status = "completed" if success else "failed"
                iter_info.completed_at = datetime.now().isoformat()
                iter_info.results_file = results_file
                iter_info.error_message = error_message

                # Calculate duration
                if iter_info.started_at:
                    start = datetime.fromisoformat(iter_info.started_at)
                    end = datetime.fromisoformat(iter_info.completed_at)
                    iter_info.duration_seconds = int((end - start).total_seconds())

                # Count screenshots
                iter_dir = self.get_iteration_dir(run_id, iteration)
                if iter_dir:
                    screenshots_dir = iter_dir / "screenshots"
                    if screenshots_dir.exists():
                        iter_info.screenshots_count = len(list(screenshots_dir.glob("*.png")))

                self._save_manifest(manifest)
                return True

        return False

    def complete_run(
        self,
        run_id: str,
        success: bool = True,
        summary: Dict[str, Any] = None
    ) -> bool:
        """Mark the entire run as completed"""
        manifest = self._run_cache.get(run_id)
        if not manifest:
            return False

        manifest.status = "completed" if success else "failed"
        manifest.completed_at = datetime.now().isoformat()

        if summary:
            manifest.summary = summary
        else:
            # Generate summary from iterations
            completed = sum(1 for i in manifest.iterations if i.status == "completed")
            failed = sum(1 for i in manifest.iterations if i.status == "failed")
            total_duration = sum(i.duration_seconds for i in manifest.iterations)

            manifest.summary = {
                "total_iterations": len(manifest.iterations),
                "completed_iterations": completed,
                "failed_iterations": failed,
                "total_duration_seconds": total_duration,
            }

        self._save_manifest(manifest)
        logger.info(f"Run completed: {manifest.folder_name} - {manifest.status}")

        return True

    def save_screenshot(
        self,
        run_id: str,
        iteration: int,
        step_number: int,
        step_name: str,
        image_data: bytes
    ) -> Optional[str]:
        """
        Save a screenshot for an iteration.

        Args:
            run_id: Run identifier
            iteration: Iteration number
            step_number: Step number (1-based)
            step_name: Step description (e.g., "launch", "settings")
            image_data: PNG image bytes

        Returns:
            Path to saved screenshot, or None on failure
        """
        iter_dir = self.get_iteration_dir(run_id, iteration)
        if not iter_dir:
            return None

        screenshots_dir = iter_dir / "screenshots"
        screenshots_dir.mkdir(exist_ok=True)

        # Sanitize step name
        safe_step_name = re.sub(r'[<>:"/\\|?*\s]', '-', step_name.lower())
        filename = f"step_{step_number:02d}_{safe_step_name}.png"

        filepath = screenshots_dir / filename
        filepath.write_bytes(image_data)

        return str(filepath)

    def save_blackbox_log(
        self,
        run_id: str,
        iteration: int,
        log_content: str
    ) -> Optional[str]:
        """
        Save blackbox log for an iteration.

        Args:
            run_id: Run identifier
            iteration: Iteration number
            log_content: Log text content

        Returns:
            Path to saved log, or None on failure
        """
        manifest = self._run_cache.get(run_id)
        if not manifest:
            return None

        iter_dir = self.get_iteration_dir(run_id, iteration)
        if not iter_dir:
            return None

        # Generate log filename
        sut = manifest.sut
        config = manifest.config
        cpu = sut.cpu_model if sut else "Unknown"
        ip_dashed = sut.ip.replace('.', '-') if sut else "Unknown"
        game = config.games[0] if config and config.games else "Unknown"
        run_type = config.run_type if config else "single"

        filename = f"blackbox_perf-run{iteration}_{cpu}_{ip_dashed}_{run_type}-{game}.log"
        filepath = iter_dir / filename

        filepath.write_text(log_content, encoding='utf-8')

        return str(filepath)

    def save_results(
        self,
        run_id: str,
        iteration: int,
        filename: str,
        content: bytes
    ) -> Optional[str]:
        """
        Save benchmark results file for an iteration.

        Args:
            run_id: Run identifier
            iteration: Iteration number
            filename: Results filename (e.g., "benchmark.csv")
            content: File content bytes

        Returns:
            Path to saved file, or None on failure
        """
        iter_dir = self.get_iteration_dir(run_id, iteration)
        if not iter_dir:
            return None

        results_dir = iter_dir / "results"
        results_dir.mkdir(exist_ok=True)

        filepath = results_dir / filename
        filepath.write_bytes(content)

        return str(filepath)

    def add_error(self, run_id: str, error: str) -> bool:
        """Add an error message to the run"""
        manifest = self._run_cache.get(run_id)
        if not manifest:
            return False

        manifest.errors.append(f"[{datetime.now().isoformat()}] {error}")
        self._save_manifest(manifest)
        return True

    def get_manifest(self, run_id: str) -> Optional[RunManifest]:
        """Get manifest for a run"""
        return self._run_cache.get(run_id)

    def load_run_history(self) -> List[RunManifest]:
        """
        Load all runs from disk.

        Returns:
            List of RunManifest objects, sorted by creation date (newest first)
        """
        runs = []

        if not self.base_dir.exists():
            return runs

        for run_dir in self.base_dir.iterdir():
            if not run_dir.is_dir():
                continue

            manifest_path = run_dir / "manifest.json"
            if not manifest_path.exists():
                continue

            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                manifest = RunManifest.from_dict(data)
                runs.append(manifest)
                self._run_cache[manifest.run_id] = manifest
            except Exception as e:
                logger.warning(f"Failed to load manifest from {run_dir}: {e}")

        # Sort by creation date (newest first)
        runs.sort(key=lambda r: r.created_at, reverse=True)

        logger.info(f"Loaded {len(runs)} runs from history")
        return runs

    def _save_manifest(self, manifest: RunManifest) -> bool:
        """Save manifest to disk"""
        run_dir = self.base_dir / manifest.folder_name
        manifest_path = run_dir / "manifest.json"

        try:
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest.to_dict(), f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save manifest: {e}")
            return False

    def update_manifest(self, manifest: RunManifest) -> bool:
        """Update an existing manifest (status, error, completed_at, etc.)"""
        if manifest.run_id not in self._run_cache:
            logger.warning(f"Cannot update manifest - run {manifest.run_id} not in cache")
            return False

        # Update cache
        self._run_cache[manifest.run_id] = manifest

        # Save to disk
        return self._save_manifest(manifest)

    def delete_run(self, run_id: str) -> bool:
        """Delete a run and all its files"""
        manifest = self._run_cache.get(run_id)
        if not manifest:
            return False

        run_dir = self.base_dir / manifest.folder_name
        if run_dir.exists():
            shutil.rmtree(run_dir)

        del self._run_cache[run_id]
        logger.info(f"Deleted run: {manifest.folder_name}")
        return True

    def get_run_stats(self) -> Dict[str, Any]:
        """Get statistics about stored runs"""
        total_runs = len(self._run_cache)
        completed = sum(1 for m in self._run_cache.values() if m.status == "completed")
        failed = sum(1 for m in self._run_cache.values() if m.status == "failed")
        running = sum(1 for m in self._run_cache.values() if m.status == "running")

        # Calculate total disk usage
        total_size = 0
        if self.base_dir.exists():
            for f in self.base_dir.rglob('*'):
                if f.is_file():
                    total_size += f.stat().st_size

        return {
            "total_runs": total_runs,
            "completed": completed,
            "failed": failed,
            "running": running,
            "disk_usage_mb": round(total_size / (1024 * 1024), 2),
        }
