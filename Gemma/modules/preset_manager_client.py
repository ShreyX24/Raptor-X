# -*- coding: utf-8 -*-
"""
Client for Preset-Manager service.
Handles all preset-related operations through Preset-Manager API.
"""

import logging
from typing import Dict, Any, Optional, List

import httpx

logger = logging.getLogger(__name__)


class PresetManagerClient:
    """
    Client for communicating with Preset-Manager service.

    Handles preset storage, retrieval, and management operations.
    """

    def __init__(
        self,
        preset_manager_url: str = "http://localhost:5002",
        timeout: float = 30.0
    ):
        self.preset_manager_url = preset_manager_url.rstrip("/")
        self.timeout = timeout
        self._available = None

    async def get_games(self) -> List[Dict[str, Any]]:
        """Get all games with presets."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.preset_manager_url}/api/games")
                response.raise_for_status()
                return response.json().get("games", [])
        except Exception as e:
            logger.error(f"Failed to get games from Preset-Manager: {e}")
            return []

    async def get_game(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Get specific game details."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.preset_manager_url}/api/games/{game_id}")
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get game {game_id}: {e}")
            return None

    async def get_presets(self, game_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all presets, optionally filtered by game."""
        try:
            params = {"game_id": game_id} if game_id else {}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.preset_manager_url}/api/presets",
                    params=params
                )
                response.raise_for_status()
                return response.json().get("presets", [])
        except Exception as e:
            logger.error(f"Failed to get presets: {e}")
            return []

    async def get_preset(self, preset_id: str) -> Optional[Dict[str, Any]]:
        """Get specific preset by ID."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.preset_manager_url}/api/presets/{preset_id}")
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get preset {preset_id}: {e}")
            return None

    async def create_preset(self, preset_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new preset."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.preset_manager_url}/api/presets",
                    json=preset_data
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to create preset: {e}")
            return None

    async def update_preset(self, preset_id: str, preset_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing preset."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.put(
                    f"{self.preset_manager_url}/api/presets/{preset_id}",
                    json=preset_data
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to update preset {preset_id}: {e}")
            return None

    async def delete_preset(self, preset_id: str) -> bool:
        """Delete a preset."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(f"{self.preset_manager_url}/api/presets/{preset_id}")
                return response.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Failed to delete preset {preset_id}: {e}")
            return False

    async def get_backups(self, game_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all backups, optionally filtered by game."""
        try:
            params = {"game_id": game_id} if game_id else {}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.preset_manager_url}/api/backups",
                    params=params
                )
                response.raise_for_status()
                return response.json().get("backups", [])
        except Exception as e:
            logger.error(f"Failed to get backups: {e}")
            return []

    async def create_backup(self, sut_id: str, game_id: str) -> Optional[Dict[str, Any]]:
        """Create a backup of current SUT settings."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.preset_manager_url}/api/backups",
                    json={"sut_id": sut_id, "game_id": game_id}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None

    async def restore_backup(self, backup_id: str, sut_id: str) -> Dict[str, Any]:
        """Restore a backup to a SUT."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.preset_manager_url}/api/backups/{backup_id}/restore",
                    json={"sut_id": sut_id}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to restore backup {backup_id}: {e}")
            return {"success": False, "error": str(e)}

    async def sync_preset_to_suts(
        self,
        preset_id: str,
        sut_ids: List[str]
    ) -> Dict[str, Any]:
        """Sync a preset to multiple SUTs."""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.preset_manager_url}/api/sync/preset",
                    json={"preset_id": preset_id, "sut_ids": sut_ids}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to sync preset {preset_id}: {e}")
            return {"success": False, "error": str(e)}

    async def apply_presets(
        self,
        sut_ips: List[str],
        games: List[str],
        resolution: str = "1920x1080",
        graphics: str = "high"
    ) -> Dict[str, Any]:
        """
        Apply presets to SUTs before Gemma automation.

        Args:
            sut_ips: List of SUT IP addresses
            games: List of game short names (e.g., ["cyberpunk-2077", "cs2"])
            resolution: Target resolution (e.g., "1920x1080", "2560x1440")
            graphics: Graphics quality level (e.g., "low", "medium", "high", "ultra")

        Returns:
            Dict with keys: successful, failed, skipped (lists), summary (dict)
        """
        try:
            payload = {
                "sut_ips": sut_ips,
                "games": games,
                "preset": {
                    "resolution": resolution,
                    "graphics": graphics
                }
            }

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.preset_manager_url}/api/sync/gemma-presets",
                    json=payload
                )
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"Failed to apply presets: {e}")
            return {
                "successful": [],
                "failed": [],
                "skipped": [],
                "summary": {"error": str(e)},
                "error": str(e)
            }

    def apply_presets_sync(
        self,
        sut_ips: List[str],
        games: List[str],
        resolution: str = "1920x1080",
        graphics: str = "high"
    ) -> Dict[str, Any]:
        """
        Apply presets to SUTs before Gemma automation (sync version for Flask).

        Args:
            sut_ips: List of SUT IP addresses
            games: List of game short names
            resolution: Target resolution
            graphics: Graphics quality level

        Returns:
            Dict with keys: successful, failed, skipped (lists), summary (dict)
        """
        import requests
        try:
            payload = {
                "sut_ips": sut_ips,
                "games": games,
                "preset": {
                    "resolution": resolution,
                    "graphics": graphics
                }
            }

            response = requests.post(
                f"{self.preset_manager_url}/api/sync/gemma-presets",
                json=payload,
                timeout=120.0
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to apply presets (sync): {e}")
            return {
                "successful": [],
                "failed": [],
                "skipped": [],
                "summary": {"error": str(e)},
                "error": str(e)
            }

    def is_available(self) -> bool:
        """Check if Preset-Manager is available (sync version for startup check)."""
        import requests
        try:
            response = requests.get(f"{self.preset_manager_url}/health", timeout=3)
            self._available = response.status_code == 200
            return self._available
        except Exception:
            self._available = False
            return False

    async def is_available_async(self) -> bool:
        """Check if Preset-Manager is available (async version)."""
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{self.preset_manager_url}/health")
                self._available = response.status_code == 200
                return self._available
        except Exception:
            self._available = False
            return False

    async def wait_for_service(self, max_retries: int = 10, delay: float = 1.0) -> bool:
        """Wait for Preset-Manager to become available with exponential backoff."""
        import asyncio

        current_delay = delay
        for attempt in range(max_retries):
            if await self.is_available_async():
                logger.info(f"Preset-Manager available after {attempt + 1} attempts")
                return True

            logger.warning(
                f"Preset-Manager not available, attempt {attempt + 1}/{max_retries}, "
                f"retrying in {current_delay:.1f}s..."
            )
            await asyncio.sleep(current_delay)
            current_delay = min(current_delay * 2, 30)

        logger.error(f"Preset-Manager not available after {max_retries} attempts")
        return False

    def get_status(self) -> Dict[str, Any]:
        """Get Preset-Manager status (sync version)."""
        import requests
        try:
            response = requests.get(f"{self.preset_manager_url}/health", timeout=5)
            if response.status_code == 200:
                return {
                    "status": "online",
                    "url": self.preset_manager_url
                }
            return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "offline", "error": str(e)}


# Global client instance
_preset_manager_client: Optional[PresetManagerClient] = None


def get_preset_manager_client(
    preset_manager_url: str = "http://localhost:5002"
) -> PresetManagerClient:
    """Get the global preset manager client instance."""
    global _preset_manager_client
    if _preset_manager_client is None:
        _preset_manager_client = PresetManagerClient(preset_manager_url=preset_manager_url)
    return _preset_manager_client


def set_preset_manager_client(client: PresetManagerClient) -> None:
    """Set the global preset manager client instance."""
    global _preset_manager_client
    _preset_manager_client = client
