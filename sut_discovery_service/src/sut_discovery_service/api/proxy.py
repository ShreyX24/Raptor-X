"""
SUT Proxy API endpoints - ALL SUT communication goes through here.

Neither Gemma nor Preset-Manager talk directly to SUTs.
This is the single gateway for all SUT API calls.
"""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Request, Response
import httpx

from ..discovery import get_device_registry

logger = logging.getLogger(__name__)
router = APIRouter()


async def proxy_to_sut(
    unique_id: str,
    endpoint: str,
    method: str = "GET",
    json_data: Dict[str, Any] = None,
    timeout: float = 30.0,
    return_raw: bool = False
) -> Any:
    """
    Proxy a request to a SUT.

    Args:
        unique_id: SUT unique ID
        endpoint: API endpoint on the SUT (e.g., "/installed_games")
        method: HTTP method (GET, POST)
        json_data: JSON body for POST requests
        timeout: Request timeout in seconds
        return_raw: If True, return raw response content (for binary data like screenshots)

    Returns:
        JSON response from SUT, or raw bytes if return_raw=True
    """
    registry = get_device_registry()
    device = registry.get_device_by_id(unique_id)

    if not device:
        raise HTTPException(status_code=404, detail=f"SUT {unique_id} not found")

    if not device.is_online:
        raise HTTPException(status_code=503, detail=f"SUT {unique_id} is offline")

    sut_url = f"http://{device.ip}:{device.port}{endpoint}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                response = await client.get(sut_url)
            elif method == "POST":
                response = await client.post(sut_url, json=json_data)
            else:
                raise HTTPException(status_code=405, detail=f"Method {method} not supported")

            if return_raw:
                return response.content

            return response.json()

    except httpx.TimeoutException:
        logger.error(f"Timeout proxying to SUT {unique_id}: {endpoint}")
        raise HTTPException(status_code=504, detail=f"Timeout connecting to SUT {unique_id}")
    except Exception as e:
        logger.error(f"Error proxying to SUT {unique_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Error proxying to SUT: {str(e)}")


# ============== Game Information ==============

@router.get("/suts/{unique_id}/games")
async def get_installed_games(unique_id: str):
    """
    Get installed games on SUT.
    Proxies to SUT /installed_games endpoint.
    """
    return await proxy_to_sut(unique_id, "/installed_games", "GET")


# ============== Preset Management ==============

@router.post("/suts/{unique_id}/apply-preset")
async def apply_preset(unique_id: str, request: Request):
    """
    Apply preset to a game on SUT.
    Proxies to SUT /apply-preset endpoint.
    """
    body = await request.json()
    return await proxy_to_sut(unique_id, "/apply-preset", "POST", body, timeout=60.0)


# ============== Screenshots ==============

@router.get("/suts/{unique_id}/screenshot")
async def get_screenshot(unique_id: str):
    """
    Get screenshot from SUT.
    Proxies to SUT /screenshot endpoint.
    Returns raw PNG image bytes.
    """
    raw_bytes = await proxy_to_sut(unique_id, "/screenshot", "GET", return_raw=True)
    return Response(content=raw_bytes, media_type="image/png")


# ============== Input Actions ==============

@router.post("/suts/{unique_id}/action")
async def send_action(unique_id: str, request: Request):
    """
    Send input action to SUT.
    Proxies to SUT /action endpoint.

    Supports: click, key, drag, scroll, text, hotkey, etc.
    """
    body = await request.json()
    return await proxy_to_sut(unique_id, "/action", "POST", body)


# ============== Game Launch/Control ==============

@router.post("/suts/{unique_id}/launch")
async def launch_game(unique_id: str, request: Request):
    """
    Launch game on SUT.
    Proxies to SUT /launch endpoint.
    """
    body = await request.json()
    return await proxy_to_sut(unique_id, "/launch", "POST", body, timeout=120.0)


@router.post("/suts/{unique_id}/check-process")
async def check_process(unique_id: str, request: Request):
    """
    Check if process is running on SUT.
    Proxies to SUT /check_process endpoint.
    """
    body = await request.json()
    return await proxy_to_sut(unique_id, "/check_process", "POST", body)


@router.post("/suts/{unique_id}/kill-process")
async def kill_process(unique_id: str, request: Request):
    """
    Kill process on SUT.
    Proxies to SUT /kill_process endpoint.
    """
    body = await request.json()
    return await proxy_to_sut(unique_id, "/kill_process", "POST", body)


@router.post("/suts/{unique_id}/terminate-game")
async def terminate_game(unique_id: str):
    """
    Terminate current game on SUT.
    Proxies to SUT /terminate_game endpoint.
    """
    return await proxy_to_sut(unique_id, "/terminate_game", "POST", {})


# ============== Status/Health ==============

@router.get("/suts/{unique_id}/status")
async def get_sut_status(unique_id: str):
    """
    Get SUT service status.
    Proxies to SUT /status endpoint.
    """
    return await proxy_to_sut(unique_id, "/status", "GET")


@router.get("/suts/{unique_id}/health")
async def get_sut_health(unique_id: str):
    """
    Get SUT health check.
    Proxies to SUT /health endpoint.
    """
    return await proxy_to_sut(unique_id, "/health", "GET")


@router.get("/suts/{unique_id}/screen-info")
async def get_screen_info(unique_id: str):
    """
    Get SUT screen information.
    Proxies to SUT /screen_info endpoint.
    """
    return await proxy_to_sut(unique_id, "/screen_info", "GET")


@router.get("/suts/{unique_id}/performance")
async def get_performance(unique_id: str):
    """
    Get SUT performance metrics.
    Proxies to SUT /performance endpoint.
    """
    return await proxy_to_sut(unique_id, "/performance", "GET")
