"""
WebSocket Connection Manager for SUT Connections.
Tracks connected SUTs and provides instant online/offline detection.
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional, Set, Callable, Any, List
from fastapi import WebSocket
import logging

from .events import event_bus, EventType

logger = logging.getLogger(__name__)


class SUTConnection:
    """Represents a single connected SUT."""

    def __init__(self, sut_id: str, websocket: WebSocket, info: Dict[str, Any]):
        self.sut_id = sut_id
        self.websocket = websocket
        self.info = info
        self.connected_at = datetime.utcnow()
        self.last_seen = datetime.utcnow()
        self.status = "online"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "sut_id": self.sut_id,
            "ip": self.info.get("ip"),
            "hostname": self.info.get("hostname"),
            "cpu_model": self.info.get("cpu_model"),
            "display_name": self.info.get("display_name"),
            "capabilities": self.info.get("capabilities", []),
            "status": self.status,
            "connected_at": self.connected_at.isoformat(),
            "last_seen": self.last_seen.isoformat()
        }

    def update_last_seen(self):
        """Update last seen timestamp."""
        self.last_seen = datetime.utcnow()

    def update_info(self, key: str, value: Any):
        """Update a specific info field."""
        self.info[key] = value


class WebSocketManager:
    """
    Manages WebSocket connections from SUTs.

    Usage:
        manager = WebSocketManager()
        await manager.connect(sut_id, websocket, info)
        await manager.send_command(sut_id, {"type": "apply_preset", ...})
        await manager.broadcast({"type": "status_request"})
    """

    def __init__(self):
        self._connections: Dict[str, SUTConnection] = {}
        self._event_handlers: Dict[str, Set[Callable]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, sut_id: str, websocket: WebSocket, info: Dict[str, Any]) -> SUTConnection:
        """
        Register a new SUT connection.
        If SUT already connected, closes old connection first.
        """
        async with self._lock:
            # Close existing connection if any
            if sut_id in self._connections:
                old_conn = self._connections[sut_id]
                try:
                    await old_conn.websocket.close(code=1000, reason="New connection")
                except:
                    pass
                logger.info(f"Replaced existing connection for {sut_id}")

            # Create new connection
            connection = SUTConnection(sut_id, websocket, info)
            self._connections[sut_id] = connection

            logger.info(f"[ONLINE] SUT {sut_id} connected from {info.get('ip')}")

            # Emit event
            event_bus.emit(EventType.WS_CONNECTED, connection.to_dict())

            return connection

    async def disconnect(self, sut_id: str):
        """Handle SUT disconnection."""
        async with self._lock:
            if sut_id in self._connections:
                conn = self._connections.pop(sut_id)
                conn.status = "offline"

                logger.info(f"[OFFLINE] SUT {sut_id} disconnected")

                # Emit event
                event_bus.emit(EventType.WS_DISCONNECTED, {"sut_id": sut_id})

    def is_connected(self, sut_id: str) -> bool:
        """Check if SUT is currently connected."""
        return sut_id in self._connections

    def get_connection(self, sut_id: str) -> Optional[SUTConnection]:
        """Get connection for specific SUT."""
        return self._connections.get(sut_id)

    def get_all_connections(self) -> List[Dict[str, Any]]:
        """Get all connected SUTs as list of dicts."""
        return [conn.to_dict() for conn in self._connections.values()]

    def get_online_sut_ids(self) -> List[str]:
        """Get list of online SUT IDs."""
        return list(self._connections.keys())

    @property
    def online_count(self) -> int:
        """Number of connected SUTs."""
        return len(self._connections)

    def set_display_name(self, sut_id: str, display_name: str) -> bool:
        """Set display name for a connected SUT."""
        conn = self._connections.get(sut_id)
        if conn:
            conn.update_info("display_name", display_name)
            return True
        return False

    async def send_command(self, sut_id: str, command: Dict[str, Any]) -> bool:
        """
        Send command to specific SUT.
        Returns True if sent successfully, False if SUT not connected.
        """
        conn = self._connections.get(sut_id)
        if not conn:
            logger.warning(f"Cannot send to {sut_id}: not connected")
            return False

        try:
            await conn.websocket.send_json(command)
            conn.update_last_seen()
            logger.debug(f"Sent to {sut_id}: {command.get('type')}")
            return True
        except Exception as e:
            logger.error(f"Send to {sut_id} failed: {e}")
            await self.disconnect(sut_id)
            return False

    async def broadcast(
        self,
        command: Dict[str, Any],
        sut_ids: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Broadcast command to multiple SUTs.

        Args:
            command: Command to send
            sut_ids: List of SUT IDs to target (None = all connected)

        Returns:
            Dict mapping sut_id to success boolean
        """
        targets = sut_ids if sut_ids else list(self._connections.keys())
        results = {}

        for sut_id in targets:
            results[sut_id] = await self.send_command(sut_id, command)

        success_count = sum(1 for v in results.values() if v)
        logger.info(f"Broadcast '{command.get('type')}' to {success_count}/{len(targets)} SUTs")

        return results


# Global WebSocket manager instance
_ws_manager: Optional[WebSocketManager] = None


def get_ws_manager() -> WebSocketManager:
    """Get singleton WebSocket manager instance."""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager
