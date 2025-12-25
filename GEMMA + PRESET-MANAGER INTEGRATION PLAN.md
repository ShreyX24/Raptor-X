# Gemma + Preset-Manager Integration Plan

## Context

Two repositories need integration:

1. **Gemma Automation Framework** - Game benchmarking automation with GUI (gui_app_multi_sut.py)
   - Uses mysuts.json for manual SUT configuration
   - Has SUTController class managing automation per SUT
   - Runs campaigns of games with step-based or FSM automation
   - Communicates with SUT clients via HTTP REST API

2. **Preset-Manager** - Game graphics preset management
   - Has full SUT discovery system (UDP broadcast + WebSocket) in src/preset_manager/discovery/
   - SUT client runs on gaming machines with Flask API (sut_client/src/sut_client/service.py)
   - Already has input automation merged from KATANA Gemma
   - Has Steam game detection (get_steam_library_folders, find_steam_game_path)
   - Has sync API for pushing presets to SUTs (/api/sync/push, /api/sync/bulk)

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SUT DISCOVERY SERVICE                             │
│                          (Standalone - Port 5001)                        │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ - UDP Broadcast listener (port 9999)                                ││
│  │ - Device Registry (paired devices, status tracking)                 ││
│  │ - WebSocket manager for real-time SUT connections                   ││
│  │ - REST API: /api/suts, /api/discover, /api/suts/{id}/games          ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
                    ▲                           ▲
                    │                           │
          ┌─────────┴─────────┐       ┌────────┴────────┐
          │                   │       │                 │
┌─────────▼─────────┐  ┌──────▼───────▼─────┐  ┌───────▼────────┐
│   GEMMA GUI       │  │  PRESET-MANAGER    │  │   SUT CLIENT   │
│   (Port 5100)     │  │   (Port 5000)      │  │   (Port 8080)  │
│                   │  │                    │  │                │
│ - Shows SUTs from │  │ - Exposes preset   │  │ - Registers    │
│   discovery svc   │  │   application API  │  │   with discovery│
│ - Selects games + │  │ - Bulk sync API    │  │ - Reports games│
│   preset + SUTs   │  │ - Game detection   │  │ - Applies presets│
│ - Requests preset │  │   via SUT client   │  │ - Input automation│
│   from PM before  │  │                    │  │                │
│   automation      │  │                    │  │                │
└───────────────────┘  └────────────────────┘  └────────────────┘
```

## Implementation Phases

---

## PHASE 1: Create Standalone SUT Discovery Service

Extract discovery from preset-manager into independent service that both Gemma and Preset-Manager consume.

### 1.1 Create sut_discovery_service directory structure

```
sut_discovery_service/
├── __init__.py
├── main.py                    # FastAPI app entry point
├── config.py                  # Service configuration
├── discovery/
│   ├── __init__.py
│   ├── device_registry.py     # Copy from preset-manager, adapt
│   ├── scanner.py             # Copy from preset-manager, adapt
│   ├── udp_announcer.py       # Copy from preset-manager
│   ├── websocket_manager.py   # Copy from preset-manager
│   └── events.py              # Copy from preset-manager
├── api/
│   ├── __init__.py
│   ├── suts.py                # SUT management endpoints
│   └── games.py               # Installed games endpoints
├── utils/
│   ├── __init__.py
│   └── network.py             # Network utilities
└── requirements.txt
```

### 1.2 main.py - FastAPI application

```python
# sut_discovery_service/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

from .config import get_settings
from .api import suts, games
from .discovery.device_registry import get_device_registry
from .discovery.scanner import init_discovery_service
from .discovery.udp_announcer import UDPAnnouncer

logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title="SUT Discovery Service",
        description="Centralized SUT discovery for Gemma and Preset-Manager",
        version="1.0.0"
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(suts.router, prefix="/api", tags=["SUTs"])
    app.include_router(games.router, prefix="/api", tags=["Games"])
    
    @app.on_event("startup")
    async def startup():
        # Initialize device registry
        registry = get_device_registry()
        registry.load_paired_devices_on_startup()
        
        # Initialize discovery service
        discovery = init_discovery_service(settings, registry)
        discovery.start()
        
        # Start UDP announcer
        announcer = UDPAnnouncer(
            master_ip=settings.host_ip,
            ws_port=settings.port,
            api_port=settings.port,
            broadcast_interval=1.0
        )
        announcer.start()
        
        app.state.discovery = discovery
        app.state.announcer = announcer
        app.state.registry = registry
        
        logger.info(f"SUT Discovery Service started on port {settings.port}")
    
    @app.on_event("shutdown")
    async def shutdown():
        if hasattr(app.state, 'discovery'):
            app.state.discovery.stop()
        if hasattr(app.state, 'announcer'):
            app.state.announcer.stop()
        logger.info("SUT Discovery Service stopped")
    
    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "sut-discovery"}
    
    return app

app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
```

### 1.3 api/suts.py - SUT endpoints

```python
# sut_discovery_service/api/suts.py

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import Optional, List
from pydantic import BaseModel

from ..discovery.device_registry import get_device_registry, SUTDevice
from ..discovery.scanner import get_discovery_service
from ..discovery.websocket_manager import get_ws_manager

router = APIRouter()

class PairRequest(BaseModel):
    paired_by: str = "user"

@router.get("/suts")
async def list_suts(status: Optional[str] = None):
    """List all discovered SUTs"""
    registry = get_device_registry()
    
    if status == "online":
        devices = registry.get_online_devices()
    elif status == "offline":
        devices = [d for d in registry.get_all_devices() if not d.is_online]
    elif status == "paired":
        devices = registry.get_paired_devices()
    else:
        devices = registry.get_all_devices()
    
    return {
        "suts": [_device_to_dict(d) for d in devices],
        "count": len(devices)
    }

@router.get("/suts/{unique_id}")
async def get_sut(unique_id: str):
    """Get specific SUT details"""
    registry = get_device_registry()
    device = registry.get_device_by_id(unique_id)
    
    if not device:
        raise HTTPException(status_code=404, detail=f"SUT {unique_id} not found")
    
    return _device_to_dict(device)

@router.post("/suts/{unique_id}/pair")
async def pair_sut(unique_id: str, request: PairRequest):
    """Pair a SUT for priority scanning"""
    registry = get_device_registry()
    success = registry.pair_device(unique_id, request.paired_by)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"SUT {unique_id} not found")
    
    return {"status": "paired", "unique_id": unique_id}

@router.post("/suts/{unique_id}/unpair")
async def unpair_sut(unique_id: str):
    """Unpair a SUT"""
    registry = get_device_registry()
    success = registry.unpair_device(unique_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"SUT {unique_id} not found")
    
    return {"status": "unpaired", "unique_id": unique_id}

@router.post("/discover")
async def trigger_discovery():
    """Force immediate discovery scan"""
    discovery = get_discovery_service()
    
    if not discovery:
        raise HTTPException(status_code=500, detail="Discovery service not initialized")
    
    stats = discovery.force_discovery_scan()
    return {"status": "scan_complete", "stats": stats}

@router.get("/discover/status")
async def discovery_status():
    """Get discovery service status"""
    discovery = get_discovery_service()
    
    if not discovery:
        return {"running": False, "error": "Discovery service not initialized"}
    
    return discovery.get_discovery_status()

@router.websocket("/ws/sut/{sut_id}")
async def sut_websocket(websocket: WebSocket, sut_id: str):
    """WebSocket endpoint for SUT connections"""
    manager = get_ws_manager()
    
    try:
        await websocket.accept()
        data = await websocket.receive_json()
        
        if data.get("type") != "register":
            await websocket.close(code=4001, reason="First message must be registration")
            return
        
        connection = await manager.connect(sut_id, websocket, data)
        
        await websocket.send_json({
            "type": "register_ack",
            "sut_id": sut_id,
            "message": "Registration successful"
        })
        
        while True:
            message = await websocket.receive_json()
            connection.update_last_seen()
            
            if message.get("type") == "pong":
                pass
            elif message.get("type") == "installed_games":
                connection.info["installed_games"] = message.get("games", [])
            
    except WebSocketDisconnect:
        await manager.disconnect(sut_id)
    except Exception as e:
        await manager.disconnect(sut_id)

