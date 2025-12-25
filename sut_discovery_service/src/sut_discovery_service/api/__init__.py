"""
SUT Discovery Service API endpoints.
"""

from .suts import router as suts_router
from .proxy import router as proxy_router
from .health import router as health_router

__all__ = ["suts_router", "proxy_router", "health_router"]
