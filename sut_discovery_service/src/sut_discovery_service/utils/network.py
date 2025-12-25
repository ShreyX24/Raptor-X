"""
Network utilities for SUT Discovery Service.
"""

import logging
import socket
import ipaddress
from typing import List

logger = logging.getLogger(__name__)


class NetworkDiscovery:
    """Network discovery utilities."""

    @staticmethod
    def get_host_ip() -> str:
        """Get the primary host IP address."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                host_ip = s.getsockname()[0]
                logger.info(f"Detected host IP: {host_ip}")
                return host_ip
        except Exception as e:
            logger.error(f"Error detecting host IP: {e}")
            return "127.0.0.1"

    @staticmethod
    def is_ip_reachable(ip: str, port: int, timeout: float = 1.0) -> bool:
        """Quick check if an IP:port is reachable."""
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except (socket.error, OSError):
            return False

    @staticmethod
    def get_network_info() -> dict:
        """Get basic network information."""
        return {
            "host_ip": NetworkDiscovery.get_host_ip(),
        }
