GEMMA + PRESET-MANAGER INTEGRATION

Context: Gemma does game benchmarking automation. Preset-Manager handles game graphics settings (PPG: resolution, graphics quality). Both need to share SUT discovery and work together.

Current State:
- Gemma uses mysuts.json for manual SUT config
- Preset-Manager has full SUT discovery (UDP broadcast + WebSocket) in src/preset_manager/discovery/
- Preset-Manager's SUT client already has input automation from KATANA Gemma
- Both systems work independently

Target State:
- Standalone SUT Discovery Service (port 5001) - both systems consume it
- Gemma shows discovered SUTs in GUI
- User selects SUTs + games + PPG preset in Gemma
- Before automation, Gemma requests preset application from Preset-Manager
- Preset-Manager checks installed games on SUTs, applies presets, returns results
- Gemma runs automation only on games with successful preset application

---

PHASE 1: CREATE STANDALONE SUT DISCOVERY SERVICE

Create directory: sut_discovery_service/

Copy these files from preset-manager src/preset_manager/discovery/ to sut_discovery_service/discovery/:
- device_registry.py
- scanner.py
- udp_announcer.py
- websocket_manager.py
- events.py

Also copy: src/preset_manager/utils/network.py to sut_discovery_service/utils/

Create sut_discovery_service/main.py:
- FastAPI app on port 5001
- On startup: load paired devices, start scanner, start UDP announcer
- Include router from api/suts.py

Create sut_discovery_service/api/suts.py with endpoints:
- GET /api/suts - list all SUTs (query param: status=online|offline|paired)
- GET /api/suts/{unique_id} - get specific SUT
- POST /api/suts/{unique_id}/pair - pair SUT
- POST /api/suts/{unique_id}/unpair - unpair SUT
- POST /api/discover - trigger immediate scan
- GET /api/discover/status - get discovery status
- WebSocket /api/ws/sut/{sut_id} - SUT registration endpoint

Create sut_discovery_service/api/games.py with endpoint:
- GET /api/suts/{unique_id}/games - proxy to SUT client's /installed_games endpoint

Create sut_discovery_service/config.py:
- Settings class with host, port (5001), discovery intervals
- Load from environment variables

Create sut_discovery_service/requirements.txt:
fastapi, uvicorn, httpx, websockets, pydantic

---

PHASE 2: ADD INSTALLED GAMES ENDPOINT TO SUT CLIENT

File: preset-manager/sut_client/src/sut_client/service.py

Add new endpoint after existing ones:

@app.route('/installed_games', methods=['GET'])
def get_installed_games():
    """Scan Steam library folders and return installed games"""
    
Implementation:
1. Call get_steam_library_folders() from steam.py
2. For each library, scan steamapps/ for appmanifest_*.acf files
3. Parse each manifest to extract: app_id, name, installdir
4. Return JSON: {"success": true, "games": [...], "count": N}

Each game object:
{
    "steam_app_id": "730",
    "name": "Counter-Strike 2",
    "install_dir": "Counter-Strike 2",
    "install_path": "D:/SteamLibrary/steamapps/common/Counter-Strike 2",
    "exists": true
}

---

PHASE 3: ADD GEMMA INTEGRATION ENDPOINT TO PRESET-MANAGER

File: preset-manager/src/preset_manager/api/sync.py

Add new Pydantic models:
- GemmaPresetRequest: sut_ips (List[str]), games (List[str]), preset (dict with resolution, graphics)
- GemmaPresetResponse: successful (List), failed (List), skipped (List)

Add endpoint POST /api/sync/gemma-presets:

1. For each SUT IP in request:
   a. Find device in registry by IP
   b. If not found or offline, add all games to failed list
   c. Query SUT's /installed_games endpoint
   d. For each game in request:
      - Check if preset exists (preset_level = f"ppg-{graphics}-{resolution_short}")
      - Check if game is installed on SUT (match game short_name against installed game names)
      - If not installed or no preset, add to skipped
      - If installed and preset exists, call sync_manager.sync_to_sut()
      - Add result to successful or failed

2. Return GemmaPresetResponse with all three lists

Resolution mapping: "1920x1080" -> "1080p", "2560x1440" -> "1440p", "3840x2160" -> "4k"
Preset level format: "ppg-high-1080p"

---

PHASE 4: ADD DISCOVERY AND PRESET CLIENTS TO GEMMA

File: gemma/modules/discovery_client.py

Create DiscoveryClient class:
- __init__(discovery_url="http://localhost:5001")
- get_suts(status=None) -> List[SUTInfo]
- get_online_suts() -> List[SUTInfo]
- get_installed_games(sut_ip) -> List[dict]
- trigger_discovery() -> bool
- is_service_available() -> bool

SUTInfo dataclass: unique_id, ip, port, hostname, status, is_online, is_paired, display_name, capabilities

File: gemma/modules/preset_manager_client.py

Create PresetManagerClient class:
- __init__(preset_manager_url="http://localhost:5000")
- apply_presets(sut_ips, games, resolution, graphics) -> dict with successful/failed/skipped lists
- get_available_presets() -> List[dict]
- is_service_available() -> bool

PresetResult dataclass: sut_ip, game, success, preset_level, error, reason

---

PHASE 5: UPDATE GEMMA GUI

File: gemma/gui_app_multi_sut.py

Add to __init__:
- self.discovery_client = DiscoveryClient()
- self.preset_client = PresetManagerClient()
- self.discovered_suts = {}

