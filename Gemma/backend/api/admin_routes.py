# -*- coding: utf-8 -*-
"""
Admin API routes for comprehensive settings management.
Shares configuration with Service Manager (~/.gemma/service_manager_config.json)
"""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from flask import Blueprint, request, jsonify
import yaml
import requests
from PIL import Image
from io import BytesIO

# Steam header image dimensions (standard format)
HEADER_WIDTH = 460
HEADER_HEIGHT = 215
HEADER_ASPECT = HEADER_WIDTH / HEADER_HEIGHT  # ~2.14

logger = logging.getLogger(__name__)

# Config file location (shared with Service Manager)
CONFIG_DIR = Path.home() / ".gemma"
CONFIG_FILE = CONFIG_DIR / "service_manager_config.json"

# Game configs directory
GAMES_CONFIG_DIR = Path(__file__).parent.parent.parent / "config" / "games"
GAME_IMAGES_DIR = Path(__file__).parent.parent.parent / "admin" / "public" / "game-images"


def get_default_config() -> Dict[str, Any]:
    """Return default configuration structure"""
    return {
        "version": "1.0",
        "project_dir": "",
        "omniparser_dir": "",
        "services": {
            "sut-discovery": {"host": "localhost", "port": 5001, "enabled": True, "remote": False, "env_vars": {}},
            "queue-service": {"host": "localhost", "port": 9000, "enabled": True, "remote": False, "env_vars": {}},
            "gemma-backend": {"host": "localhost", "port": 5000, "enabled": True, "remote": False, "env_vars": {}},
            "gemma-frontend": {"host": "localhost", "port": 3000, "enabled": True, "remote": False, "env_vars": {}},
            "preset-manager": {"host": "localhost", "port": 5002, "enabled": True, "remote": False, "env_vars": {}},
            "pm-frontend": {"host": "localhost", "port": 3001, "enabled": True, "remote": False, "env_vars": {}},
            "sut-client": {"host": "localhost", "port": 8080, "enabled": True, "remote": True, "env_vars": {}},
        },
        "profiles": {
            "local": {"description": "All services on localhost", "overrides": {}}
        },
        "active_profile": "local",
        "omniparser_servers": [],
        "omniparser_instance_count": 0,
        "steam_account_pairs": [],
        "steam_login_timeout": 180,
        "discovery_settings": {
            "scan_interval": 60,
            "timeout": 3,
            "offline_timeout": 30,
            "stale_timeout": 300,
            "udp_port": 9999,
            "paired_interval": 0.5,
            "network_ranges": [],
            "manual_targets": [],
        },
        "automation_settings": {
            "startup_wait": 80,
            "benchmark_duration": 100,
            "screenshot_interval": 5,
            "retry_count": 3,
            "step_timeout": 60,
            "process_detection_timeout": 120,
        },
    }


def load_config() -> Dict[str, Any]:
    """Load configuration from JSON file"""
    if not CONFIG_FILE.exists():
        return get_default_config()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        # Merge with defaults to ensure all keys exist
        default = get_default_config()
        for key, value in default.items():
            if key not in config:
                config[key] = value
            elif isinstance(value, dict) and isinstance(config.get(key), dict):
                for subkey, subvalue in value.items():
                    if subkey not in config[key]:
                        config[key][subkey] = subvalue
        return config
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading config: {e}")
        return get_default_config()


def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to JSON file"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return True
    except IOError as e:
        logger.error(f"Error saving config: {e}")
        return False


def deep_merge(base: Dict, updates: Dict) -> Dict:
    """Deep merge updates into base dict"""
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# Create Blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


# ============================================================================
# Configuration Endpoints
# ============================================================================

