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
    """OmniParser parse request model with all OCR configuration options."""
    base64_image: str
    box_threshold: float = 0.05      # YOLO detection confidence threshold
    iou_threshold: float = 0.1       # IOU threshold for overlap removal
    use_paddleocr: bool = True       # True = PaddleOCR, False = EasyOCR
    text_threshold: float = 0.8      # OCR confidence threshold for text detection
    use_local_semantics: bool = True # Use caption model for icon labeling
    scale_img: bool = False          # Scale image before processing
    imgsz: Optional[int] = None      # Image size for YOLO model (None = use original)


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
    num_workers: int = 1
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
            "num_workers": self.num_workers,
            "avg_processing_time": round(self.avg_processing_time, 3),
            "avg_queue_wait_time": round(self.avg_queue_wait_time, 3),
            "requests_per_minute": round(self.requests_per_minute, 2),
            "uptime_seconds": round(self.uptime_seconds, 1),
        }


class QueueManager:
    """Manages the request queue and forwards requests to OmniParser servers.

    Supports multiple OmniParser servers with round-robin load balancing,
    automatic failover for unhealthy servers, and parallel workers.
    """

    def __init__(self, target_urls: List[str] = None, timeout: int = None, num_workers: int = None):
        config = get_config()
        self.target_urls = target_urls or config.omniparser_urls
        self.timeout = timeout or config.request_timeout
        self.max_queue_size = config.max_queue_size

        # Number of workers: 0 = auto (one per OmniParser URL, min 2)
        configured_workers = num_workers if num_workers is not None else config.num_workers
        if configured_workers <= 0:
            self.num_workers = max(len(self.target_urls), 2)
        else:
            self.num_workers = configured_workers

        self.request_queue: asyncio.Queue = None
        self.worker_tasks: List[asyncio.Task] = []  # Multiple workers

        # Round-robin state with lock for thread safety
        self._current_server_index = 0
        self._server_index_lock = asyncio.Lock()
        self._server_health: Dict[str, bool] = {url: True for url in self.target_urls}

        # Statistics tracking
        self._stats = QueueStats(num_workers=self.num_workers)
        self._start_time = datetime.now()
        self._processing_times: deque = deque(maxlen=100)
        self._queue_wait_times: deque = deque(maxlen=100)
        self._request_timestamps: deque = deque(maxlen=100)

        # Job history
        self._job_history: deque = deque(maxlen=config.job_history_size)

        # Queue depth history for graphing
        self._queue_depth_history: deque = deque(maxlen=config.stats_history_size)

        logger.info(f"QueueManager initialized with {len(self.target_urls)} server(s), {self.num_workers} workers: {self.target_urls}")

    async def _get_next_server(self) -> str:
        """Round-robin server selection, skipping unhealthy servers. Thread-safe."""
        async with self._server_index_lock:
            attempts = 0
            while attempts < len(self.target_urls):
                url = self.target_urls[self._current_server_index]
                self._current_server_index = (self._current_server_index + 1) % len(self.target_urls)

                if self._server_health.get(url, True):
                    return url
                attempts += 1

            # All unhealthy - try first server anyway
            logger.warning("All OmniParser servers unhealthy, trying first server")
            return self.target_urls[0]

    async def start(self):
        """Start the queue manager and parallel workers."""
        if self.request_queue is None:
            self.request_queue = asyncio.Queue(maxsize=self.max_queue_size)

        # Start multiple workers
        if not self.worker_tasks or all(t.done() for t in self.worker_tasks):
            self.worker_tasks = []
            for i in range(self.num_workers):
                task = asyncio.create_task(self._worker(worker_id=i))
                self.worker_tasks.append(task)
            self._stats.worker_running = True
            logger.info(f"Started {self.num_workers} parallel queue workers")

    async def stop(self):
        """Stop the queue manager and all workers."""
        if self.worker_tasks:
            for task in self.worker_tasks:
                if not task.done():
                    task.cancel()
            # Wait for all to finish
            for task in self.worker_tasks:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self.worker_tasks = []
            self._stats.worker_running = False
            logger.info("All queue workers stopped")

    async def _worker(self, worker_id: int = 0):
        """Background worker that processes requests from the queue."""
        logger.info(f"Worker {worker_id} started")

        while True:
            try:
                # Get next request from queue
                queued_request: QueuedRequest = await self.request_queue.get()
                self._update_queue_depth()

                queue_wait_time = queued_request.queue_wait_time
                self._queue_wait_times.append(queue_wait_time)

                logger.info(
                    f"[W{worker_id}] Processing request {queued_request.request_id} "
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

                    logger.info(f"[W{worker_id}] Request {queued_request.request_id} completed in {processing_time:.2f}s")

                except asyncio.TimeoutError:
                    processing_time = time.time() - start_time
                    self._stats.timeout_requests += 1
                    job_record.status = "timeout"
                    job_record.processing_time = processing_time
                    job_record.error = f"Timeout after {self.timeout}s"

                    error = Exception(f"Request timed out after {self.timeout}s")
                    queued_request.response_future.set_exception(error)
                    logger.error(f"[W{worker_id}] Request {queued_request.request_id} timed out")

                except Exception as e:
                    processing_time = time.time() - start_time
                    self._stats.failed_requests += 1
                    job_record.status = "failed"
                    job_record.processing_time = processing_time
                    job_record.error = str(e)

                    queued_request.response_future.set_exception(e)
                    logger.error(f"[W{worker_id}] Request {queued_request.request_id} failed: {e}")

                finally:
                    self._job_history.appendleft(job_record)
                    self.request_queue.task_done()
                    self._update_stats()

            except asyncio.CancelledError:
                logger.info(f"[W{worker_id}] Worker cancelled, shutting down")
                break
            except Exception as e:
                logger.error(f"[W{worker_id}] Worker error: {e}")
                await asyncio.sleep(1)  # Avoid tight loop on errors

    async def _forward_to_omniparser(self, queued_request: QueuedRequest) -> Dict[str, Any]:
        """Forward a request to the next available OmniParser server."""
        target_url = await self._get_next_server()
        logger.debug(f"Forwarding request {queued_request.request_id} to {target_url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{target_url}/parse/",
                    json=queued_request.payload,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code != 200:
                    self._server_health[target_url] = False
                    raise Exception(f"OmniParser error {response.status_code}: {response.text}")

                # Mark server as healthy on success
                self._server_health[target_url] = True
                return response.json()

            except httpx.ConnectError as e:
                self._server_health[target_url] = False
                logger.error(f"Connection failed to {target_url}: {e}")
                raise

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

    async def health_check(self) -> List[Dict[str, Any]]:
        """Check health of all OmniParser servers."""
        results = []
        async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
            for url in self.target_urls:
                try:
                    # Use trailing slash - OmniParser requires it
                    response = await client.get(f"{url}/probe/")
                    response.raise_for_status()
                    self._server_health[url] = True
                    results.append({
                        "url": url,
                        "status": "healthy",
                        "response": response.json(),
                    })
                except Exception as e:
                    self._server_health[url] = False
                    logger.error(f"Health check failed for {url}: {e}")
                    results.append({
                        "url": url,
                        "status": "unhealthy",
                        "error": str(e),
                    })
        return results

    def get_server_health(self) -> Dict[str, bool]:
        """Get current health status of all servers."""
        return self._server_health.copy()


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
