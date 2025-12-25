"""
Queue Service - OmniParser request queue middleware with terminal dashboard.

This service queues OmniParser requests from multiple SUTs and forwards them
sequentially to prevent request denial when SUTs send requests simultaneously.
"""

from .main import main, app

__version__ = "1.0.0"
__all__ = ["main", "app"]
