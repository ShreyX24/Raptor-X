"""
Health API endpoints - service health checks.
"""

from fastapi import APIRouter

from ..queue_manager import get_queue_manager
from ..config import get_config

router = APIRouter()


@router.get("/probe")
async def probe():
    """
    Health check endpoint - compatible with OmniparserClient.
    Returns queue service health and OmniParser server health.
    """
    manager = get_queue_manager()
    health_status = await manager.health_check()
    stats = manager.get_stats()

    return {
        "service": "queue-service",
        "version": "1.0.0",
        "queue_service_status": "running",
        "omniparser_status": health_status,
        "stats": stats.to_dict(),
    }


@router.get("/health")
async def health():
    """Basic health check endpoint."""
    manager = get_queue_manager()
    stats = manager.get_stats()

    return {
        "status": "healthy" if stats.worker_running else "degraded",
        "worker_running": stats.worker_running,
        "queue_size": stats.current_queue_size,
        "uptime_seconds": stats.uptime_seconds,
    }


@router.get("/")
async def root():
    """Root endpoint with service information."""
    config = get_config()

    return {
        "service": "Queue Service",
        "version": "1.0.0",
        "description": "OmniParser request queue middleware with terminal dashboard",
        "target_server": config.omniparser_url,
        "endpoints": {
            "parse": "/parse/",
            "health": "/probe",
            "stats": "/stats",
            "jobs": "/jobs",
            "queue_depth": "/queue-depth",
        },
        "dashboard": "Run 'queue-dashboard' for terminal monitoring",
    }
