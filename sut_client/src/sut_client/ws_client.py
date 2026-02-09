"""
WebSocket Client for SUT
Maintains persistent connection to Master server
"""

import asyncio
import socket
import json
import platform
import threading
from datetime import datetime
from typing import Optional, Dict, Any, Callable
import logging

try:
    import websockets
    from websockets.exceptions import ConnectionClosed
except ImportError:
    websockets = None
    ConnectionClosed = Exception

from .config import get_settings
from .hardware import get_cpu_model
from .system import rename_computer

logger = logging.getLogger(__name__)


class WebSocketClient:
    """
    WebSocket client for connecting to Master server.

    Usage:
        client = WebSocketClient(
            sut_id="SUT-001",
            master_ip="192.168.1.10",
            master_port=5000,
            on_command=handle_command
        )
        await client.run()
    """

    def __init__(
        self,
        sut_id: str,
        master_ip: str,
        master_port: int,
        on_command: Optional[Callable[[Dict[str, Any]], Any]] = None
    ):
        if websockets is None:
            raise ImportError("websockets package required: pip install websockets")

        self.sut_id = sut_id
        self.master_ip = master_ip
        self.master_port = master_port
        self.on_command = on_command

        self.websocket = None
        self.connected = False
        self.running = True

        # Reconnection settings
        self.reconnect_base_delay = 1.0
        self.reconnect_max_delay = 30.0
        self.reconnect_attempts = 0

    def _get_local_ip(self) -> str:
        """Get local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def _get_registration_info(self) -> Dict[str, Any]:
        """Build registration payload with SSH key"""
        settings = get_settings()

        # Lazy-load SSH key info for Master registration (only when needed)
        ssh_public_key = None
        ssh_fingerprint = None
        try:
            from .ssh_key_manager import get_key_manager
            ssh_manager = get_key_manager()
            ssh_manager.ensure_key_exists()
            ssh_public_key = ssh_manager.get_public_key()
            ssh_fingerprint = ssh_manager.get_key_fingerprint()
        except Exception as e:
            logger.warning(f"SSH key setup skipped: {e}")

        return {
            "type": "register",
            "sut_id": self.sut_id,
            "ip": self._get_local_ip(),
            "hostname": settings.hostname,
            "cpu_model": get_cpu_model(),
            "platform": platform.system(),
            "platform_version": platform.version(),
            "capabilities": [
                "preset_sync",
                "config_backup",
                "config_restore",
                "basic_clicks",
                "advanced_clicks",
                "hotkeys",
                "text_input",
                "pc_rename"
            ],
            "timestamp": datetime.utcnow().isoformat(),
            # SSH key for Master authentication (for updates)
            "ssh_public_key": ssh_public_key,
            "ssh_key_fingerprint": ssh_fingerprint,
        }

    def _get_reconnect_delay(self) -> float:
        """Calculate reconnection delay with exponential backoff"""
        import random
        delay = min(
            self.reconnect_base_delay * (2 ** self.reconnect_attempts),
            self.reconnect_max_delay
        )
        jitter = random.uniform(0, delay * 0.3)
        self.reconnect_attempts += 1
        total = delay + jitter
        logger.debug(f"[WS] Reconnect delay: {total:.1f}s (attempt #{self.reconnect_attempts}, base={delay:.1f}s, jitter={jitter:.1f}s)")
        return total

    async def connect_and_run(self):
        """Connect to Master and maintain connection"""
        uri = f"ws://{self.master_ip}:{self.master_port}/api/ws/sut/{self.sut_id}"

        logger.info(f"Connecting to Master: {uri}")

        while self.running:
            try:
                async with websockets.connect(
                    uri,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5
                ) as ws:
                    self.websocket = ws
                    self.connected = True
                    self.reconnect_attempts = 0  # Reset on successful connect

                    # Send registration
                    reg_info = self._get_registration_info()
                    logger.debug(f"[WS] --> Sending registration: type={reg_info.get('type')}, sut_id={reg_info.get('sut_id')}, ip={reg_info.get('ip')}")
                    await ws.send(json.dumps(reg_info))

                    # Wait for acknowledgment
                    raw_response = await ws.recv()
                    response = json.loads(raw_response)
                    logger.debug(f"[WS] <-- Registration response: type={response.get('type')}, keys={list(response.keys())}")

                    if response.get("type") != "register_ack":
                        raise Exception(f"Registration failed: {response}")

                    logger.info(f"[CONNECTED] Registered with Master at {self.master_ip}:{self.master_port}")

                    # Handle bidirectional SSH: Install Master's public key if provided
                    await self._handle_master_key_exchange(ws, response)

                    # Message loop
                    async for message in ws:
                        parsed = json.loads(message)
                        logger.debug(f"[WS] <-- Received message: type={parsed.get('type')}, keys={list(parsed.keys())}")
                        await self._handle_message(parsed)

            except ConnectionClosed:
                self.connected = False
                if self.running:
                    delay = self._get_reconnect_delay()
                    logger.warning(f"Connection closed, reconnecting in {delay:.1f}s...")
                    await asyncio.sleep(delay)

            except Exception as e:
                self.connected = False
                if self.running:
                    delay = self._get_reconnect_delay()
                    logger.error(f"Error: {e}, reconnecting in {delay:.1f}s...")
                    await asyncio.sleep(delay)

    async def _handle_master_key_exchange(self, ws, response: Dict[str, Any]):
        """
        Handle bidirectional SSH key exchange.

        If Master sends its public key, install it in authorized_keys
        so Master can SSH into this SUT for trace pulling, etc.
        """
        master_public_key = response.get("master_public_key")
        master_fingerprint = response.get("master_fingerprint")
        re_exchange = response.get("re_exchange", False)

        if not master_public_key:
            logger.debug("No master public key in register_ack, skipping key exchange")
            return

        logger.info(f"Master key exchange: fingerprint={master_fingerprint}, re_exchange={re_exchange}")

        try:
            from .ssh_setup import get_ssh_setup
            ssh_setup = get_ssh_setup()

            # Install Master's public key
            success, msg = ssh_setup.add_authorized_key(master_public_key)

            if success:
                logger.info(f"Installed Master's SSH key: {msg}")
                # Notify Master that key was installed
                await ws.send(json.dumps({
                    "type": "master_key_installed",
                    "success": True,
                    "message": msg,
                }))
            else:
                logger.warning(f"Failed to install Master's SSH key: {msg}")
                await ws.send(json.dumps({
                    "type": "master_key_installed",
                    "success": False,
                    "error": msg,
                }))

        except Exception as e:
            logger.error(f"Error during master key exchange: {e}")
            await ws.send(json.dumps({
                "type": "master_key_installed",
                "success": False,
                "error": str(e),
            }))

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming message from Master"""
        msg_type = message.get("type")
        logger.debug(f"[WS] Handling message type: {msg_type}")

        if msg_type == "ping":
            # Respond to heartbeat
            logger.debug("[WS] --> Sending pong")
            await self.websocket.send(json.dumps({"type": "pong"}))

        elif msg_type == "status_request":
            # Send status
            logger.debug("[WS] --> Sending status response")
            await self._send_status()

        elif msg_type == "update_available":
            # Handle update notification from Master
            await self._handle_update_available(message)

        elif msg_type == "install_master_key":
            # Master requesting key re-installation (e.g., after IP change)
            await self._handle_master_key_exchange(self.websocket, message)

        elif msg_type == "rename_pc":
            # Handle PC rename command
            new_name = message.get("new_name")
            if not new_name:
                await self._send_result(msg_type, {"error": "new_name is required"})
            else:
                logger.info(f"Received PC rename command: {new_name}")
                result = rename_computer(new_name)
                await self._send_result(msg_type, result)

        elif self.on_command:
            # Custom command handler
            try:
                result = self.on_command(message)
                if asyncio.iscoroutine(result):
                    result = await result
                if result:
                    await self._send_result(msg_type, result)
            except Exception as e:
                logger.error(f"Command handler error: {e}")
                await self._send_result(msg_type, {"error": str(e)})

        else:
            logger.warning(f"Unhandled message type: {msg_type}")

    async def _handle_update_available(self, message: Dict[str, Any]):
        """Handle update available notification from Master"""
        new_version = message.get("version", "unknown")
        master_ip = message.get("master_ip", self.master_ip)

        logger.info(f"Update available: {new_version} from {master_ip}")

        # Notify the update handler
        try:
            from .update_handler import get_update_handler
            handler = get_update_handler()
            if handler:
                handler.notify_update_available(new_version, master_ip)
            else:
                logger.warning("Update handler not initialized")
        except ImportError:
            logger.warning("Update handler module not available")

    async def _send_status(self):
        """Send status to Master"""
        if self.websocket:
            payload = {
                "type": "status",
                "sut_id": self.sut_id,
                "data": {
                    "status": "ready",
                    "connected": self.connected,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            logger.debug(f"[WS] --> status: connected={self.connected}")
            await self.websocket.send(json.dumps(payload))

    async def _send_result(self, command_type: str, result: Dict[str, Any]):
        """Send command result to Master"""
        if self.websocket:
            payload = {
                "type": "result",
                "sut_id": self.sut_id,
                "command_type": command_type,
                "data": result,
                "timestamp": datetime.utcnow().isoformat()
            }
            logger.debug(f"[WS] --> result for '{command_type}': keys={list(result.keys())}")
            await self.websocket.send(json.dumps(payload))

    def stop(self):
        """Stop the client"""
        logger.debug("[WS] Stop requested, closing connection")
        self.running = False
        self.connected = False


class WebSocketClientThread(threading.Thread):
    """
    Thread wrapper for WebSocket client.
    Runs alongside synchronous Flask app.
    """

    def __init__(
        self,
        sut_id: str,
        master_ip: str,
        master_port: int,
        on_command: Optional[Callable[[Dict[str, Any]], Any]] = None
    ):
        super().__init__(daemon=True)
        self.sut_id = sut_id
        self.master_ip = master_ip
        self.master_port = master_port
        self.on_command = on_command
        self.client: Optional[WebSocketClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def run(self):
        """Thread main loop"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self.client = WebSocketClient(
            sut_id=self.sut_id,
            master_ip=self.master_ip,
            master_port=self.master_port,
            on_command=self.on_command
        )

        try:
            self._loop.run_until_complete(self.client.connect_and_run())
        except Exception as e:
            logger.error(f"WebSocket thread error: {e}")
        finally:
            self._loop.close()

    def stop(self):
        """Stop the WebSocket client"""
        if self.client:
            self.client.stop()

    @property
    def connected(self) -> bool:
        """Check if connected to Master"""
        return self.client.connected if self.client else False

    def update_master(self, master_ip: str, master_port: int):
        """Update Master connection info (for reconnection on Master change)"""
        if self.client:
            self.client.master_ip = master_ip
            self.client.master_port = master_port
