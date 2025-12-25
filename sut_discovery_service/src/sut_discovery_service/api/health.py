"""
Health API endpoints for SUT Discovery Service.
"""

from fastapi import APIRouter

from ..discovery import get_device_registry, get_ws_manager
from ..config import get_config

router = APIRouter()


@router.get("/health")
async def health():
    """Basic health check endpoint."""
    registry = get_device_registry()
    ws_manager = get_ws_manager()
    stats = registry.get_device_stats()

    return {
        "status": "healthy",
        "service": "sut-discovery-service",
        "version": "1.0.0",
        "websocket_connections": ws_manager.online_count,
        "devices": stats,
    }


@router.get("/")
async def root():
    """Root endpoint with service information."""
    config = get_config()
    registry = get_device_registry()
    stats = registry.get_device_stats()

    return {
        "service": "SUT Discovery Service",
        "version": "1.0.0",
        "description": "Central gateway for all SUT communication",
        "port": config.port,
        "udp_port": config.udp_port,
        "devices": stats,
        "endpoints": {
            "suts": "/api/suts",
            "sut_detail": "/api/suts/{id}",
            "pair": "/api/suts/{id}/pair",
            "unpair": "/api/suts/{id}/unpair",
            "discover": "/api/discover",
            "websocket": "/api/ws/sut/{id}",
            "proxy": {
                "games": "/api/suts/{id}/games",
                "screenshot": "/api/suts/{id}/screenshot",
                "action": "/api/suts/{id}/action",
                "launch": "/api/suts/{id}/launch",
                "apply_preset": "/api/suts/{id}/apply-preset",
                "status": "/api/suts/{id}/status",
            }
        },
    }
