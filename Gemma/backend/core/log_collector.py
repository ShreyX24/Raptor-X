# -*- coding: utf-8 -*-
"""
Log Collector - Collects logs from all services for run correlation

This module provides functionality to:
1. Pull SUT Client logs via HTTP API
2. Copy local service logs (Queue Service, Preset Manager, SUT Discovery)
3. Save all logs to the run's service_logs directory for correlation

Architecture:
- Run ID is the correlation key
- Services log their blackbox logs to local files
- At run completion, this collector gathers all relevant logs
- Future: Intel SocWatch/PTAT traces will use the same mechanism

Usage:
    collector = LogCollector(run_storage, sut_client)
    collector.collect_all_logs(run_id, sut_ip, run_start_time)
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


class LogCollector:
    """
    Collects logs from all services involved in an automation run.

    Services:
    - SUT Client (remote) - pulled via HTTP API
    - Queue Service (local) - copied from queue_service.log
    - Preset Manager (local) - copied from preset_manager.log
    - SUT Discovery (local) - copied from sut_discovery.log
    """

    # Default log file locations (relative to project root)
    LOG_FILE_PATHS = {
        'queue_service': 'queue_service/queue_service.log',
        'preset_manager': 'preset-manager/preset_manager.log',  # Note: hyphen in folder name
        'sut_discovery': 'sut_discovery_service/sut_discovery.log',
    }

    def __init__(self, run_storage, sut_client=None, project_root: Path = None):
        """
        Initialize LogCollector.

        Args:
            run_storage: RunStorageManager instance
            sut_client: SUTClient instance for pulling remote logs
            project_root: Project root directory (auto-detected if not provided)
        """
        self.run_storage = run_storage
        self.sut_client = sut_client

        if project_root is None:
            # Default to parent of Gemma/backend/core
            project_root = Path(__file__).parent.parent.parent.parent
        self.project_root = project_root

        logger.debug(f"LogCollector initialized with project_root: {project_root}")

    def collect_all_logs(
        self,
        run_id: str,
        sut_ip: str = None,
        run_start_time: datetime = None
    ) -> dict:
        """
        Collect logs from all services for a run.

        Args:
            run_id: Run identifier
            sut_ip: SUT IP address (for pulling SUT Client logs)
            run_start_time: Start time of the run (for filtering logs)

        Returns:
            Dict with collection results for each service
        """
        results = {}

        # Widen the time window to 5 minutes before run start to capture pre-run setup
        if run_start_time:
            from datetime import timedelta
            adjusted_start = run_start_time - timedelta(minutes=5)
            since_iso = adjusted_start.isoformat()
        else:
            since_iso = None

        # 1. Pull SUT Client logs (remote)
        if sut_ip and self.sut_client:
            results['sut_client'] = self._collect_sut_client_logs(
                run_id, sut_ip, since_iso
            )

        # 2. Collect local service logs
        for service_name, log_path in self.LOG_FILE_PATHS.items():
            results[service_name] = self._collect_local_logs(
                run_id, service_name, log_path, since_iso
            )

        logger.info(f"Log collection complete for run {run_id}: {results}")
        return results

    def _collect_sut_client_logs(
        self,
        run_id: str,
        sut_ip: str,
        since_iso: str = None
    ) -> dict:
        """Pull logs from SUT Client via HTTP API."""
        try:
            result = self.sut_client.get_logs(
                ip=sut_ip,
                port=8080,
                lines=5000,  # Get last 5000 lines
                since=since_iso
            )

            if result.success and result.data:
                lines = result.data.get('lines', [])
                hostname = result.data.get('hostname', sut_ip)

                if lines:
                    saved_path = self.run_storage.save_service_logs(
                        run_id=run_id,
                        service_name='sut_client',
                        log_lines=lines,
                        hostname=hostname
                    )
                    return {
                        'success': True,
                        'lines_collected': len(lines),
                        'saved_to': saved_path
                    }
                else:
                    return {
                        'success': True,
                        'lines_collected': 0,
                        'message': 'No logs found for time range'
                    }
            else:
                return {
                    'success': False,
                    'error': result.error or 'Unknown error'
                }

        except Exception as e:
            logger.error(f"Error collecting SUT Client logs: {e}")
            return {'success': False, 'error': str(e)}

    def _collect_local_logs(
        self,
        run_id: str,
        service_name: str,
        log_path: str,
        since_iso: str = None
    ) -> dict:
        """Copy local service log file."""
        try:
            full_path = self.project_root / log_path

            if not full_path.exists():
                return {
                    'success': False,
                    'error': f'Log file not found: {full_path}'
                }

            # Read and optionally filter log lines
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()

            # Filter by timestamp if provided
            if since_iso:
                lines = self._filter_lines_by_time(all_lines, since_iso)
            else:
                # Get last 2000 lines if no time filter
                lines = all_lines[-2000:]

            lines = [line.rstrip('\n') for line in lines]

            if lines:
                saved_path = self.run_storage.save_service_logs(
                    run_id=run_id,
                    service_name=service_name,
                    log_lines=lines
                )
                return {
                    'success': True,
                    'lines_collected': len(lines),
                    'saved_to': saved_path
                }
            else:
                return {
                    'success': True,
                    'lines_collected': 0,
                    'message': 'No logs found for time range'
                }

        except Exception as e:
            logger.error(f"Error collecting {service_name} logs: {e}")
            return {'success': False, 'error': str(e)}

    def _filter_lines_by_time(
        self,
        lines: List[str],
        since_iso: str
    ) -> List[str]:
        """
        Filter log lines to only include those after a given timestamp.

        Expected log format: 2025-12-31 10:30:45,123 - ...
        """
        try:
            since_dt = datetime.fromisoformat(since_iso.replace('Z', '+00:00'))
        except ValueError:
            return lines  # Can't parse, return all

        filtered = []
        for line in lines:
            # Try to extract timestamp from log line
            if len(line) >= 23:
                try:
                    # Handle both comma and period as millisecond separator
                    line_time_str = line[:23].replace(',', '.')
                    line_time = datetime.fromisoformat(line_time_str)
                    if line_time >= since_dt:
                        filtered.append(line)
                except ValueError:
                    # Can't parse timestamp, include the line
                    filtered.append(line)
            else:
                # Short line, include it
                filtered.append(line)

        return filtered

    def download_sut_log_file(
        self,
        run_id: str,
        sut_ip: str
    ) -> Optional[str]:
        """
        Download full SUT Client log file (not just recent lines).

        Useful for debugging or when timestamps can't be reliably parsed.

        Args:
            run_id: Run identifier
            sut_ip: SUT IP address

        Returns:
            Path to saved log file, or None on failure
        """
        if not self.sut_client:
            return None

        try:
            logs_dir = self.run_storage.get_service_logs_dir(run_id)
            if not logs_dir:
                return None

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = logs_dir / f"sut_client_full_{sut_ip.replace('.', '-')}_{timestamp}.log"

            result = self.sut_client.download_logs(
                ip=sut_ip,
                port=8080,
                save_path=str(save_path)
            )

            if result.success:
                logger.info(f"Downloaded full SUT log to {save_path}")
                return str(save_path)
            else:
                logger.error(f"Failed to download SUT log: {result.error}")
                return None

        except Exception as e:
            logger.error(f"Error downloading SUT log file: {e}")
            return None
