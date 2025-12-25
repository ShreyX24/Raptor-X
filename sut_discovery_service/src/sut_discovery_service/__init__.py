"""
SUT Discovery Service - Central gateway for all SUT communication.

This service handles:
- UDP broadcast for SUT discovery
- WebSocket connections from SUT clients
- Device registry and pairing
- Proxy for all SUT API calls
"""

from .main import main, app

__version__ = "1.0.0"
__all__ = ["main", "app"]
