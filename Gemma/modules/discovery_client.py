# -*- coding: utf-8 -*-
"""
Client for external SUT Discovery Service.
Used when Gemma is configured to use standalone Discovery Service.
"""

import logging
from typing import List, Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)


class DiscoveryServiceClient:
    """
    Client to communicate with standalone SUT Discovery Service.

    When use_external_discovery is True, Gemma uses this client
    instead of internal discovery for all SUT communication.
    """

    def __init__(
        self,
        discovery_url: str = "http://localhost:5001",
        timeout: float = 10.0,
        retry_count: int = 3,
        retry_delay: float = 1.0
    ):
        self.discovery_url = discovery_url.rstrip("/")
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self._available = None

    async def get_suts(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all SUTs from discovery service."""
        params = {"status": status} if status else {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.discovery_url}/api/suts", params=params)
                response.raise_for_status()
                return response.json().get("suts", [])
        except Exception as e:
            logger.error(f"Failed to get SUTs from Discovery Service: {e}")
            return []

    async def get_online_suts(self) -> List[Dict[str, Any]]:
        """Get all online SUTs."""
        return await self.get_suts(status="online")

    async def get_paired_suts(self) -> List[Dict[str, Any]]:
        """Get all paired SUTs."""
        return await self.get_suts(status="paired")

    async def get_sut(self, unique_id: str) -> Optional[Dict[str, Any]]:
        """Get specific SUT by ID."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.discovery_url}/api/suts/{unique_id}")
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get SUT {unique_id}: {e}")
            return None

    async def get_sut_by_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        """Find SUT by IP address."""
        suts = await self.get_suts()
        return next((s for s in suts if s.get("ip") == ip), None)

    async def get_installed_games(self, unique_id: str) -> List[Dict[str, Any]]:
        """Get installed games on SUT via Discovery Service proxy."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.discovery_url}/api/suts/{unique_id}/games")
                response.raise_for_status()
                data = response.json()
                return data.get("games", [])
        except Exception as e:
            logger.error(f"Failed to get games for SUT {unique_id}: {e}")
            return []

    async def get_sut_status(self, unique_id: str) -> Optional[Dict[str, Any]]:
        """Get SUT status via Discovery Service proxy."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.discovery_url}/api/suts/{unique_id}/status")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get status for SUT {unique_id}: {e}")
            return None

    async def take_screenshot(self, unique_id: str) -> Optional[bytes]:
        """Take screenshot from SUT via Discovery Service proxy."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.discovery_url}/api/suts/{unique_id}/screenshot")
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"Failed to take screenshot from SUT {unique_id}: {e}")
            return None

    async def perform_action(self, unique_id: str, action_data: dict) -> Dict[str, Any]:
        """Perform action on SUT via Discovery Service proxy."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.discovery_url}/api/suts/{unique_id}/action",
                    json=action_data
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to perform action on SUT {unique_id}: {e}")
            return {"success": False, "error": str(e)}

    async def launch_application(self, unique_id: str, path: str, process_id: Optional[str] = None) -> Dict[str, Any]:
        """Launch application on SUT via Discovery Service proxy."""
        try:
            payload = {"path": path}
            if process_id:
                payload["process_id"] = process_id

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.discovery_url}/api/suts/{unique_id}/launch",
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to launch application on SUT {unique_id}: {e}")
            return {"success": False, "error": str(e)}

    async def apply_preset(self, unique_id: str, preset_data: dict) -> Dict[str, Any]:
        """Apply preset to SUT via Discovery Service proxy."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.discovery_url}/api/suts/{unique_id}/apply-preset",
                    json=preset_data
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to apply preset to SUT {unique_id}: {e}")
            return {"success": False, "error": str(e)}

    async def pair_device(self, unique_id: str, paired_by: str = "gemma") -> bool:
        """Pair a device via Discovery Service."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.discovery_url}/api/suts/{unique_id}/pair",
                    json={"paired_by": paired_by}
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to pair device {unique_id}: {e}")
            return False

    async def unpair_device(self, unique_id: str) -> bool:
        """Unpair a device via Discovery Service."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.discovery_url}/api/suts/{unique_id}/unpair"
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to unpair device {unique_id}: {e}")
            return False

    async def trigger_discovery(self) -> Dict[str, Any]:
        """Trigger a discovery scan via Discovery Service."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.discovery_url}/api/discover")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to trigger discovery: {e}")
            return {"success": False, "error": str(e)}

    def is_available(self) -> bool:
        """Check if Discovery Service is available (sync version for startup check)."""
        import requests
        try:
            response = requests.get(f"{self.discovery_url}/health", timeout=3)
            self._available = response.status_code == 200
            return self._available
        except Exception:
            self._available = False
            return False

    async def is_available_async(self) -> bool:
        """Check if Discovery Service is available (async version)."""
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{self.discovery_url}/health")
                self._available = response.status_code == 200
                return self._available
        except Exception:
            self._available = False
            return False

    async def wait_for_service(self, max_retries: int = 10, delay: float = 1.0) -> bool:
        """
        Wait for Discovery Service to become available with exponential backoff.

        Args:
            max_retries: Maximum number of retry attempts
            delay: Initial delay between retries (doubles each retry)

        Returns:
            True if service became available, False if max retries reached
        """
        import asyncio

        current_delay = delay
        for attempt in range(max_retries):
            if await self.is_available_async():
                logger.info(f"Discovery Service available after {attempt + 1} attempts")
                return True

            logger.warning(
                f"Discovery Service not available, attempt {attempt + 1}/{max_retries}, "
                f"retrying in {current_delay:.1f}s..."
            )
            await asyncio.sleep(current_delay)
            current_delay = min(current_delay * 2, 30)  # Cap at 30 seconds

        logger.error(f"Discovery Service not available after {max_retries} attempts")
        return False

    def get_discovery_status_sync(self) -> Dict[str, Any]:
        """Get discovery status (sync version)."""
        import requests
        try:
            response = requests.get(f"{self.discovery_url}/api/discovery/status", timeout=5)
            if response.status_code == 200:
                return response.json()
            return {"running": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"running": False, "error": str(e)}

    def get_device_stats_sync(self) -> Dict[str, Any]:
        """Get device statistics (sync version)."""
        import requests
        try:
            response = requests.get(f"{self.discovery_url}/api/suts", timeout=5)
            if response.status_code == 200:
                data = response.json()
                suts = data.get("suts", [])
                online = len([s for s in suts if s.get("status") == "online"])
                paired = len([s for s in suts if s.get("is_paired")])
                return {
                    "total_devices": len(suts),
                    "online_devices": online,
                    "offline_devices": len(suts) - online,
                    "paired_devices": paired
                }
            return {"total_devices": 0, "online_devices": 0, "offline_devices": 0, "paired_devices": 0}
        except Exception as e:
            logger.error(f"Failed to get device stats: {e}")
            return {"total_devices": 0, "online_devices": 0, "offline_devices": 0, "paired_devices": 0}

    def get_suts_sync(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all SUTs from discovery service (sync version for Flask)."""
        import requests
        params = {"status": status} if status else {}
        try:
            response = requests.get(f"{self.discovery_url}/api/suts", params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json().get("suts", [])
        except Exception as e:
            logger.error(f"Failed to get SUTs from Discovery Service: {e}")
            return []

    def get_sut_by_ip_sync(self, ip: str) -> Optional[Dict[str, Any]]:
        """Find SUT by IP address (sync version for Flask)."""
        suts = self.get_suts_sync()
        return next((s for s in suts if s.get("ip") == ip), None)


# Global client instance
_discovery_client: Optional[DiscoveryServiceClient] = None


def get_discovery_client(discovery_url: str = "http://localhost:5001") -> DiscoveryServiceClient:
    """Get the global discovery client instance."""
    global _discovery_client
    if _discovery_client is None:
        _discovery_client = DiscoveryServiceClient(discovery_url=discovery_url)
    return _discovery_client


def set_discovery_client(client: DiscoveryServiceClient) -> None:
    """Set the global discovery client instance."""
    global _discovery_client
    _discovery_client = client
