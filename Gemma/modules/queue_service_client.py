# -*- coding: utf-8 -*-
"""
Client for Queue Service (OmniParser queue).
Routes all OmniParser requests through the centralized Queue Service.
"""

import os
import base64
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Result from Queue Service parse operation."""
    success: bool
    job_id: Optional[str] = None
    elements: Optional[List[Dict[str, Any]]] = None
    annotated_image_data: Optional[bytes] = None
    response_time: Optional[float] = None
    queue_time: Optional[float] = None
    error: Optional[str] = None


class QueueServiceClient:
    """
    Client for communicating with Queue Service.

    Routes OmniParser requests through the centralized queue
    to prevent request denial and enable monitoring.
    """

    def __init__(
        self,
        queue_url: str = "http://localhost:9000",
        timeout: float = 120.0,
        retry_count: int = 3,
        retry_delay: float = 2.0
    ):
        self.queue_url = queue_url.rstrip("/")
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self._available = None

    async def parse_screenshot(
        self,
        image_path: str,
        priority: int = 5,
        ocr_config: Optional[Dict[str, Any]] = None
    ) -> ParseResult:
        """
        Submit screenshot for parsing via Queue Service.

        Args:
            image_path: Path to the screenshot image
            priority: Queue priority (1-10, lower = higher priority)
            ocr_config: Optional OCR configuration dict with keys:
                - use_paddleocr: bool (True=PaddleOCR, False=EasyOCR)
                - text_threshold: float (0.0-1.0, lower = more lenient)
                - box_threshold: float (0.0-1.0, lower = detect more elements)
                - iou_threshold: float (0.0-1.0, higher = less overlap removal)

        Returns:
            ParseResult with elements and annotated image
        """
        try:
            if not os.path.exists(image_path):
                return ParseResult(
                    success=False,
                    error=f"Image file not found: {image_path}"
                )

            # Encode image to base64
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')

            # Submit to queue with OCR config
            payload = {
                "base64_image": image_data,
                "priority": priority
            }

            # Add OCR config parameters if provided
            if ocr_config:
                if 'use_paddleocr' in ocr_config:
                    payload['use_paddleocr'] = ocr_config['use_paddleocr']
                if 'text_threshold' in ocr_config:
                    payload['text_threshold'] = ocr_config['text_threshold']
                if 'box_threshold' in ocr_config:
                    payload['box_threshold'] = ocr_config['box_threshold']
                if 'iou_threshold' in ocr_config:
                    payload['iou_threshold'] = ocr_config['iou_threshold']

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.queue_url}/parse/",
                    json=payload
                )

                if response.status_code == 200:
                    response_data = response.json()

                    # Extract elements
                    elements = self._parse_elements(response_data)

                    # Extract annotated image if available
                    annotated_image_data = None
                    if "som_image_base64" in response_data:
                        try:
                            annotated_image_data = base64.b64decode(response_data["som_image_base64"])
                        except Exception as e:
                            logger.warning(f"Failed to decode annotated image: {e}")

                    return ParseResult(
                        success=True,
                        job_id=response_data.get("job_id"),
                        elements=elements,
                        annotated_image_data=annotated_image_data,
                        response_time=response_data.get("processing_time"),
                        queue_time=response_data.get("queue_time")
                    )
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    return ParseResult(success=False, error=error_msg)

        except httpx.TimeoutException:
            return ParseResult(success=False, error="Request timeout - queue may be busy")
        except Exception as e:
            return ParseResult(success=False, error=f"Unexpected error: {str(e)}")

    async def parse_screenshot_base64(self, base64_image: str, priority: int = 5) -> ParseResult:
        """
        Submit base64-encoded screenshot for parsing.

        Args:
            base64_image: Base64-encoded image data
            priority: Queue priority (1-10, lower = higher priority)

        Returns:
            ParseResult with elements and annotated image
        """
        try:
            payload = {
                "base64_image": base64_image,
                "priority": priority
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.queue_url}/parse/",
                    json=payload
                )

                if response.status_code == 200:
                    response_data = response.json()
                    elements = self._parse_elements(response_data)

                    annotated_image_data = None
                    if "som_image_base64" in response_data:
                        try:
                            annotated_image_data = base64.b64decode(response_data["som_image_base64"])
                        except Exception as e:
                            logger.warning(f"Failed to decode annotated image: {e}")

                    return ParseResult(
                        success=True,
                        job_id=response_data.get("job_id"),
                        elements=elements,
                        annotated_image_data=annotated_image_data,
                        response_time=response_data.get("processing_time"),
                        queue_time=response_data.get("queue_time")
                    )
                else:
                    return ParseResult(
                        success=False,
                        error=f"HTTP {response.status_code}: {response.text}"
                    )

        except httpx.TimeoutException:
            return ParseResult(success=False, error="Request timeout - queue may be busy")
        except Exception as e:
            return ParseResult(success=False, error=f"Unexpected error: {str(e)}")

    def _parse_elements(self, response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse UI elements from response."""
        elements = []
        parsed_content_list = response_data.get("parsed_content_list", [])

        for item in parsed_content_list:
            if 'bbox' in item:
                element = {
                    'bbox': item['bbox'],
                    'type': item.get('type', 'unknown'),
                    'content': item.get('content', ''),
                    'interactive': item.get('interactivity', False),
                    'confidence': item.get('confidence', 1.0)
                }
                elements.append(element)

        logger.debug(f"Parsed {len(elements)} UI elements")
        return elements

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.queue_url}/stats")
                if response.status_code == 200:
                    return response.json()
                return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    async def get_job_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent job history."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.queue_url}/jobs",
                    params={"limit": limit}
                )
                if response.status_code == 200:
                    return response.json().get("jobs", [])
                return []
        except Exception as e:
            logger.error(f"Failed to get job history: {e}")
            return []

    def is_available(self) -> bool:
        """Check if Queue Service is available (sync version for startup check)."""
        import requests
        try:
            response = requests.get(f"{self.queue_url}/health", timeout=3)
            self._available = response.status_code == 200
            return self._available
        except Exception:
            self._available = False
            return False

    async def is_available_async(self) -> bool:
        """Check if Queue Service is available (async version)."""
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{self.queue_url}/health")
                self._available = response.status_code == 200
                return self._available
        except Exception:
            self._available = False
            return False

    async def wait_for_service(self, max_retries: int = 10, delay: float = 1.0) -> bool:
        """Wait for Queue Service to become available with exponential backoff."""
        import asyncio

        current_delay = delay
        for attempt in range(max_retries):
            if await self.is_available_async():
                logger.info(f"Queue Service available after {attempt + 1} attempts")
                return True

            logger.warning(
                f"Queue Service not available, attempt {attempt + 1}/{max_retries}, "
                f"retrying in {current_delay:.1f}s..."
            )
            await asyncio.sleep(current_delay)
            current_delay = min(current_delay * 2, 30)

        logger.error(f"Queue Service not available after {max_retries} attempts")
        return False

    def test_connection(self) -> bool:
        """Test connection to Queue Service (sync, for compatibility)."""
        return self.is_available()

    def get_server_status(self) -> Dict[str, Any]:
        """Get server status (sync version for compatibility with existing code)."""
        import requests
        try:
            response = requests.get(f"{self.queue_url}/probe", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "online",
                    "url": self.queue_url,
                    "queue_size": data.get("queue_size", 0),
                    "omniparser_available": data.get("omniparser_available", False)
                }
            return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "offline", "error": str(e)}

    def analyze_screenshot(
        self,
        image_path: str,
        ocr_config: Optional[Dict[str, Any]] = None
    ) -> 'OmniparserResult':
        """
        Sync wrapper for parse_screenshot (compatibility with existing OmniparserClient).

        Args:
            image_path: Path to the screenshot image
            ocr_config: Optional OCR configuration dict with keys:
                - use_paddleocr: bool (True=PaddleOCR, False=EasyOCR)
                - text_threshold: float (0.0-1.0, lower = more lenient)
                - box_threshold: float (0.0-1.0, lower = detect more elements)

        Note: This blocks the thread. For async code, use parse_screenshot directly.
        """
        import asyncio

        # Import here to avoid circular dependency
        from .omniparser_client import OmniparserResult

        try:
            # Run async method in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self.parse_screenshot(image_path, ocr_config=ocr_config)
                )
            finally:
                loop.close()

            return OmniparserResult(
                success=result.success,
                elements=result.elements,
                annotated_image_data=result.annotated_image_data,
                response_time=result.response_time,
                error=result.error
            )
        except Exception as e:
            from .omniparser_client import OmniparserResult
            return OmniparserResult(success=False, error=str(e))

    def close(self):
        """Close the client (no-op for httpx)."""
        pass


# Global client instance
_queue_client: Optional[QueueServiceClient] = None


def get_queue_client(queue_url: str = "http://localhost:9000") -> QueueServiceClient:
    """Get the global queue client instance."""
    global _queue_client
    if _queue_client is None:
        _queue_client = QueueServiceClient(queue_url=queue_url)
    return _queue_client


def set_queue_client(client: QueueServiceClient) -> None:
    """Set the global queue client instance."""
    global _queue_client
    _queue_client = client