@admin_bp.route('/config', methods=['GET'])
def get_config():
    """Get full configuration"""
    try:
        config = load_config()
        # Mask passwords in response
        safe_config = config.copy()
        if 'steam_account_pairs' in safe_config:
            safe_config['steam_account_pairs'] = [
                {**pair, 'af_password': '***', 'gz_password': '***'}
                for pair in safe_config.get('steam_account_pairs', [])
            ]
        return jsonify(safe_config)
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/config', methods=['PUT'])
def update_config():
    """Update configuration (partial update)"""
    try:
        updates = request.get_json()
        if not updates:
            return jsonify({"error": "No data provided"}), 400

        config = load_config()
        config = deep_merge(config, updates)

        if save_config(config):
            return jsonify({"status": "ok", "message": "Configuration saved"})
        else:
            return jsonify({"error": "Failed to save configuration"}), 500
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/config/reset', methods=['POST'])
def reset_config():
    """Reset configuration to defaults"""
    try:
        config = get_default_config()
        if save_config(config):
            return jsonify({"status": "ok", "message": "Configuration reset to defaults"})
        else:
            return jsonify({"error": "Failed to save configuration"}), 500
    except Exception as e:
        logger.error(f"Error resetting config: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Service Management Endpoints
# ============================================================================

@admin_bp.route('/services', methods=['GET'])
def get_services():
    """Get all service configurations with status"""
    try:
        config = load_config()
        services = config.get('services', {})

        # Check health for each service
        result = {}
        for name, settings in services.items():
            host = settings.get('host', 'localhost')
            port = settings.get('port', 0)
            status = 'unknown'

            if settings.get('enabled', True) and port > 0:
                try:
                    url = f"http://{host}:{port}/api/health"
                    if name == 'gemma-frontend' or name == 'pm-frontend':
                        url = f"http://{host}:{port}/"
                    resp = requests.get(url, timeout=2)
                    status = 'online' if resp.ok else 'error'
                except requests.RequestException:
                    status = 'offline'
            elif not settings.get('enabled', True):
                status = 'disabled'

            result[name] = {**settings, 'status': status}

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting services: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/services/<name>', methods=['GET'])
def get_service(name: str):
    """Get single service configuration with status"""
    try:
        config = load_config()
        services = config.get('services', {})

        if name not in services:
            return jsonify({"error": f"Service '{name}' not found"}), 404

        settings = services[name]
        host = settings.get('host', 'localhost')
        port = settings.get('port', 0)
        status = 'unknown'

        if settings.get('enabled', True) and port > 0:
            try:
                url = f"http://{host}:{port}/api/health"
                resp = requests.get(url, timeout=2)
                status = 'online' if resp.ok else 'error'
            except requests.RequestException:
                status = 'offline'
        elif not settings.get('enabled', True):
            status = 'disabled'

        return jsonify({**settings, 'name': name, 'status': status})
    except Exception as e:
        logger.error(f"Error getting service {name}: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/services/<name>', methods=['PUT'])
def update_service(name: str):
    """Update single service configuration"""
    try:
        updates = request.get_json()
        if not updates:
            return jsonify({"error": "No data provided"}), 400

        config = load_config()
        if 'services' not in config:
            config['services'] = {}

        if name not in config['services']:
            config['services'][name] = {}

        config['services'][name] = {**config['services'][name], **updates}

        if save_config(config):
            return jsonify({"status": "ok", "message": f"Service '{name}' updated"})
        else:
            return jsonify({"error": "Failed to save configuration"}), 500
    except Exception as e:
        logger.error(f"Error updating service {name}: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/services/<name>/restart', methods=['POST'])
def restart_service(name: str):
    """Request service restart (handled by Service Manager)"""
    try:
        # Write restart request to a file that Service Manager watches
        restart_file = CONFIG_DIR / "restart_requests.json"

        requests_data = []
        if restart_file.exists():
            try:
                with open(restart_file, "r") as f:
                    requests_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                requests_data = []

        # Add new restart request
        import time
        requests_data.append({
            "service": name,
            "timestamp": time.time(),
            "source": "admin_api"
        })

        # Keep only last 10 requests
        requests_data = requests_data[-10:]

        with open(restart_file, "w") as f:
            json.dump(requests_data, f)

        return jsonify({
            "status": "ok",
            "message": f"Restart request for '{name}' queued",
            "note": "Service Manager will process this request"
        })
    except Exception as e:
        logger.error(f"Error requesting restart for {name}: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/services/<name>/status', methods=['GET'])
def get_service_status(name: str):
    """Get service health status"""
    try:
        config = load_config()
        services = config.get('services', {})

        if name not in services:
            return jsonify({"error": f"Service '{name}' not found"}), 404

        settings = services[name]
        host = settings.get('host', 'localhost')
        port = settings.get('port', 0)

        result = {
            "name": name,
            "enabled": settings.get('enabled', True),
            "host": host,
            "port": port,
            "status": "unknown",
            "response_time": None,
            "details": None
        }

        if not settings.get('enabled', True):
            result["status"] = "disabled"
            return jsonify(result)

        if port <= 0:
            result["status"] = "no_port"
            return jsonify(result)

        try:
            import time
            url = f"http://{host}:{port}/api/health"
            start = time.time()
            resp = requests.get(url, timeout=5)
            result["response_time"] = round((time.time() - start) * 1000, 2)
            result["status"] = "online" if resp.ok else "error"
            if resp.ok:
                try:
                    result["details"] = resp.json()
                except Exception:
                    pass
        except requests.Timeout:
            result["status"] = "timeout"
        except requests.ConnectionError:
            result["status"] = "offline"
        except Exception as e:
            result["status"] = "error"
            result["details"] = str(e)

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting status for {name}: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Game Configuration Endpoints
# ============================================================================

@admin_bp.route('/games', methods=['GET'])
def list_games():
    """List all game configurations"""
    try:
        games = []
        if GAMES_CONFIG_DIR.exists():
            for yaml_file in GAMES_CONFIG_DIR.glob("*.yaml"):
                if yaml_file.name == "ui_flow.yaml":
                    continue  # Skip UI flow config
                try:
                    with open(yaml_file, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    metadata = data.get("metadata", {})
                    games.append({
                        "filename": yaml_file.name,
                        "name": yaml_file.stem,
                        "game_name": metadata.get("game_name", yaml_file.stem),
                        "steam_app_id": metadata.get("steam_app_id"),
                        "preset_id": metadata.get("preset_id"),
                        "display_name": metadata.get("display_name"),
                    })
                except Exception as e:
                    logger.warning(f"Error reading {yaml_file}: {e}")
                    games.append({
                        "filename": yaml_file.name,
                        "name": yaml_file.stem,
                        "error": str(e)
                    })

        return jsonify({"games": games, "count": len(games)})
    except Exception as e:
        logger.error(f"Error listing games: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/games/<name>/yaml', methods=['GET'])
def get_game_yaml(name: str):
    """Get raw YAML content for a game"""
    try:
        yaml_file = GAMES_CONFIG_DIR / f"{name}.yaml"
        if not yaml_file.exists():
            return jsonify({"error": f"Game '{name}' not found"}), 404

        with open(yaml_file, "r", encoding="utf-8") as f:
            content = f.read()

        return jsonify({
            "name": name,
            "filename": yaml_file.name,
            "content": content,
            "path": str(yaml_file)
        })
    except Exception as e:
        logger.error(f"Error reading game {name}: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/games/<name>/yaml', methods=['PUT'])
def update_game_yaml(name: str):
    """Update YAML content for a game"""
    try:
        data = request.get_json()
        if not data or 'content' not in data:
            return jsonify({"error": "No content provided"}), 400

        content = data['content']

        # Validate YAML syntax
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            return jsonify({"error": f"Invalid YAML: {e}"}), 400

        yaml_file = GAMES_CONFIG_DIR / f"{name}.yaml"

        # Create backup
        if yaml_file.exists():
            backup_file = yaml_file.with_suffix('.yaml.bak')
            shutil.copy(yaml_file, backup_file)

        with open(yaml_file, "w", encoding="utf-8") as f:
            f.write(content)

        return jsonify({
            "status": "ok",
            "message": f"Game '{name}' saved",
            "backup": f"{name}.yaml.bak" if yaml_file.exists() else None
        })
    except Exception as e:
        logger.error(f"Error updating game {name}: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/games', methods=['POST'])
def create_game():
    """Create a new game configuration"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        name = data.get('name')
        content = data.get('content')

        if not name:
            return jsonify({"error": "Game name required"}), 400

        # Sanitize name (slug format)
        name = name.lower().replace(' ', '-').replace('_', '-')
        name = ''.join(c for c in name if c.isalnum() or c == '-')

        yaml_file = GAMES_CONFIG_DIR / f"{name}.yaml"
        if yaml_file.exists():
            return jsonify({"error": f"Game '{name}' already exists"}), 409

        # Use provided content or generate template
        if content:
            try:
                yaml.safe_load(content)
            except yaml.YAMLError as e:
                return jsonify({"error": f"Invalid YAML: {e}"}), 400
        else:
            content = f"""metadata:
  game_name: "{data.get('game_name', name.replace('-', ' ').title())}"
  steam_app_id: "{data.get('steam_app_id', '')}"
  preset_id: "{data.get('preset_id', name)}"
  display_name: "{data.get('display_name', '')}"

process:
  name: ""
  window_title: ""

launch:
  type: steam  # or: exe, custom
  steam_app_id: "{data.get('steam_app_id', '')}"

steps:
  1:
    description: "Press Space to continue"
    target: "Continue"
    wait_before: 2
"""

        with open(yaml_file, "w", encoding="utf-8") as f:
            f.write(content)

        return jsonify({
            "status": "ok",
            "message": f"Game '{name}' created",
            "name": name,
            "filename": f"{name}.yaml"
        }), 201
    except Exception as e:
        logger.error(f"Error creating game: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/games/<name>', methods=['DELETE'])
def delete_game(name: str):
    """Delete a game configuration"""
    try:
        yaml_file = GAMES_CONFIG_DIR / f"{name}.yaml"
        if not yaml_file.exists():
            return jsonify({"error": f"Game '{name}' not found"}), 404

        # Create backup before deletion
        backup_dir = GAMES_CONFIG_DIR / "backup"
        backup_dir.mkdir(exist_ok=True)

        import time
        timestamp = int(time.time())
        backup_file = backup_dir / f"{name}.{timestamp}.yaml"
        shutil.copy(yaml_file, backup_file)

        yaml_file.unlink()

        return jsonify({
            "status": "ok",
            "message": f"Game '{name}' deleted",
            "backup": str(backup_file)
        })
    except Exception as e:
        logger.error(f"Error deleting game {name}: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# YAML Validation Endpoint
# ============================================================================

@admin_bp.route('/validate-yaml', methods=['POST'])
def validate_yaml():
    """Validate YAML syntax"""
    try:
        data = request.get_json()
        if not data or 'content' not in data:
            return jsonify({"error": "No content provided"}), 400

        content = data['content']

        try:
            parsed = yaml.safe_load(content)

            # Basic structure validation for game configs
            warnings = []
            if isinstance(parsed, dict):
                if 'metadata' not in parsed:
                    warnings.append("Missing 'metadata' section")
                if 'steps' not in parsed:
                    warnings.append("Missing 'steps' section")
                if 'process' not in parsed:
                    warnings.append("Missing 'process' section")

            return jsonify({
                "valid": True,
                "warnings": warnings,
                "parsed_keys": list(parsed.keys()) if isinstance(parsed, dict) else None
            })
        except yaml.YAMLError as e:
            # Extract line number from error
            line = None
            if hasattr(e, 'problem_mark') and e.problem_mark:
                line = e.problem_mark.line + 1

            return jsonify({
                "valid": False,
                "error": str(e),
                "line": line
            })
    except Exception as e:
        logger.error(f"Error validating YAML: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Profile Management Endpoints
# ============================================================================

@admin_bp.route('/profiles', methods=['GET'])
def get_profiles():
    """Get all profiles"""
    try:
        config = load_config()
        profiles = config.get('profiles', {})
        active = config.get('active_profile', 'local')

        result = []
        for name, data in profiles.items():
            result.append({
                "name": name,
                "description": data.get('description', ''),
                "overrides": data.get('overrides', {}),
                "is_active": name == active,
                "is_default": name == 'local'
            })

        return jsonify({"profiles": result, "active_profile": active})
    except Exception as e:
        logger.error(f"Error getting profiles: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/profiles/<name>', methods=['PUT'])
def update_profile(name: str):
    """Create or update a profile"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        config = load_config()
        if 'profiles' not in config:
            config['profiles'] = {}

        config['profiles'][name] = {
            "description": data.get('description', ''),
            "overrides": data.get('overrides', {})
        }

        if save_config(config):
            return jsonify({"status": "ok", "message": f"Profile '{name}' saved"})
        else:
            return jsonify({"error": "Failed to save configuration"}), 500
    except Exception as e:
        logger.error(f"Error updating profile {name}: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/profiles/<name>', methods=['DELETE'])
def delete_profile(name: str):
    """Delete a profile (cannot delete 'local')"""
    try:
        if name == 'local':
            return jsonify({"error": "Cannot delete default 'local' profile"}), 400

        config = load_config()
        profiles = config.get('profiles', {})

        if name not in profiles:
            return jsonify({"error": f"Profile '{name}' not found"}), 404

        del config['profiles'][name]

        # Switch to local if deleting active profile
        if config.get('active_profile') == name:
            config['active_profile'] = 'local'

        if save_config(config):
            return jsonify({"status": "ok", "message": f"Profile '{name}' deleted"})
        else:
            return jsonify({"error": "Failed to save configuration"}), 500
    except Exception as e:
        logger.error(f"Error deleting profile {name}: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/profiles/<name>/activate', methods=['POST'])
def activate_profile(name: str):
    """Activate a profile"""
    try:
        config = load_config()
        profiles = config.get('profiles', {})

        if name not in profiles:
            return jsonify({"error": f"Profile '{name}' not found"}), 404

        config['active_profile'] = name

        if save_config(config):
            return jsonify({
                "status": "ok",
                "message": f"Profile '{name}' activated",
                "restart_required": True
            })
        else:
            return jsonify({"error": "Failed to save configuration"}), 500
    except Exception as e:
        logger.error(f"Error activating profile {name}: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# OmniParser Settings Endpoints
# ============================================================================

@admin_bp.route('/omniparser', methods=['GET'])
def get_omniparser_settings():
    """Get OmniParser settings"""
    try:
        config = load_config()

        return jsonify({
            "servers": config.get('omniparser_servers', []),
            "instance_count": config.get('omniparser_instance_count', 0),
            "omniparser_dir": config.get('omniparser_dir', '')
        })
    except Exception as e:
        logger.error(f"Error getting OmniParser settings: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/omniparser', methods=['PUT'])
def update_omniparser_settings():
    """Update OmniParser settings"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        config = load_config()

        if 'servers' in data:
            config['omniparser_servers'] = data['servers']
        if 'instance_count' in data:
            config['omniparser_instance_count'] = max(0, min(5, data['instance_count']))
        if 'omniparser_dir' in data:
            config['omniparser_dir'] = data['omniparser_dir']

        if save_config(config):
            return jsonify({
                "status": "ok",
                "message": "OmniParser settings saved",
                "restart_required": True
            })
        else:
            return jsonify({"error": "Failed to save configuration"}), 500
    except Exception as e:
        logger.error(f"Error updating OmniParser settings: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/omniparser/test', methods=['POST'])
def test_omniparser_server():
    """Test connection to an OmniParser server"""
    try:
        data = request.get_json()
        url = data.get('url') if data else None

        if not url:
            return jsonify({"error": "URL required"}), 400

        try:
            import time
            start = time.time()
            resp = requests.get(f"{url.rstrip('/')}/probe", timeout=5)
            response_time = round((time.time() - start) * 1000, 2)

            if resp.ok:
                return jsonify({
                    "status": "online",
                    "response_time": response_time,
                    "details": resp.json() if resp.headers.get('content-type', '').startswith('application/json') else None
                })
            else:
                return jsonify({
                    "status": "error",
                    "error": f"HTTP {resp.status_code}"
                })
        except requests.Timeout:
            return jsonify({"status": "timeout", "error": "Connection timed out"})
        except requests.ConnectionError:
            return jsonify({"status": "offline", "error": "Connection refused"})
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)})
    except Exception as e:
        logger.error(f"Error testing OmniParser: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Steam Accounts Endpoints
# ============================================================================

@admin_bp.route('/steam-accounts', methods=['GET'])
def get_steam_accounts():
    """Get Steam account pairs (passwords masked)"""
    try:
        config = load_config()
        pairs = config.get('steam_account_pairs', [])

        # Mask passwords
        safe_pairs = [
            {**pair, 'af_password': '***' if pair.get('af_password') else '',
             'gz_password': '***' if pair.get('gz_password') else ''}
            for pair in pairs
        ]

        return jsonify({
            "pairs": safe_pairs,
            "login_timeout": config.get('steam_login_timeout', 180)
        })
    except Exception as e:
        logger.error(f"Error getting Steam accounts: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/steam-accounts', methods=['PUT'])
def update_steam_accounts():
    """Update Steam account pairs"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        config = load_config()

        if 'pairs' in data:
            # Preserve existing passwords if new password is '***' (masked)
            existing_pairs = {p.get('name'): p for p in config.get('steam_account_pairs', [])}
            new_pairs = []

            for pair in data['pairs']:
                name = pair.get('name')
                if name in existing_pairs:
                    # Preserve passwords if masked
                    if pair.get('af_password') == '***':
                        pair['af_password'] = existing_pairs[name].get('af_password', '')
                    if pair.get('gz_password') == '***':
                        pair['gz_password'] = existing_pairs[name].get('gz_password', '')
                new_pairs.append(pair)

            config['steam_account_pairs'] = new_pairs

        if 'login_timeout' in data:
            config['steam_login_timeout'] = max(30, min(600, data['login_timeout']))

        if save_config(config):
            return jsonify({"status": "ok", "message": "Steam accounts saved"})
        else:
            return jsonify({"error": "Failed to save configuration"}), 500
    except Exception as e:
        logger.error(f"Error updating Steam accounts: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Discovery Settings Endpoints
# ============================================================================

@admin_bp.route('/discovery', methods=['GET'])
def get_discovery_settings():
    """Get discovery settings"""
    try:
        config = load_config()
        return jsonify(config.get('discovery_settings', get_default_config()['discovery_settings']))
    except Exception as e:
        logger.error(f"Error getting discovery settings: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/discovery', methods=['PUT'])
def update_discovery_settings():
    """Update discovery settings"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        config = load_config()

        if 'discovery_settings' not in config:
            config['discovery_settings'] = get_default_config()['discovery_settings']

        config['discovery_settings'] = {**config['discovery_settings'], **data}

        if save_config(config):
            return jsonify({
                "status": "ok",
                "message": "Discovery settings saved",
                "restart_required": True
            })
        else:
            return jsonify({"error": "Failed to save configuration"}), 500
    except Exception as e:
        logger.error(f"Error updating discovery settings: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Automation Settings Endpoints
# ============================================================================

@admin_bp.route('/automation', methods=['GET'])
def get_automation_settings():
    """Get automation settings"""
    try:
        config = load_config()
        return jsonify(config.get('automation_settings', get_default_config()['automation_settings']))
    except Exception as e:
        logger.error(f"Error getting automation settings: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/automation', methods=['PUT'])
def update_automation_settings():
    """Update automation settings"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        config = load_config()

        if 'automation_settings' not in config:
            config['automation_settings'] = get_default_config()['automation_settings']

        config['automation_settings'] = {**config['automation_settings'], **data}

        if save_config(config):
            return jsonify({"status": "ok", "message": "Automation settings saved"})
        else:
            return jsonify({"error": "Failed to save configuration"}), 500
    except Exception as e:
        logger.error(f"Error updating automation settings: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Game Image Endpoints
# ============================================================================

def resize_to_header(img: Image.Image) -> Image.Image:
    """Resize and crop image to Steam header format (460x215)"""
    orig_width, orig_height = img.size
    orig_aspect = orig_width / orig_height

    if orig_aspect > HEADER_ASPECT:
        # Image is wider than target - crop sides
        new_width = int(orig_height * HEADER_ASPECT)
        left = (orig_width - new_width) // 2
        img = img.crop((left, 0, left + new_width, orig_height))
    elif orig_aspect < HEADER_ASPECT:
        # Image is taller than target - crop top/bottom (keep center-top focus)
        new_height = int(orig_width / HEADER_ASPECT)
        # Bias toward top of image (usually more important content)
        top = int((orig_height - new_height) * 0.3)
        img = img.crop((0, top, orig_width, top + new_height))

    # Resize to exact dimensions
    img = img.resize((HEADER_WIDTH, HEADER_HEIGHT), Image.Resampling.LANCZOS)
    return img


@admin_bp.route('/games/<name>/image', methods=['POST'])
def upload_game_image(name: str):
    """Upload a custom image for a game - auto-resizes to Steam header format"""
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        file = request.files['image']
        if not file.filename:
            return jsonify({"error": "No file selected"}), 400

        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in allowed_extensions:
            return jsonify({"error": f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"}), 400

        # Ensure game images directory exists
        GAME_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        # Open and process the image
        img = Image.open(file.stream)

        # Convert to RGB if necessary (for PNG with transparency, etc.)
        if img.mode in ('RGBA', 'P', 'LA'):
            # Create white background for transparent images
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Get original dimensions for logging
        orig_size = img.size

        # Resize to Steam header format
        img = resize_to_header(img)

        # Save as JPG
        image_path = GAME_IMAGES_DIR / f"{name}.jpg"
        img.save(image_path, 'JPEG', quality=90)

        logger.info(f"Saved game image for '{name}' to {image_path} (resized from {orig_size} to {img.size})")
        return jsonify({
            "status": "ok",
            "message": f"Image uploaded and resized for '{name}'",
            "path": str(image_path),
            "original_size": list(orig_size),
            "final_size": [HEADER_WIDTH, HEADER_HEIGHT]
        })
    except Exception as e:
        logger.error(f"Error uploading image for {name}: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/games/<name>/image/steam', methods=['POST'])
def fetch_steam_image(name: str):
    """Fetch and save game image from Steam CDN"""
    try:
        data = request.get_json()
        if not data or 'steam_app_id' not in data:
            return jsonify({"error": "No steam_app_id provided"}), 400

        steam_app_id = data['steam_app_id']

        # Steam CDN URL for header images
        steam_url = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/header.jpg"

        # Fetch the image
        response = requests.get(steam_url, timeout=10)
        if response.status_code != 200:
            return jsonify({"error": f"Failed to fetch Steam image (HTTP {response.status_code})"}), 400

        # Ensure game images directory exists
        GAME_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        # Save the image
        image_path = GAME_IMAGES_DIR / f"{name}.jpg"
        with open(image_path, 'wb') as f:
            f.write(response.content)

        logger.info(f"Downloaded Steam image for '{name}' (App ID: {steam_app_id}) to {image_path}")
        return jsonify({
            "status": "ok",
            "message": f"Steam image downloaded for '{name}'",
            "path": str(image_path),
            "steam_app_id": steam_app_id
        })
    except requests.RequestException as e:
        logger.error(f"Error fetching Steam image for {name}: {e}")
        return jsonify({"error": f"Failed to fetch Steam image: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error saving Steam image for {name}: {e}")
        return jsonify({"error": str(e)}), 500
