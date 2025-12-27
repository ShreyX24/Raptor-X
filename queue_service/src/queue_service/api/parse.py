"""
Parse API endpoint - queues and forwards parse requests to OmniParser.
"""

import logging
from fastapi import APIRouter, HTTPException

from ..queue_manager import get_queue_manager, ParseRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/parse/")
async def parse_image(request: ParseRequest):
    """
    Parse image endpoint - queues request and forwards to OmniParser.
    Compatible with OmniparserClient API format.

    Args:
        request: Parse request with base64_image and parameters

    Returns:
        OmniParser response with parsed_content_list and som_image_base64
    """
    try:
        # Exclude None values to avoid sending null to OmniParser for optional fields like imgsz
        payload = request.model_dump(exclude_none=True)
        logger.info(f"Received parse request (image size: {len(payload['base64_image'])} bytes)")

        manager = get_queue_manager()
        result = await manager.enqueue_request(payload)

        return result

    except Exception as e:
        error_msg = str(e)
        if "Queue is full" in error_msg:
            raise HTTPException(status_code=503, detail=error_msg)
        elif "timed out" in error_msg.lower():
            raise HTTPException(status_code=504, detail=error_msg)
        else:
            logger.error(f"Parse request failed: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {error_msg}")
