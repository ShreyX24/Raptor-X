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
    Returns queue service health and OmniParser server health for all configured servers.
    """
    manager = get_queue_manager()
    server_statuses = await manager.health_check()  # Now returns List of server statuses
    stats = manager.get_stats()

    # Determine overall status - healthy if at least one server is healthy
    healthy_count = sum(1 for s in server_statuses if s.get("status") == "healthy")
    overall_status = "healthy" if healthy_count > 0 else "unhealthy"

    return {
        "service": "queue-service",
        "version": "1.0.0",
        "queue_service_status": "running",
        "omniparser_status": server_statuses,  # List of {url, status, ...}
        "omniparser_healthy_count": healthy_count,
        "omniparser_total_count": len(server_statuses),
        "overall_omniparser_status": overall_status,
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
        "target_servers": config.omniparser_urls,
        "server_count": len(config.omniparser_urls),
        "load_balancing": "round-robin",
        "endpoints": {
            "parse": "/parse/",
            "health": "/probe",
            "stats": "/stats",
            "jobs": "/jobs",
            "queue_depth": "/queue-depth",
        },
        "dashboard": "Run 'queue-dashboard' for terminal monitoring",
    }
