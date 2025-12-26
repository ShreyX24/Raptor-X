"""
UDP Discovery for SUT Client
Listens for Master UDP broadcasts to discover Master server
"""

import asyncio
import socket
import json
import threading
from typing import Optional, Dict, Any, Callable
import logging

logger = logging.getLogger(__name__)


class UDPDiscovery:
    """
    Listens for Master UDP broadcasts.

    Usage:
        discovery = UDPDiscovery(udp_port=9999)
        master_info = await discovery.listen_for_master(timeout=10.0)
        # master_info = {"ip": "192.168.1.10", "ws_port": 8000, ...}
    """

    def __init__(self, udp_port: int = 9999):
        self.udp_port = udp_port

    async def listen_for_master(self, timeout: float = 10.0) -> Dict[str, Any]:
        """
        Listen for Master UDP broadcast.

        Args:
            timeout: Maximum time to wait for broadcast

        Returns:
            Master info dict with ip, ws_port, etc.

        Raises:
            TimeoutError: If no Master found within timeout
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', self.udp_port))
        sock.setblocking(False)

        loop = asyncio.get_running_loop()

        logger.info(f"Listening for Master broadcast on UDP:{self.udp_port}...")

        try:
            end_time = loop.time() + timeout

            while loop.time() < end_time:
                try:
                    # Try to receive with short timeout
                    data = await asyncio.wait_for(
                        loop.sock_recv(sock, 1024),
                        timeout=0.5
                    )

                    # Parse message
                    message = json.loads(data.decode('utf-8'))

                    if message.get("type") == "MASTER_ANNOUNCE":
                        logger.info(f"Discovered Master at {message['ip']}:{message['ws_port']}")
                        return message

                except asyncio.TimeoutError:
                    continue
                except json.JSONDecodeError:
                    continue

            raise TimeoutError(f"No Master found within {timeout} seconds")

        finally:
            sock.close()

    async def listen_continuous(
        self,
        callback: Callable[[Dict[str, Any]], None],
        stop_event: Optional[asyncio.Event] = None
    ):
        """
        Continuously listen for Master broadcasts.
        Useful for detecting Master changes or reconnection.

        Args:
            callback: Function to call when Master is discovered
            stop_event: Event to signal stop
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', self.udp_port))
        sock.setblocking(False)

        loop = asyncio.get_running_loop()
        stop = stop_event or asyncio.Event()

        try:
            while not stop.is_set():
                try:
                    data = await asyncio.wait_for(
                        loop.sock_recv(sock, 1024),
                        timeout=1.0
                    )

                    message = json.loads(data.decode('utf-8'))

                    if message.get("type") == "MASTER_ANNOUNCE":
                        if asyncio.iscoroutinefunction(callback):
                            await callback(message)
                        else:
                            callback(message)

                except asyncio.TimeoutError:
                    continue
                except json.JSONDecodeError:
                    continue
        finally:
            sock.close()


class DiscoveryThread(threading.Thread):
    """
    Thread wrapper for UDP discovery.
    Useful when running alongside synchronous Flask app.
    """

    def __init__(
        self,
        udp_port: int = 9999,
        on_master_found: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        super().__init__(daemon=True)
        self.udp_port = udp_port
        self.on_master_found = on_master_found
        self.master_info: Optional[Dict[str, Any]] = None
        self.running = True
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def run(self):
        """Thread main loop"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._discovery_loop())
        except Exception as e:
            logger.error(f"Discovery thread error: {e}")
        finally:
            self._loop.close()

    async def _discovery_loop(self):
        """Async discovery loop"""
        discovery = UDPDiscovery(self.udp_port)

        while self.running:
            try:
                # Listen for master with 30 second timeout
                master_info = await discovery.listen_for_master(timeout=30.0)
                self.master_info = master_info

                if self.on_master_found:
                    self.on_master_found(master_info)

                # After finding master, continue listening for changes
                # with shorter intervals
                await asyncio.sleep(5)

            except TimeoutError:
                logger.debug("No Master broadcast received, retrying...")
            except Exception as e:
                logger.error(f"Discovery error: {e}")
                await asyncio.sleep(5)

    def stop(self):
        """Stop the discovery thread"""
        self.running = False
