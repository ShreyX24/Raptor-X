"""
SUT Client Flask Service
HTTP API for receiving preset commands from Master
Supports fast discovery via UDP broadcast and WebSocket connection

Merged with KATANA Gemma v0.2 game launch and input automation features
"""

import logging
import os
import socket
import base64
import io
import re
import time
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from flask import Flask, request, jsonify, send_file
from waitress import serve as waitress_serve
from PIL import ImageGrab

from .config import get_settings
from .backup import BackupService
from .applier import PresetApplier
from .discovery import DiscoveryThread
from .ws_client import WebSocketClientThread
from .input_controller import InputController
from .launcher import launch_game, cancel_launch, terminate_game, get_game_status
from .system import check_process, kill_process
from .steam import login_steam, get_steam_library_folders
from .hardware import set_dpi_awareness, get_screen_resolution

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create Flask application"""
    app = Flask(__name__)
    settings = get_settings()

    # Initialize services
    backup_service = BackupService(settings.backup_dir)
    preset_applier = PresetApplier(backup_service)

    # Initialize input controller (from Gemma v0.2)
    input_controller = InputController()

    @app.route('/status', methods=['GET'])
    def status():
        """Return SUT status for discovery"""
        # Get screen resolution
        screen_width, screen_height = get_screen_resolution()

        # Get game status
        game_status = get_game_status()

        return jsonify({
            "status": "online",
            "unique_id": settings.device_id,  # For manual add feature
            "device_id": settings.device_id,
            "hostname": settings.hostname,
            "version": "0.3.0",
            "gemma_sut_signature": "gemma_sut_v3",
            "capabilities": [
                "preset_application",
                "backup_restore",
                "config_replacement",
                "game_launch",
                "input_automation",
                "basic_clicks",
                "advanced_clicks",
                "hotkeys",
                "text_input",
                "drag",
                "scroll",
                "screenshot",
                "steam_login",
                "process_control",
                "performance_monitoring"
            ],
            "screen": {
                "width": screen_width,
                "height": screen_height
            },
            "game": game_status,
            "timestamp": datetime.now().isoformat()
        })

    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint"""
        return jsonify({"status": "healthy"})

    @app.route('/apply-preset', methods=['POST'])
    def apply_preset():
        """Apply a preset from Master"""
        try:
            data = request.get_json()

            if not data:
                return jsonify({"success": False, "error": "No data provided"}), 400

            game_short_name = data.get('game_short_name')
            preset_level = data.get('preset_level')
            files = data.get('files', [])
            config_files = data.get('config_files', [])
            backup = data.get('backup', True)

            if not game_short_name or not files:
                return jsonify({
                    "success": False,
                    "error": "Missing required fields: game_short_name, files"
                }), 400

            # Apply the preset
            result = preset_applier.apply_preset(
                game_short_name=game_short_name,
                preset_level=preset_level,
                files=files,
                config_files=config_files,
                create_backup=backup
            )

            if result['success']:
                return jsonify({
                    "success": True,
                    "status": "success",
                    "message": f"Applied preset {preset_level} for {game_short_name}",
                    "details": result
                })
            else:
                return jsonify({
                    "success": False,
                    "error": result.get('error', 'Unknown error'),
                    "details": result
                }), 500

        except Exception as e:
            logger.error(f"Error applying preset: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/restore-config', methods=['POST'])
    def restore_config():
        """Restore config from backup"""
        try:
            data = request.get_json()
            game_slug = data.get('game_slug')
            backup_id = data.get('backup_id')  # Optional, uses latest if not provided

            if not game_slug:
                return jsonify({"success": False, "error": "Missing game_slug"}), 400

            result = backup_service.restore_backup(game_slug, backup_id)

            return jsonify(result)

        except Exception as e:
            logger.error(f"Error restoring config: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/backups', methods=['GET'])
    def list_backups():
        """List all backups"""
        try:
            game_slug = request.args.get('game')
            backups = backup_service.list_backups(game_slug)
            return jsonify({"success": True, "backups": backups})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/info', methods=['GET'])
    def info():
        """Get SUT information"""
        return jsonify({
            "device_id": settings.device_id,
            "hostname": settings.hostname,
            "port": settings.port,
            "version": "0.3.0",
            "backup_dir": str(settings.backup_dir),
            "max_backups": settings.max_backups_per_game
        })

    @app.route('/screen_info', methods=['GET'])
    def screen_info():
        """
        Get screen resolution information.
        Required by Gemma automation NetworkManager.
        """
        screen_width, screen_height = get_screen_resolution()
        return jsonify({
            "status": "success",
            "screen_width": screen_width,
            "screen_height": screen_height
        })

    @app.route('/installed_games', methods=['GET'])
    def installed_games():
        """
        Scan Steam library folders and return installed games.
        Used by Discovery Service to get game inventory on SUT.
        """
        try:
            libraries = get_steam_library_folders()
            installed = []

            for lib in libraries:
                steamapps = os.path.join(lib, "steamapps")
                if not os.path.exists(steamapps):
                    continue

                for filename in os.listdir(steamapps):
                    if filename.startswith("appmanifest_") and filename.endswith(".acf"):
                        app_id = filename.replace("appmanifest_", "").replace(".acf", "")
                        manifest_path = os.path.join(steamapps, filename)

                        try:
                            with open(manifest_path, 'r', encoding='utf-8') as f:
                                content = f.read()

                            # Parse name
                            name_match = re.search(r'"name"\s+"([^"]+)"', content)
                            installdir_match = re.search(r'"installdir"\s+"([^"]+)"', content)

                            if name_match and installdir_match:
                                game_name = name_match.group(1)
                                install_dir = installdir_match.group(1)
                                full_path = os.path.join(steamapps, "common", install_dir)

                                installed.append({
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
                "games": installed,
                "count": len(installed),
                "libraries_scanned": len(libraries)
            })

        except Exception as e:
            logger.error(f"Error getting installed games: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    # =========================================================================
    # GAME LAUNCH ENDPOINTS (from KATANA Gemma v0.2)
    # =========================================================================

    @app.route('/launch', methods=['POST'])
    def launch():
        """
        Launch a game with window detection.

        Request body:
        {
            "steam_app_id": "1234567",  # Optional: Steam App ID
            "exe_path": "C:/path/to/game.exe",  # Optional: Direct exe path
            "path": "C:/path/to/game.exe",  # Optional: Legacy Gemma NetworkManager format
            "process_name": "game.exe",  # Optional: Process to detect
            "force_relaunch": false,  # Optional: Kill existing and relaunch
            "launch_args": "-benchmark test.xml"  # Optional: Command-line args for game
        }
        """
        try:
            data = request.get_json() or {}

            steam_app_id = data.get('steam_app_id')
            exe_path = data.get('exe_path')
            # Support legacy 'path' parameter from Gemma NetworkManager
            legacy_path = data.get('path')
            # Support both 'process_name' and 'process_id' (Gemma sends process_id)
            process_name = data.get('process_name') or data.get('process_id')
            force_relaunch = data.get('force_relaunch', False)
            startup_wait = data.get('startup_wait', 30)  # Default 30 seconds
            launch_args = data.get('launch_args')  # Command-line arguments for game

            # Handle legacy 'path' parameter - could be exe path or Steam App ID
            if not steam_app_id and not exe_path and legacy_path:
                # Check if it's a numeric Steam App ID
                if str(legacy_path).isdigit():
                    steam_app_id = str(legacy_path)
                    logger.info(f"Legacy path detected as Steam App ID: {steam_app_id}")
                else:
                    exe_path = legacy_path
                    logger.info(f"Legacy path detected as exe path: {exe_path}")

            if not steam_app_id and not exe_path:
                return jsonify({
                    "status": "error",
                    "message": "Either steam_app_id, exe_path, or path is required"
                }), 400

            if launch_args:
                logger.info(f"Launch args provided: {launch_args}")

            # Map startup_wait to retry behavior
            # startup_wait / retry_interval = retry_count
            retry_interval = 10
            retry_count = max(3, startup_wait // retry_interval)

            result = launch_game(
                steam_app_id=steam_app_id,
                exe_path=exe_path,
                process_name=process_name,
                force_relaunch=force_relaunch,
                settings=settings,
                launch_args=launch_args,
                retry_count=retry_count,
                retry_interval=retry_interval
            )

            return jsonify(result)

        except Exception as e:
            logger.error(f"Launch error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/cancel_launch', methods=['POST'])
    def cancel_launch_route():
        """Cancel an ongoing game launch."""
        try:
            cancel_launch()
            return jsonify({"status": "success", "message": "Launch cancelled"})
        except Exception as e:
            logger.error(f"Cancel launch error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/terminate_game', methods=['POST'])
    def terminate_game_route():
        """Terminate the currently tracked game."""
        try:
            result = terminate_game()
            return jsonify(result)
        except Exception as e:
            logger.error(f"Terminate game error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # =========================================================================
    # INPUT AUTOMATION ENDPOINTS (from KATANA Gemma v0.2)
    # =========================================================================

    @app.route('/action', methods=['POST'])
    def action():
        """
        Unified input action endpoint.

        Request body:
        {
            "action": "click|double_click|hold_click|drag|scroll|key|hotkey|type",
            "x": 100,  # For mouse actions
            "y": 200,
            "button": "left|right|middle",  # For click actions
            "duration": 0.5,  # For hold_click
            "end_x": 300,  # For drag
            "end_y": 400,
            "delta": 3,  # For scroll (positive=up, negative=down)
            "key": "enter",  # For key action
            "keys": ["ctrl", "c"],  # For hotkey action
            "text": "Hello World"  # For type action
        }
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400

            # Accept both 'action' (preset-manager style) and 'type' (Gemma style)
            action_type = data.get('action') or data.get('type')
            if not action_type:
                return jsonify({"status": "error", "message": "Missing 'action' or 'type' field"}), 400

            result = {"status": "success", "action": action_type}

            if action_type == 'click':
                x = data.get('x')
                y = data.get('y')
                button = data.get('button', 'left')
                if x is None or y is None:
                    return jsonify({"status": "error", "message": "click requires x and y"}), 400
                input_controller.click_mouse(x, y, button)
                result["message"] = f"Clicked {button} at ({x}, {y})"

            elif action_type == 'double_click':
                x = data.get('x')
                y = data.get('y')
                button = data.get('button', 'left')
                if x is None or y is None:
                    return jsonify({"status": "error", "message": "double_click requires x and y"}), 400
                input_controller.double_click(x, y, button)
                result["message"] = f"Double-clicked {button} at ({x}, {y})"

            elif action_type == 'hold_click':
                x = data.get('x')
                y = data.get('y')
                duration = data.get('duration', 0.5)
                button = data.get('button', 'left')
                if x is None or y is None:
                    return jsonify({"status": "error", "message": "hold_click requires x and y"}), 400
                input_controller.hold_click(x, y, duration, button)
                result["message"] = f"Held {button} click at ({x}, {y}) for {duration}s"

            elif action_type == 'drag':
                x = data.get('x')
                y = data.get('y')
                end_x = data.get('end_x')
                end_y = data.get('end_y')
                duration = data.get('duration', 0.5)
                button = data.get('button', 'left')
                if None in (x, y, end_x, end_y):
                    return jsonify({"status": "error", "message": "drag requires x, y, end_x, end_y"}), 400
                input_controller.drag(x, y, end_x, end_y, duration, button)
                result["message"] = f"Dragged from ({x}, {y}) to ({end_x}, {end_y})"

            elif action_type == 'scroll':
                x = data.get('x')
                y = data.get('y')
                direction = data.get('direction', 'down')
                clicks = data.get('clicks', data.get('delta', 3))  # Support both clicks and delta
                if x is None or y is None:
                    return jsonify({"status": "error", "message": "scroll requires x and y coordinates"}), 400
                input_controller.scroll(x, y, clicks, direction)
                result["message"] = f"Scrolled {direction} {clicks} times at ({x}, {y})"

            elif action_type == 'key':
                key = data.get('key')
                if not key:
                    return jsonify({"status": "error", "message": "key action requires 'key' field"}), 400
                # Support repeat: count + interval for multiple press-release cycles
                count = data.get('count', 1)
                interval = data.get('interval', 1.0)  # Delay between presses in seconds
                for i in range(count):
                    input_controller.press_key(key)
                    if i < count - 1:  # Don't delay after the last press
                        time.sleep(interval)
                if count > 1:
                    result["message"] = f"Pressed key: {key} x{count} (interval: {interval}s)"
                else:
                    result["message"] = f"Pressed key: {key}"

            elif action_type == 'hold_key':
                key = data.get('key')
                duration = data.get('duration', 0.5)
                if not key:
                    return jsonify({"status": "error", "message": "hold_key requires 'key' field"}), 400
                input_controller.hold_key(key, duration)
                result["message"] = f"Held key {key} for {duration}s"

            elif action_type == 'hotkey':
                keys = data.get('keys', [])
                if not keys:
                    return jsonify({"status": "error", "message": "hotkey requires 'keys' array"}), 400
                input_controller.press_hotkey(*keys)
                result["message"] = f"Pressed hotkey: {'+'.join(keys)}"

            elif action_type == 'type':
                text = data.get('text', '')
                if not text:
                    return jsonify({"status": "error", "message": "type requires 'text' field"}), 400
                interval = data.get('interval', 0.02)
                input_controller.type_text(text, interval)
                result["message"] = f"Typed {len(text)} characters"

            elif action_type == 'move':
                x = data.get('x')
                y = data.get('y')
                if x is None or y is None:
                    return jsonify({"status": "error", "message": "move requires x and y"}), 400
                input_controller.move_mouse(x, y)
                result["message"] = f"Moved mouse to ({x}, {y})"

            elif action_type == 'wait':
                duration = data.get('duration', 1.0)
                time.sleep(duration)
                result["message"] = f"Waited {duration} seconds"

            else:
                return jsonify({
                    "status": "error",
                    "message": f"Unknown action: {action_type}",
                    "valid_actions": ["click", "double_click", "hold_click", "drag", "scroll",
                                      "key", "hold_key", "hotkey", "type", "move", "wait"]
                }), 400

            return jsonify(result)

        except Exception as e:
            logger.error(f"Action error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/screenshot', methods=['GET'])
    def screenshot():
        """
        Take a screenshot and return as PNG image.

        Query params:
        - region: x,y,width,height (optional, full screen if not provided)
        - format: png|base64 (default: png)
        """
        try:
            region_str = request.args.get('region')
            output_format = request.args.get('format', 'png')

            if region_str:
                parts = [int(x) for x in region_str.split(',')]
                if len(parts) == 4:
                    x, y, w, h = parts
                    region = (x, y, x + w, y + h)
                else:
                    return jsonify({"status": "error", "message": "Invalid region format"}), 400
            else:
                region = None

            # Capture screenshot
            img = ImageGrab.grab(bbox=region)

            if output_format == 'base64':
                # Return as base64 JSON
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                buffer.seek(0)
                img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                return jsonify({
                    "status": "success",
                    "image": img_base64,
                    "width": img.width,
                    "height": img.height
                })
            else:
                # Return as PNG file
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                buffer.seek(0)
                return send_file(buffer, mimetype='image/png')

        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # =========================================================================
    # PROCESS CONTROL ENDPOINTS (from KATANA Gemma v0.2)
    # =========================================================================

    @app.route('/check_process', methods=['POST'])
    def check_process_route():
        """
        Check if a process is running.

        Request body:
        {
            "process_name": "game.exe"
        }
        """
        try:
            data = request.get_json() or {}
            process_name = data.get('process_name')

            if not process_name:
                return jsonify({"status": "error", "message": "Missing process_name"}), 400

            result = check_process(process_name)
            return jsonify(result)

        except Exception as e:
            logger.error(f"Check process error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/kill_process', methods=['POST'])
    @app.route('/kill', methods=['POST'])  # Alias for convenience
    def kill_process_route():
        """
        Kill a process by name.

        Endpoints: /kill_process, /kill

        Request body:
        {
            "process_name": "game.exe"
        }
        """
        try:
            data = request.get_json() or {}
            process_name = data.get('process_name')

            if not process_name:
                return jsonify({"status": "error", "message": "Missing process_name"}), 400

            result = kill_process(process_name)
            return jsonify(result)

        except Exception as e:
            logger.error(f"Kill process error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # =========================================================================
    # STEAM ENDPOINTS (from KATANA Gemma v0.2)
    # =========================================================================

    @app.route('/login_steam', methods=['POST'])
    def login_steam_route():
        """
        Login to Steam with provided credentials.

        Request body:
        {
            "username": "steam_username",
            "password": "steam_password",
            "timeout": 60  # Optional
        }
        """
        try:
            data = request.get_json() or {}
            username = data.get('username')
            password = data.get('password')
            timeout = data.get('timeout', 60)

            if not username or not password:
                return jsonify({
                    "status": "error",
                    "message": "Missing username or password"
                }), 400

            result = login_steam(username, password, timeout)
            return jsonify(result)

        except Exception as e:
            logger.error(f"Steam login error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    return app


def _parse_master_address(master_str: str) -> tuple:
    """Parse master address from IP:PORT string"""
    if ':' in master_str:
        parts = master_str.split(':')
        return parts[0], int(parts[1])
    else:
        # Default to port 5000 if not specified
        return master_str, 5000


def _ensure_firewall_rule(port: int, rule_name: str = "SUT Client") -> bool:
    """
    Ensure Windows Firewall rule exists for the SUT client port.
    Creates the rule if it doesn't exist (requires admin privileges).

    Returns True if rule exists or was created, False otherwise.
    """
    import subprocess
    import sys

    # Check if rule already exists
    check_cmd = f'netsh advfirewall firewall show rule name="{rule_name}" >nul 2>&1'
    result = subprocess.run(check_cmd, shell=True, capture_output=True)

    if result.returncode == 0:
        logger.info(f"Firewall rule '{rule_name}' already exists")
        return True

    # Try to create the rule (requires admin)
    logger.info(f"Creating firewall rule '{rule_name}' for port {port}...")

    # Get the Python executable path for the rule
    python_exe = sys.executable

    # Create inbound rule for the port
    create_cmd = (
        f'netsh advfirewall firewall add rule name="{rule_name}" '
        f'dir=in action=allow protocol=tcp localport={port} '
        f'enable=yes profile=any'
    )

    result = subprocess.run(create_cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        logger.info(f"Firewall rule created successfully for port {port}")
        return True
    else:
        logger.warning(
            f"Could not create firewall rule (needs admin). "
            f"Run once as Administrator or manually add rule:\n"
            f"  {create_cmd}"
        )
        return False


def start_service(master_override: Optional[str] = None):
    """Start the SUT client service

    Args:
        master_override: Optional master server address (IP:PORT) to connect directly,
                        bypassing UDP discovery. Useful for cross-subnet deployments.
    """
    settings = get_settings()

    logger.info("=" * 60)
    logger.info("PML SUT Client")
    logger.info("=" * 60)
    logger.info(f"Device ID: {settings.device_id}")
    logger.info(f"Hostname: {settings.hostname}")
    logger.info(f"Port: {settings.port}")
    logger.info(f"Backup Dir: {settings.backup_dir}")
    if master_override:
        logger.info(f"Master Override: {master_override}")
    logger.info("=" * 60)

    # Ensure firewall rule exists (avoids UAC prompt on subsequent runs)
    _ensure_firewall_rule(settings.port, rule_name="SUT Client")

    # Create Flask app
    app = create_app()

    # WebSocket client reference (created after discovery)
    ws_thread: Optional[WebSocketClientThread] = None

    def on_master_found(master_info: Dict[str, Any]):
        """Callback when Master is discovered via UDP"""
        nonlocal ws_thread

        master_ip = master_info.get("ip")
        master_port = master_info.get("ws_port", master_info.get("api_port", 5000))

        logger.info(f"Master discovered: {master_ip}:{master_port}")

        # Start or update WebSocket connection
        if ws_thread is None or not ws_thread.is_alive():
            ws_thread = WebSocketClientThread(
                sut_id=settings.device_id,
                master_ip=master_ip,
                master_port=master_port,
                on_command=handle_ws_command
            )
            ws_thread.start()
            logger.info("WebSocket client started")
        else:
            # Update Master info for reconnection
            ws_thread.update_master(master_ip, master_port)

    def handle_ws_command(command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle commands received via WebSocket"""
        cmd_type = command.get("type")
        data = command.get("data", {})

        logger.info(f"WebSocket command received: {cmd_type}")

        # Handle different command types
        if cmd_type == "apply_preset":
            # Apply preset command via WebSocket
            backup_service = BackupService(settings.backup_dir)
            preset_applier = PresetApplier(backup_service)

            return preset_applier.apply_preset(
                game_short_name=data.get("game_short_name"),
                preset_level=data.get("preset_level"),
                files=data.get("files", []),
                config_files=data.get("config_files", []),
                create_backup=data.get("backup", True)
            )

        elif cmd_type == "status_request":
            return {
                "status": "ready",
                "device_id": settings.device_id,
                "hostname": settings.hostname
            }

        else:
            logger.warning(f"Unknown WebSocket command: {cmd_type}")
            return {"error": f"Unknown command: {cmd_type}"}

    # Discovery mode: direct connection or UDP discovery
    discovery_thread = None

    if master_override:
        # Direct connection mode - bypass UDP discovery
        master_ip, master_port = _parse_master_address(master_override)
        logger.info(f"Direct connection mode: connecting to {master_ip}:{master_port}")

        # Start WebSocket connection directly
        ws_thread = WebSocketClientThread(
            sut_id=settings.device_id,
            master_ip=master_ip,
            master_port=master_port,
            on_command=handle_ws_command
        )
        ws_thread.start()
        logger.info("WebSocket client started (direct connection)")
    else:
        # Normal UDP discovery mode
        discovery_thread = DiscoveryThread(
            udp_port=9999,
            on_master_found=on_master_found
        )
        discovery_thread.start()
        logger.info("UDP Discovery started - listening for Master broadcast")

    # Run Flask app with Waitress (production WSGI server)
    # Waitress handles concurrent requests properly on Windows
    try:
        logger.info(f"Starting Waitress server on {settings.host}:{settings.port}")
        waitress_serve(
            app,
            host=settings.host,
            port=settings.port,
            threads=8,  # Handle 8 concurrent requests
            channel_timeout=120,  # 2 minute timeout for long-running requests
            connection_limit=100,
        )
    finally:
        # Cleanup on shutdown
        logger.info("Shutting down...")
        if discovery_thread:
            discovery_thread.stop()
        if ws_thread:
            ws_thread.stop()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    start_service()
