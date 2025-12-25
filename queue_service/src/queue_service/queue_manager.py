"""
Queue Manager - Core queue logic for OmniParser requests.

Queues requests and forwards them sequentially to OmniParser server.
Tracks job history and statistics for dashboard monitoring.
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import uuid

import httpx
from pydantic import BaseModel

from .config import get_config

logger = logging.getLogger(__name__)


class ParseRequest(BaseModel):
    """OmniParser parse request model."""
    base64_image: str
    box_threshold: float = 0.05
    iou_threshold: float = 0.1
    use_paddleocr: bool = True


@dataclass
class JobRecord:
    """Record of a processed job for history."""
    job_id: str
    timestamp: datetime
    status: str  # "success", "failed", "timeout"
    processing_time: float
    queue_wait_time: float
    error: Optional[str] = None
    image_size: int = 0  # Base64 image size in bytes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "processing_time": round(self.processing_time, 3),
            "queue_wait_time": round(self.queue_wait_time, 3),
            "error": self.error,
            "image_size": self.image_size,
        }


@dataclass
class QueuedRequest:
    """Represents a queued request with its metadata."""
    request_id: str
    payload: Dict[str, Any]
    enqueued_at: datetime = field(default_factory=datetime.now)
    response_future: asyncio.Future = field(default_factory=asyncio.Future)

    @property
    def queue_wait_time(self) -> float:
        """Time spent waiting in queue."""
        return (datetime.now() - self.enqueued_at).total_seconds()


@dataclass
class QueueStats:
    """Current queue statistics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_requests: int = 0
    current_queue_size: int = 0
    worker_running: bool = False
    avg_processing_time: float = 0.0
    avg_queue_wait_time: float = 0.0
    requests_per_minute: float = 0.0
    uptime_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "timeout_requests": self.timeout_requests,
            "current_queue_size": self.current_queue_size,
            "worker_running": self.worker_running,
            "avg_processing_time": round(self.avg_processing_time, 3),
            "avg_queue_wait_time": round(self.avg_queue_wait_time, 3),
            "requests_per_minute": round(self.requests_per_minute, 2),
            "uptime_seconds": round(self.uptime_seconds, 1),
        }