def _device_to_dict(device: SUTDevice) -> dict:
    return {
        "unique_id": device.unique_id,
        "ip": device.ip,
        "port": device.port,
        "hostname": device.hostname,
        "status": device.status.value,
        "is_online": device.is_online,
        "is_paired": device.is_paired,
        "display_name": device.display_name,
        "cpu_model": device.cpu_model,
        "capabilities": device.capabilities,
        "last_seen": device.last_seen.isoformat() if device.last_seen else None
    }
```

### 1.4 api/games.py - Installed games endpoints

```python
# sut_discovery_service/api/games.py

from fastapi import APIRouter, HTTPException
import httpx
import logging

from ..discovery.device_registry import get_device_registry

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/suts/{unique_id}/games")
async def get_installed_games(unique_id: str):
    """
    Get installed games on a SUT.
    Queries the SUT client directly for installed games list.
    """
    registry = get_device_registry()
    device = registry.get_device_by_id(unique_id)
    
    if not device:
        raise HTTPException(status_code=404, detail=f"SUT {unique_id} not found")
    
    if not device.is_online:
        raise HTTPException(status_code=503, detail=f"SUT {unique_id} is offline")
    
    # Query SUT client for installed games
    sut_url = f"http://{device.ip}:{device.port}/installed_games"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(sut_url)
            response.raise_for_status()
            return response.json()
    
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"Timeout querying SUT {unique_id}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error querying SUT: {str(e)}")
```

---

## PHASE 2: Add Installed Games Endpoint to SUT Client

The SUT client needs an endpoint to report installed Steam games.

### 2.1 Update sut_client/src/sut_client/service.py

Add new endpoint after existing endpoints:

```python
# Add to sut_client/src/sut_client/service.py

from .steam import get_steam_library_folders, find_steam_game_path

