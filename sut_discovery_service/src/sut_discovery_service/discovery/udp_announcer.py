"""
UDP Announcer for SUT Discovery Service.
Broadcasts service presence on UDP for SUTs to discover instantly.
"""

import asyncio
import socket
import json
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class UDPAnnouncer:
    """
    Broadcasts Discovery Service presence on UDP for SUTs to discover.

    Usage:
        announcer = UDPAnnouncer(service_ip="192.168.1.10", ws_port=5001)
        announcer.start()  # Starts background broadcast
        ...
        announcer.stop()   # Stops broadcast
    """

    def __init__(
        self,
        service_ip: str,
        ws_port: int,
        udp_port: int = 9999,
        interval: float = 1.0,
        service_name: str = "sut-discovery-service"
    ):
        self.service_ip = service_ip
        self.ws_port = ws_port
        self.udp_port = udp_port
        self.interval = interval
        self.service_name = service_name

        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._socket: Optional[socket.socket] = None

    def _create_socket(self) -> socket.socket:
        """Create UDP broadcast socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(False)
        return sock

    def _build_message(self) -> bytes:
        """Build broadcast message."""
        return json.dumps({
            "type": "MASTER_ANNOUNCE",
            "service": self.service_name,
            "version": "1.0.0",
            "ip": self.service_ip,
            "ws_port": self.ws_port,
            "api_port": self.ws_port,
            "timestamp": datetime.utcnow().isoformat()
        }).encode('utf-8')

    async def _broadcast_loop(self):
        """Main broadcast loop - runs until stopped."""
        self._socket = self._create_socket()
        logger.info(f"UDP Announcer started - broadcasting on port {self.udp_port}")
        logger.info(f"Service: {self.service_ip}:{self.ws_port}")

        while self.running:
            try:
                message = self._build_message()
                self._socket.sendto(message, ('255.255.255.255', self.udp_port))
                logger.debug("Broadcast sent")
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

            await asyncio.sleep(self.interval)

        self._socket.close()
        self._socket = None
        logger.info("UDP Announcer stopped")

    def start(self):
        """Start broadcasting (creates background task)."""
        if self.running:
            logger.warning("UDP Announcer already running")
            return

        self.running = True
        self._task = asyncio.create_task(self._broadcast_loop())

    def stop(self):
        """Stop broadcasting."""
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()

    @property
    def is_running(self) -> bool:
        return self.running and self._task is not None and not self._task.done()