class QueueManager:
    """Manages the request queue and forwards requests to OmniParser server."""

    def __init__(self, target_url: str = None, timeout: int = None):
        config = get_config()
        self.target_url = target_url or config.omniparser_url
        self.timeout = timeout or config.request_timeout
        self.max_queue_size = config.max_queue_size

        self.request_queue: asyncio.Queue = None
        self.worker_task: Optional[asyncio.Task] = None

        # Statistics tracking
        self._stats = QueueStats()
        self._start_time = datetime.now()
        self._processing_times: deque = deque(maxlen=100)
        self._queue_wait_times: deque = deque(maxlen=100)
        self._request_timestamps: deque = deque(maxlen=100)

        # Job history
        self._job_history: deque = deque(maxlen=config.job_history_size)

        # Queue depth history for graphing
        self._queue_depth_history: deque = deque(maxlen=config.stats_history_size)

        logger.info(f"QueueManager initialized with target: {self.target_url}")

    async def start(self):
        """Start the queue manager and worker."""
        if self.request_queue is None:
            self.request_queue = asyncio.Queue(maxsize=self.max_queue_size)

        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._worker())
            self._stats.worker_running = True
            logger.info("Queue worker started")

    async def stop(self):
        """Stop the queue manager and worker."""
        if self.worker_task and not self.worker_task.done():
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            self._stats.worker_running = False
            logger.info("Queue worker stopped")

    async def _worker(self):
        """Background worker that processes requests from the queue one at a time."""
        logger.info("Worker thread started, processing requests sequentially")

        while True:
            try:
                # Get next request from queue
                queued_request: QueuedRequest = await self.request_queue.get()
                self._update_queue_depth()

                queue_wait_time = queued_request.queue_wait_time
                self._queue_wait_times.append(queue_wait_time)

                logger.info(
                    f"Processing request {queued_request.request_id} "
                    f"(waited {queue_wait_time:.2f}s, queue size: {self.request_queue.qsize()})"
                )

                # Process the request
                start_time = time.time()
                job_record = JobRecord(
                    job_id=queued_request.request_id,
                    timestamp=datetime.now(),
                    status="pending",
                    processing_time=0,
                    queue_wait_time=queue_wait_time,
                    image_size=len(queued_request.payload.get("base64_image", "")),
                )

                try:
                    response_data = await self._forward_to_omniparser(queued_request)
                    queued_request.response_future.set_result(response_data)

                    processing_time = time.time() - start_time
                    self._processing_times.append(processing_time)
                    self._request_timestamps.append(datetime.now())

                    self._stats.successful_requests += 1
                    job_record.status = "success"
                    job_record.processing_time = processing_time

                    logger.info(f"Request {queued_request.request_id} completed in {processing_time:.2f}s")

                except asyncio.TimeoutError:
                    processing_time = time.time() - start_time
                    self._stats.timeout_requests += 1
                    job_record.status = "timeout"
                    job_record.processing_time = processing_time
                    job_record.error = f"Timeout after {self.timeout}s"

                    error = Exception(f"Request timed out after {self.timeout}s")
                    queued_request.response_future.set_exception(error)
                    logger.error(f"Request {queued_request.request_id} timed out")

                except Exception as e:
                    processing_time = time.time() - start_time
                    self._stats.failed_requests += 1
                    job_record.status = "failed"
                    job_record.processing_time = processing_time
                    job_record.error = str(e)

                    queued_request.response_future.set_exception(e)
                    logger.error(f"Request {queued_request.request_id} failed: {e}")

                finally:
                    self._job_history.appendleft(job_record)
                    self.request_queue.task_done()
                    self._update_stats()

            except asyncio.CancelledError:
                logger.info("Worker cancelled, shutting down")
                self._stats.worker_running = False
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(1)  # Avoid tight loop on errors

    async def _forward_to_omniparser(self, queued_request: QueuedRequest) -> Dict[str, Any]:
        """Forward a request to the OmniParser server."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.target_url}/parse/",
                json=queued_request.payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                raise Exception(f"OmniParser error {response.status_code}: {response.text}")

            return response.json()

    async def enqueue_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Add a request to the queue and wait for its result."""
        if self.request_queue is None:
            await self.start()

        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]

        # Check queue size
        current_size = self.request_queue.qsize()
        if current_size >= self.max_queue_size:
            logger.warning(f"Queue full ({current_size}/{self.max_queue_size}), rejecting request")
            raise Exception("Queue is full, please retry later")

        # Create queued request
        queued_request = QueuedRequest(
            request_id=request_id,
            payload=payload,
        )

        self._stats.total_requests += 1

        # Add to queue
        await self.request_queue.put(queued_request)
        self._update_queue_depth()

        queue_position = self.request_queue.qsize()
        logger.info(f"Request {request_id} queued at position {queue_position}")

        # Wait for result
        return await queued_request.response_future

    def _update_queue_depth(self):
        """Update queue depth history."""
        self._queue_depth_history.append({
            "timestamp": datetime.now().isoformat(),
            "depth": self.request_queue.qsize() if self.request_queue else 0,
        })
        self._stats.current_queue_size = self.request_queue.qsize() if self.request_queue else 0

    def _update_stats(self):
        """Update running statistics."""
        # Average processing time
        if self._processing_times:
            self._stats.avg_processing_time = sum(self._processing_times) / len(self._processing_times)

        # Average queue wait time
        if self._queue_wait_times:
            self._stats.avg_queue_wait_time = sum(self._queue_wait_times) / len(self._queue_wait_times)

        # Requests per minute (from last minute's timestamps)
        now = datetime.now()
        recent = [t for t in self._request_timestamps if (now - t).total_seconds() < 60]
        self._stats.requests_per_minute = len(recent)

        # Uptime
        self._stats.uptime_seconds = (datetime.now() - self._start_time).total_seconds()

    def get_stats(self) -> QueueStats:
        """Get current queue statistics."""
        self._update_stats()
        return self._stats

    def get_job_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent job history."""
        return [job.to_dict() for job in list(self._job_history)[:limit]]

    def get_queue_depth_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get queue depth history for graphing."""
        return list(self._queue_depth_history)[-limit:]

    async def health_check(self) -> Dict[str, Any]:
        """Check health of the OmniParser server."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.target_url}/probe")
                response.raise_for_status()
                return {
                    "status": "healthy",
                    "omniparser_server": self.target_url,
                    "omniparser_response": response.json(),
                }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "omniparser_server": self.target_url,
                "error": str(e),
            }


# Global queue manager instance
_queue_manager: Optional[QueueManager] = None


def get_queue_manager() -> QueueManager:
    """Get the global queue manager instance."""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = QueueManager()
    return _queue_manager


async def start_queue_manager():
    """Start the global queue manager."""
    manager = get_queue_manager()
    await manager.start()


async def stop_queue_manager():
    """Stop the global queue manager."""
    global _queue_manager
    if _queue_manager is not None:
        await _queue_manager.stop()