@app.route('/installed_games', methods=['GET'])
def get_installed_games():
    """
    Get list of installed Steam games on this SUT.
    Scans Steam library folders for installed games.
    """
    try:
        from .steam import get_steam_library_folders
        import os
        import re
        
        libraries = get_steam_library_folders()
        installed_games = []
        
        for lib in libraries:
            steamapps = os.path.join(lib, "steamapps")
            if not os.path.exists(steamapps):
                continue
            
            # Find all appmanifest files
            for filename in os.listdir(steamapps):
                if filename.startswith("appmanifest_") and filename.endswith(".acf"):
                    app_id = filename.replace("appmanifest_", "").replace(".acf", "")
                    manifest_path = os.path.join(steamapps, filename)
                    
                    try:
                        with open(manifest_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Extract game name
                        name_match = re.search(r'"name"\s+"([^"]+)"', content)
                        installdir_match = re.search(r'"installdir"\s+"([^"]+)"', content)
                        
                        if name_match and installdir_match:
                            game_name = name_match.group(1)
                            install_dir = installdir_match.group(1)
                            full_path = os.path.join(steamapps, "common", install_dir)
                            
                            installed_games.append({
                                "steam_app_id": app_id,
                                "name": game_name,
                                "install_dir": install_dir,
                                "install_path": full_path,
                                "exists": os.path.exists(full_path)
                            })
                    
                    except Exception as e:
                        logger.warning(f"Failed to parse {filename}: {e}")
        
        return jsonify({
            "success": True,
            "games": installed_games,
            "count": len(installed_games),
            "libraries_scanned": len(libraries)
        })
    
    except Exception as e:
        logger.error(f"Error getting installed games: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
```

---

## PHASE 3: Update Preset-Manager to Use Discovery Service

Modify preset-manager to consume SUT discovery service instead of running its own.

### 3.1 Create modules/discovery_client.py in preset-manager

```python
# src/preset_manager/discovery_client.py

import httpx
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DiscoveryClientConfig:
    discovery_url: str = "http://localhost:5001"
    timeout: float = 10.0

class DiscoveryServiceClient:
    """Client for communicating with standalone SUT Discovery Service"""
    
    def __init__(self, config: DiscoveryClientConfig = None):
        self.config = config or DiscoveryClientConfig()
        self._cache = {}
        self._cache_ttl = 5  # seconds
    
    async def get_suts(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all SUTs from discovery service"""
        params = {}
        if status:
            params["status"] = status
        
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.get(
                f"{self.config.discovery_url}/api/suts",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            return data.get("suts", [])
    
    async def get_sut(self, unique_id: str) -> Optional[Dict[str, Any]]:
        """Get specific SUT details"""
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.get(
                f"{self.config.discovery_url}/api/suts/{unique_id}"
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
    
    async def get_installed_games(self, unique_id: str) -> List[Dict[str, Any]]:
        """Get installed games on a SUT"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.config.discovery_url}/api/suts/{unique_id}/games"
            )
            response.raise_for_status()
            data = response.json()
            return data.get("games", [])
    
    async def trigger_discovery(self) -> Dict[str, Any]:
        """Trigger immediate discovery scan"""
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(
                f"{self.config.discovery_url}/api/discover"
            )
            response.raise_for_status()
            return response.json()
    
    async def get_discovery_status(self) -> Dict[str, Any]:
        """Get discovery service status"""
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.get(
                f"{self.config.discovery_url}/api/discover/status"
            )
            response.raise_for_status()
            return response.json()
```

### 3.2 Add new endpoint to preset-manager for Gemma integration

Add to src/preset_manager/api/sync.py:

```python
# Add to src/preset_manager/api/sync.py

class GemmaPresetRequest(BaseModel):
    """Request from Gemma to apply presets before automation"""
    sut_ips: List[str]
    games: List[str]  # Game short names
    preset: dict  # {"resolution": "1920x1080", "graphics": "high"}

class GemmaPresetResponse(BaseModel):
    """Response to Gemma after preset application"""
    successful: List[dict]  # [{"sut_ip": "...", "game": "...", "status": "applied"}]
    failed: List[dict]      # [{"sut_ip": "...", "game": "...", "error": "..."}]
    skipped: List[dict]     # [{"sut_ip": "...", "game": "...", "reason": "not installed"}]

@router.post("/sync/gemma-presets", response_model=GemmaPresetResponse)
async def apply_presets_for_gemma(request: GemmaPresetRequest):
    """
    Apply presets for Gemma automation.
    
    Flow:
    1. For each SUT IP, resolve to device from discovery service
    2. Check which games are installed on each SUT
    3. Apply preset only for installed games
    4. Return results grouped by success/failure/skipped
    """
    global _device_registry, _sync_manager
    
    successful = []
    failed = []
    skipped = []
    
    # Determine preset level from request
    resolution = request.preset.get("resolution", "1920x1080")
    graphics = request.preset.get("graphics", "high")
    
    # Map common preset names to folder names
    res_map = {"1920x1080": "1080p", "2560x1440": "1440p", "3840x2160": "4k"}
    res_short = res_map.get(resolution, "1080p")
    preset_level = f"ppg-{graphics}-{res_short}"
    
    for sut_ip in request.sut_ips:
        # Find device by IP
        device = None
        if _device_registry:
            device = _device_registry.get_device_by_ip(sut_ip)
        
        if not device:
            for game in request.games:
                failed.append({
                    "sut_ip": sut_ip,
                    "game": game,
                    "error": "SUT not found in device registry"
                })
            continue
        
        if not device.is_online:
            for game in request.games:
                failed.append({
                    "sut_ip": sut_ip,
                    "game": game,
                    "error": "SUT is offline"
                })
            continue
        
        # Get installed games on this SUT
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"http://{device.ip}:{device.port}/installed_games"
                )
                response.raise_for_status()
                sut_games = response.json().get("games", [])
        except Exception as e:
            for game in request.games:
                failed.append({
                    "sut_ip": sut_ip,
                    "game": game,
                    "error": f"Failed to get installed games: {str(e)}"
                })
            continue
        
        # Build lookup of installed game names
        installed_names = {g["name"].lower(): g for g in sut_games}
        installed_ids = {g["steam_app_id"]: g for g in sut_games}
        
        for game_short_name in request.games:
            # Check if preset exists for this game
            if not check_preset_exists(game_short_name, preset_level):
                skipped.append({
                    "sut_ip": sut_ip,
                    "game": game_short_name,
                    "reason": f"No preset '{preset_level}' available for game"
                })
                continue
            
            # Check if game is installed (try various matching strategies)
            game_installed = False
            # TODO: Implement better game name matching
            # For now, check if short_name appears in any installed game name
            for installed_game in sut_games:
                if game_short_name.lower().replace("-", " ") in installed_game["name"].lower():
                    game_installed = True
                    break
            
            if not game_installed:
                skipped.append({
                    "sut_ip": sut_ip,
                    "game": game_short_name,
                    "reason": "Game not installed on SUT"
                })
                continue
            
            # Apply the preset
            try:
                if _sync_manager:
                    success = _sync_manager.sync_to_sut(
                        sut_unique_id=device.unique_id,
                        game_short_name=game_short_name,
                        preset_level=preset_level
                    )
                    
                    if success:
                        successful.append({
                            "sut_ip": sut_ip,
                            "game": game_short_name,
                            "preset_level": preset_level,
                            "status": "applied"
                        })
                    else:
                        failed.append({
                            "sut_ip": sut_ip,
                            "game": game_short_name,
                            "error": "Sync manager returned failure"
                        })
                else:
                    failed.append({
                        "sut_ip": sut_ip,
                        "game": game_short_name,
                        "error": "Sync manager not initialized"
                    })
            
            except Exception as e:
                failed.append({
                    "sut_ip": sut_ip,
                    "game": game_short_name,
                    "error": str(e)
                })
    
    return GemmaPresetResponse(
        successful=successful,
        failed=failed,
        skipped=skipped
    )
```

---

## PHASE 4: Update Gemma to Use Discovery Service and Preset-Manager

### 4.1 Create modules/discovery_client.py in Gemma

```python
# modules/discovery_client.py

import requests
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass 
class SUTInfo:
    unique_id: str
    ip: str
    port: int
    hostname: str
    status: str
    is_online: bool
    is_paired: bool
    display_name: Optional[str] = None
    capabilities: List[str] = None

class DiscoveryClient:
    """Client for SUT Discovery Service"""
    
    def __init__(self, discovery_url: str = "http://localhost:5001"):
        self.discovery_url = discovery_url.rstrip("/")
        self.timeout = 10
    
    def get_suts(self, status: Optional[str] = None) -> List[SUTInfo]:
        """Get all discovered SUTs"""
        params = {}
        if status:
            params["status"] = status
        
        try:
            response = requests.get(
                f"{self.discovery_url}/api/suts",
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            return [SUTInfo(
                unique_id=s.get("unique_id", ""),
                ip=s.get("ip", ""),
                port=s.get("port", 8080),
                hostname=s.get("hostname", ""),
                status=s.get("status", "unknown"),
                is_online=s.get("is_online", False),
                is_paired=s.get("is_paired", False),
                display_name=s.get("display_name"),
                capabilities=s.get("capabilities", [])
            ) for s in data.get("suts", [])]
        
        except Exception as e:
            logger.error(f"Failed to get SUTs from discovery service: {e}")
            return []
    
    def get_online_suts(self) -> List[SUTInfo]:
        """Get only online SUTs"""
        return self.get_suts(status="online")
    
    def get_paired_suts(self) -> List[SUTInfo]:
        """Get paired SUTs"""
        return self.get_suts(status="paired")
    
    def get_installed_games(self, sut_ip: str) -> List[Dict[str, Any]]:
        """Get installed games on a specific SUT"""
        try:
            # First get SUT by IP to find unique_id
            suts = self.get_suts()
            sut = next((s for s in suts if s.ip == sut_ip), None)
            
            if not sut:
                logger.warning(f"SUT with IP {sut_ip} not found")
                return []
            
            response = requests.get(
                f"{self.discovery_url}/api/suts/{sut.unique_id}/games",
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get("games", [])
        
        except Exception as e:
            logger.error(f"Failed to get installed games for {sut_ip}: {e}")
            return []
    
    def trigger_discovery(self) -> bool:
        """Trigger immediate discovery scan"""
        try:
            response = requests.post(
                f"{self.discovery_url}/api/discover",
                timeout=self.timeout
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to trigger discovery: {e}")
            return False
    
    def is_service_available(self) -> bool:
        """Check if discovery service is available"""
        try:
            response = requests.get(
                f"{self.discovery_url}/health",
                timeout=3
            )
            return response.status_code == 200
        except:
            return False
```

### 4.2 Create modules/preset_manager_client.py in Gemma

```python
# modules/preset_manager_client.py

import requests
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PresetResult:
    sut_ip: str
    game: str
    success: bool
    preset_level: Optional[str] = None
    error: Optional[str] = None
    reason: Optional[str] = None

class PresetManagerClient:
    """Client for Preset-Manager API"""
    
    def __init__(self, preset_manager_url: str = "http://localhost:5000"):
        self.preset_manager_url = preset_manager_url.rstrip("/")
        self.timeout = 60  # Preset application can take time
    
    def apply_presets(
        self,
        sut_ips: List[str],
        games: List[str],
        resolution: str = "1920x1080",
        graphics: str = "high"
    ) -> Dict[str, List[PresetResult]]:
        """
        Apply presets for games on SUTs before automation.
        
        Returns dict with keys: successful, failed, skipped
        """
        try:
            payload = {
                "sut_ips": sut_ips,
                "games": games,
                "preset": {
                    "resolution": resolution,
                    "graphics": graphics
                }
            }
            
            response = requests.post(
                f"{self.preset_manager_url}/api/sync/gemma-presets",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            results = {
                "successful": [],
                "failed": [],
                "skipped": []
            }
            
            for item in data.get("successful", []):
                results["successful"].append(PresetResult(
                    sut_ip=item.get("sut_ip", ""),
                    game=item.get("game", ""),
                    success=True,
                    preset_level=item.get("preset_level")
                ))
            
            for item in data.get("failed", []):
                results["failed"].append(PresetResult(
                    sut_ip=item.get("sut_ip", ""),
                    game=item.get("game", ""),
                    success=False,
                    error=item.get("error")
                ))
            
            for item in data.get("skipped", []):
                results["skipped"].append(PresetResult(
                    sut_ip=item.get("sut_ip", ""),
                    game=item.get("game", ""),
                    success=False,
                    reason=item.get("reason")
                ))
            
            return results
        
        except Exception as e:
            logger.error(f"Failed to apply presets: {e}")
            # Return all as failed
            return {
                "successful": [],
                "failed": [PresetResult(
                    sut_ip=ip,
                    game=game,
                    success=False,
                    error=str(e)
                ) for ip in sut_ips for game in games],
                "skipped": []
            }
    
    def get_available_presets(self) -> List[Dict[str, Any]]:
        """Get list of available games with presets"""
        try:
            response = requests.get(
                f"{self.preset_manager_url}/api/sync/games",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json().get("games", [])
        except Exception as e:
            logger.error(f"Failed to get available presets: {e}")
            return []
    
    def is_service_available(self) -> bool:
        """Check if preset-manager is available"""
        try:
            response = requests.get(
                f"{self.preset_manager_url}/health",
                timeout=3
            )
            return response.status_code == 200
        except:
            return False
```

### 4.3 Update gui_app_multi_sut.py

Major changes to the GUI:

```python
# Add imports at top of gui_app_multi_sut.py
from modules.discovery_client import DiscoveryClient, SUTInfo
from modules.preset_manager_client import PresetManagerClient, PresetResult

# Add to MultiSUTGUI.__init__():
self.discovery_client = DiscoveryClient("http://localhost:5001")
self.preset_client = PresetManagerClient("http://localhost:5000")
self.selected_preset = {"resolution": "1920x1080", "graphics": "high"}

# Add new method for SUT selection panel
def create_sut_discovery_panel(self, parent):
    """Create SUT discovery panel with checkboxes"""
    frame = ttk.LabelFrame(parent, text="SUT Selection (from Discovery Service)")
    
    # Toolbar
    toolbar = ttk.Frame(frame)
    ttk.Button(toolbar, text="Refresh SUTs", command=self.refresh_suts).pack(side=tk.LEFT)
    ttk.Button(toolbar, text="Select All", command=self.select_all_suts).pack(side=tk.LEFT)
    ttk.Button(toolbar, text="Deselect All", command=self.deselect_all_suts).pack(side=tk.LEFT)
    toolbar.pack(fill=tk.X, padx=5, pady=5)
    
    # SUT list with checkboxes
    self.sut_listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, height=10)
    self.sut_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # Status label
    self.sut_status_label = ttk.Label(frame, text="No SUTs loaded")
    self.sut_status_label.pack(fill=tk.X, padx=5)
    
    return frame

def refresh_suts(self):
    """Refresh SUT list from discovery service"""
    self.sut_listbox.delete(0, tk.END)
    
    if not self.discovery_client.is_service_available():
        self.sut_status_label.config(text="⚠ Discovery service not available")
        return
    
    suts = self.discovery_client.get_online_suts()
    self.discovered_suts = {s.ip: s for s in suts}
    
    for sut in suts:
        display_name = sut.display_name or sut.hostname or sut.ip
        status = "🟢" if sut.is_online else "🔴"
        self.sut_listbox.insert(tk.END, f"{status} {display_name} ({sut.ip})")
    
    self.sut_status_label.config(text=f"Found {len(suts)} online SUTs")

# Add preset selection panel
def create_preset_selection_panel(self, parent):
    """Create preset (PPG) selection panel"""
    frame = ttk.LabelFrame(parent, text="PPG Settings")
    
    # Resolution dropdown
    ttk.Label(frame, text="Resolution:").pack(anchor=tk.W, padx=5)
    self.resolution_var = tk.StringVar(value="1920x1080")
    resolution_combo = ttk.Combobox(frame, textvariable=self.resolution_var,
                                     values=["1920x1080", "2560x1440", "3840x2160"])
    resolution_combo.pack(fill=tk.X, padx=5, pady=2)
    
    # Graphics dropdown
    ttk.Label(frame, text="Graphics Quality:").pack(anchor=tk.W, padx=5)
    self.graphics_var = tk.StringVar(value="high")
    graphics_combo = ttk.Combobox(frame, textvariable=self.graphics_var,
                                   values=["low", "medium", "high", "ultra"])
    graphics_combo.pack(fill=tk.X, padx=5, pady=2)
    
    return frame

# Add validation method
def validate_before_start(self):
    """
    Validate configuration before starting automation.
    Checks installed games and preset availability.
    """
    selected_suts = self.get_selected_sut_ips()
    selected_games = self.get_selected_games()
    
    if not selected_suts:
        messagebox.showwarning("Validation", "No SUTs selected")
        return False
    
    if not selected_games:
        messagebox.showwarning("Validation", "No games selected")
        return False
    
    validation_results = []
    
    for sut_ip in selected_suts:
        installed_games = self.discovery_client.get_installed_games(sut_ip)
        installed_names = [g["name"].lower() for g in installed_games]
        
        for game in selected_games:
            # Check if game is installed
            game_found = any(game.lower() in name for name in installed_names)
            validation_results.append({
                "sut_ip": sut_ip,
                "game": game,
                "installed": game_found
            })
    
    # Show validation dialog
    missing = [r for r in validation_results if not r["installed"]]
    
    if missing:
        msg = "The following games are not installed:\n\n"
        for r in missing[:10]:  # Show first 10
            msg += f"• {r['game']} on {r['sut_ip']}\n"
        if len(missing) > 10:
            msg += f"\n... and {len(missing) - 10} more"
        msg += "\n\nContinue anyway? (Missing games will be skipped)"
        
        return messagebox.askyesno("Validation Warning", msg)
    
    return True

# Add preset application method
def apply_presets_before_automation(self, sut_ips: List[str], games: List[str]) -> List[str]:
    """
    Apply presets before starting automation.
    Returns list of games that successfully had presets applied.
    """
    self.log_message("Applying PPG presets...")
    
    resolution = self.resolution_var.get()
    graphics = self.graphics_var.get()
    
    results = self.preset_client.apply_presets(
        sut_ips=sut_ips,
        games=games,
        resolution=resolution,
        graphics=graphics
    )
    
    # Log results
    for r in results["successful"]:
        self.log_message(f"✓ Preset applied: {r.game} on {r.sut_ip} ({r.preset_level})")
    
    for r in results["failed"]:
        self.log_message(f"✗ Preset failed: {r.game} on {r.sut_ip} - {r.error}")
    
    for r in results["skipped"]:
        self.log_message(f"⊘ Preset skipped: {r.game} on {r.sut_ip} - {r.reason}")
    
    # Return only games with successful preset application
    successful_games = set(r.game for r in results["successful"])
    
    # Show summary
    total = len(games) * len(sut_ips)
    success = len(results["successful"])
    
    messagebox.showinfo(
        "Preset Application Complete",
        f"Presets Applied: {success}/{total}\n"
        f"Failed: {len(results['failed'])}\n"
        f"Skipped: {len(results['skipped'])}\n\n"
        f"Automation will run on {len(successful_games)} games with successful presets."
    )
    
    return list(successful_games)

# Modify start_automation method to include preset application
def start_automation(self):
    """Modified to include preset application step"""
    # Validation
    if not self.validate_before_start():
        return
    
    selected_suts = self.get_selected_sut_ips()
    selected_games = self.get_selected_games()
    
    # Apply presets first
    if not self.preset_client.is_service_available():
        if not messagebox.askyesno(
            "Preset Manager Unavailable",
            "Preset Manager is not available.\n"
            "Continue without applying presets?"
        ):
            return
        games_to_run = selected_games
    else:
        games_to_run = self.apply_presets_before_automation(selected_suts, selected_games)
        
        if not games_to_run:
            messagebox.showwarning(
                "No Games Ready",
                "No games have successful preset application.\n"
                "Please check preset configurations and game installations."
            )
            return
    
    # Continue with existing automation logic using games_to_run
    # ... existing automation code ...
```

---

## PHASE 5: Configuration Files

### 5.1 Create config/integration_config.json

```json
{
    "discovery_service": {
        "url": "http://localhost:5001",
        "timeout": 10,
        "refresh_interval": 30
    },
    "preset_manager": {
        "url": "http://localhost:5000",
        "timeout": 60,
        "retry_count": 3
    },
    "defaults": {
        "resolution": "1920x1080",
        "graphics": "high"
    },
    "validation": {
        "check_installed_games": true,
        "require_preset_success": false
    }
}
```

---

## PHASE 6: Remove SUT Discovery from Both Original Systems

### 6.1 Gemma changes

Remove from gui_app_multi_sut.py:
- Remove mysuts.json loading/saving
- Remove manual SUT entry dialog
- Keep mysuts.json as fallback only if discovery service unavailable

### 6.2 Preset-Manager changes

In src/preset_manager/server.py:
- Make discovery service optional/configurable
- Add config flag: use_external_discovery = True
- If external discovery, don't start internal scanner/UDP announcer
- Use DiscoveryServiceClient instead

---

## Implementation Order

1. **Phase 1.1-1.4**: Create standalone SUT Discovery Service
   - Copy discovery modules from preset-manager
   - Create FastAPI app with endpoints
   - Test standalone service works

2. **Phase 2.1**: Add /installed_games endpoint to SUT client
   - Simple addition, test immediately

3. **Phase 3.1-3.2**: Update Preset-Manager
   - Add DiscoveryServiceClient
   - Add /api/sync/gemma-presets endpoint
   - Test preset application flow

4. **Phase 4.1-4.3**: Update Gemma
   - Add DiscoveryClient
   - Add PresetManagerClient
   - Update GUI with SUT selection panel
   - Add preset selection panel
   - Add validation and preset application to workflow

5. **Phase 5.1**: Add configuration file

6. **Phase 6**: Remove duplicate discovery (optional, can defer)

---

## Testing Checklist

- [ ] SUT Discovery Service starts and discovers SUTs
- [ ] SUT client registers via WebSocket
- [ ] /installed_games endpoint returns Steam games
- [ ] Preset-Manager /api/sync/gemma-presets works
- [ ] Gemma GUI shows discovered SUTs
- [ ] Gemma GUI shows preset selection
- [ ] Validation shows installed/missing games
- [ ] Preset application runs before automation
- [ ] Automation only runs on successful preset games
- [ ] Fallback works when services unavailable

---

## API Summary

### SUT Discovery Service (Port 5001)
- GET /api/suts - List all SUTs
- GET /api/suts/{id} - Get specific SUT
- GET /api/suts/{id}/games - Get installed games
- POST /api/discover - Trigger scan
- WS /api/ws/sut/{id} - WebSocket for SUT clients

### Preset-Manager (Port 5000)
- POST /api/sync/gemma-presets - Apply presets for Gemma
- GET /api/sync/games - List games with presets
- POST /api/sync/push - Push preset to SUTs (existing)

### SUT Client (Port 8080)
- GET /installed_games - List installed Steam games
- POST /apply-preset - Apply preset (existing)
- GET /status - SUT status (existing)
