"""
Stats API endpoints - queue statistics and job history.
"""

from fastapi import APIRouter, Query

from ..queue_manager import get_queue_manager

router = APIRouter()


@router.get("/stats")
async def get_stats():
    """Get current queue statistics and performance metrics."""
    manager = get_queue_manager()
    stats = manager.get_stats()
    return stats.to_dict()


@router.get("/jobs")
async def get_jobs(limit: int = Query(default=20, ge=1, le=100)):
    """
    Get recent job history.

    Args:
        limit: Maximum number of jobs to return (1-100, default 20)

    Returns:
        List of recent job records with timing and status
    """
    manager = get_queue_manager()
    return {
        "jobs": manager.get_job_history(limit=limit),
        "count": len(manager._job_history),
    }


@router.get("/queue-depth")
async def get_queue_depth(limit: int = Query(default=50, ge=1, le=200)):
    """
    Get queue depth history for graphing.

    Args:
        limit: Maximum number of data points to return (1-200, default 50)

    Returns:
        List of queue depth measurements with timestamps
    """
    manager = get_queue_manager()
    return {
        "history": manager.get_queue_depth_history(limit=limit),
        "current_depth": manager._stats.current_queue_size,
    }