Add SUT Discovery Panel:
- LabelFrame "SUT Selection (from Discovery Service)"
- Toolbar: Refresh SUTs button, Select All, Deselect All
- Listbox with checkboxes showing discovered SUTs
- Format: "🟢 DisplayName (IP)" or "🔴 DisplayName (IP)"
- Status label showing count

Add Preset Selection Panel:
- LabelFrame "PPG Settings"
- Resolution dropdown: 1920x1080, 2560x1440, 3840x2160
- Graphics dropdown: low, medium, high, ultra
- Store in self.resolution_var, self.graphics_var

Add refresh_suts() method:
- Check discovery service availability
- Call discovery_client.get_online_suts()
- Populate listbox with results

Add validate_before_start() method:
- Get selected SUTs and games
- For each SUT, call discovery_client.get_installed_games()
- Check if selected games are installed
- Show warning dialog for missing games
- Return True/False

Add apply_presets_before_automation(sut_ips, games) method:
- Call preset_client.apply_presets()
- Log all results (successful, failed, skipped)
- Show summary dialog
- Return list of games with successful preset application

Modify start_automation():
1. Call validate_before_start(), exit if False
2. Check preset_client.is_service_available()
3. If available, call apply_presets_before_automation()
4. If not available, ask user to continue without presets
5. Filter game list to only successful preset games
6. Continue with existing automation logic using filtered list

---

PHASE 6: CONFIGURATION

Create gemma/config/integration_config.json:
{
    "discovery_service": {"url": "http://localhost:5001", "timeout": 10},
    "preset_manager": {"url": "http://localhost:5000", "timeout": 60},
    "defaults": {"resolution": "1920x1080", "graphics": "high"}
}

Load in GUI __init__ and use for client initialization.

---

PHASE 7: CLEANUP (OPTIONAL - DEFER IF NEEDED)

In Gemma:
- Remove mysuts.json loading as primary source
- Keep as fallback if discovery service unavailable

In Preset-Manager:
- Add config flag: use_external_discovery
- If True, don't start internal discovery, use client to external service
- Keep internal discovery for standalone usage

---

IMPLEMENTATION ORDER

1. Phase 1: SUT Discovery Service (do first, foundational)
2. Phase 2: SUT client /installed_games endpoint (quick add)
3. Phase 3: Preset-Manager /gemma-presets endpoint (depends on installed games working)
4. Phase 4: Gemma clients (simple HTTP clients)
5. Phase 5: Gemma GUI changes (largest change)
6. Phase 6: Configuration file
7. Phase 7: Cleanup (defer)

Test after each phase before moving on.

---

TESTING FLOW

1. Start SUT Discovery Service on port 5001
2. Start SUT Client on gaming machine
3. Verify SUT appears in discovery service: curl http://localhost:5001/api/suts
4. Verify installed games: curl http://localhost:5001/api/suts/{id}/games
5. Start Preset-Manager on port 5000
6. Test preset application: POST http://localhost:5000/api/sync/gemma-presets
7. Start Gemma GUI
8. Verify SUTs appear in discovery panel
9. Select SUT, games, preset
10. Click start, verify preset application happens first
11. Verify automation runs only on successful games

---

KEY FILES TO CREATE

sut_discovery_service/
├── main.py
├── config.py
├── requirements.txt
├── api/
│   ├── __init__.py
│   ├── suts.py
│   └── games.py
├── discovery/
│   ├── __init__.py
│   ├── device_registry.py (copy from preset-manager)
│   ├── scanner.py (copy from preset-manager)
│   ├── udp_announcer.py (copy from preset-manager)
│   ├── websocket_manager.py (copy from preset-manager)
│   └── events.py (copy from preset-manager)
└── utils/
    ├── __init__.py
    └── network.py (copy from preset-manager)

KEY FILES TO MODIFY

preset-manager/sut_client/src/sut_client/service.py
- Add /installed_games endpoint

preset-manager/src/preset_manager/api/sync.py
- Add GemmaPresetRequest, GemmaPresetResponse models
- Add POST /api/sync/gemma-presets endpoint

gemma/modules/discovery_client.py (new)
gemma/modules/preset_manager_client.py (new)
gemma/gui_app_multi_sut.py (major changes)
gemma/config/integration_config.json (new)

---

PORTS

- SUT Discovery Service: 5001
- Preset-Manager: 5000
- SUT Client: 8080
- UDP Discovery Broadcast: 9999

---

DATA FLOW

1. User opens Gemma GUI
2. GUI -> Discovery Service: GET /api/suts (get online SUTs)
3. GUI displays SUTs with checkboxes
4. User selects SUTs, games, PPG preset (1080p high)
5. User clicks "Validate" (optional)
6. GUI -> Discovery Service: GET /api/suts/{id}/games (for each SUT)
7. GUI shows which games are installed/missing
8. User clicks "Start Automation"
9. GUI -> Preset-Manager: POST /api/sync/gemma-presets
10. Preset-Manager -> SUT Client: GET /installed_games (verify installation)
11. Preset-Manager -> SUT Client: POST /apply-preset (for each game)
12. Preset-Manager -> Gemma: Response with successful/failed/skipped
13. GUI shows "Preset applied to X games, Y failed, Z skipped"
14. GUI filters game list to successful only
15. GUI starts automation on filtered games
16. Automation uses existing SUTController flow
