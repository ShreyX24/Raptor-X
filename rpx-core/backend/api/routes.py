# -*- coding: utf-8 -*-
"""
REST API routes for the backend system
"""

import logging
import json
import os
import io
import zipfile
import tempfile
from flask import Blueprint, request, jsonify, send_file
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class APIRoutes:
    """API routes handler"""

    def __init__(self, device_registry, discovery_service, sut_client, omniparser_client, websocket_handler, game_manager=None):
        self.device_registry = device_registry
        self.discovery_service = discovery_service
        self.sut_client = sut_client
        self.omniparser_client = omniparser_client
        self.websocket_handler = websocket_handler
        self.game_manager = game_manager

        # External service clients (set by controller when use_external_discovery=True)
        self.use_external_discovery = False
        self.discovery_client = None
        self.queue_client = None
        self.preset_manager_client = None
        
    def register_routes(self, app):
        """Register all API routes with Flask app"""
        
        # System status and health
        @app.route('/api/status', methods=['GET'])
        def get_system_status():
            """Get comprehensive system status"""
            try:
                device_stats = self.device_registry.get_device_stats()
                omniparser_status = self.omniparser_client.get_server_status()

                if self.use_external_discovery:
                    # External microservices mode
                    mode = "external_services"
                    discovery_status = {
                        "running": True,
                        "external": True,
                        "target_ips": 0
                    }
                    # Include external service status
                    services = {
                        "discovery_service": {
                            "available": "online",
                            "url": "http://localhost:5001"
                        },
                        "queue_service": {
                            "available": "online",
                            "url": "http://localhost:9000"
                        },
                        "preset_manager": {
                            "available": "online",
                            "url": "http://localhost:5002"
                        }
                    }
                else:
                    mode = "internal_discovery"
                    ds = self.discovery_service.get_discovery_status()
                    discovery_status = {
                        "running": ds.get("running", False),
                        "external": False,
                        "target_ips": ds.get("target_ips", 0)
                    }
                    services = None

                response = {
                    "backend": {
                        "running": True,
                        "version": "2.0.0",
                        "mode": mode,
                        "uptime": 0,
                        "websocket_clients": self.websocket_handler.get_connected_clients_count()
                    },
                    "discovery": discovery_status,
                    "devices": device_stats,
                    "omniparser": omniparser_status
                }

                if services:
                    response["services"] = services

                return jsonify(response)
            except Exception as e:
                logger.error(f"Error getting system status: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/health', methods=['GET'])
        def health_check():
            """Basic health check endpoint"""
            if self.use_external_discovery:
                return jsonify({
                    "status": "healthy",
                    "mode": "external_services"
                })
            else:
                return jsonify({
                    "status": "healthy",
                    "timestamp": self.discovery_service.get_discovery_status()
                })
            
        # Device management
        @app.route('/api/devices', methods=['GET'])
        def get_devices():
            """Get all discovered devices"""
            try:
                if self.use_external_discovery and self.discovery_client:
                    # Get devices from external Discovery Service
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        suts = loop.run_until_complete(self.discovery_client.get_suts())
                    finally:
                        loop.close()

                    devices_data = []
                    for sut in suts:
                        device_data = {
                            "device_id": sut.get("unique_id", sut.get("device_id")),
                            "ip": sut.get("ip"),
                            "port": sut.get("port", 8080),
                            "hostname": sut.get("hostname"),
                            "status": sut.get("status", "unknown"),
                            "capabilities": sut.get("capabilities", {}),
                            "last_seen": sut.get("last_seen"),
                            "first_discovered": sut.get("first_discovered"),
                            "current_task": sut.get("current_task"),
                            "error_count": sut.get("error_count", 0),
                            "success_rate": sut.get("success_rate", 100.0),
                            "is_paired": sut.get("is_paired", False),
                            "paired_at": sut.get("paired_at"),
                            "paired_by": sut.get("paired_by"),
                            # SSH fields (bidirectional SSH)
                            "ssh_fingerprint": sut.get("ssh_fingerprint"),
                            "master_key_installed": sut.get("master_key_installed", False),
                            "master_key_installed_at": sut.get("master_key_installed_at"),
                            # Binding fields
                            "session_id": sut.get("session_id"),
                            "last_ip_change": sut.get("last_ip_change"),
                        }
                        devices_data.append(device_data)

                    return jsonify({
                        "devices": devices_data,
                        "total_count": len(devices_data),
                        "online_count": len([d for d in devices_data if d.get("status") == "online"]),
                        "source": "discovery_service"
                    })
                else:
                    # Internal device registry
                    devices = self.device_registry.get_all_devices()
                    devices_data = []

                    for device in devices:
                        device_data = {
                            "device_id": device.unique_id,
                            "ip": device.ip,
                            "port": device.port,
                            "hostname": device.hostname,
                            "status": device.status.value,
                            "capabilities": device.capabilities,
                            "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                            "first_discovered": device.first_discovered.isoformat() if device.first_discovered else None,
                            "current_task": device.current_task,
                            "error_count": device.error_count,
                            "success_rate": device.success_rate,
                            "age_seconds": device.age_seconds,
                            "last_seen_seconds": device.last_seen_seconds
                        }
                        devices_data.append(device_data)

                    return jsonify({
                        "devices": devices_data,
                        "total_count": len(devices_data),
                        "online_count": len([d for d in devices if d.is_online]),
                        "source": "internal_registry"
                    })
            except Exception as e:
                logger.error(f"Error getting devices: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/devices/<device_id>', methods=['GET'])
        def get_device_details(device_id):
            """Get detailed information about a specific device"""
            try:
                device = self.device_registry.get_device_by_id(device_id)
                if not device:
                    return jsonify({"error": f"Device {device_id} not found"}), 404
                    
                device_data = {
                    "device_id": device.unique_id,
                    "ip": device.ip,
                    "port": device.port,
                    "hostname": device.hostname,
                    "status": device.status.value,
                    "capabilities": device.capabilities,
                    "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                    "first_discovered": device.first_discovered.isoformat() if device.first_discovered else None,
                    "current_task": device.current_task,
                    "error_count": device.error_count,
                    "total_pings": device.total_pings,
                    "successful_pings": device.successful_pings,
                    "success_rate": device.success_rate,
                    "age_seconds": device.age_seconds,
                    "last_seen_seconds": device.last_seen_seconds
                }
                
                return jsonify(device_data)
            except Exception as e:
                logger.error(f"Error getting device {device_id}: {e}")
                return jsonify({"error": str(e)}), 500
                
        # Discovery management
        @app.route('/api/discovery/scan', methods=['POST'])
        def force_discovery_scan():
            """Force an immediate discovery scan"""
            try:
                if self.use_external_discovery:
                    # External mode - scan is handled by external SUT Discovery Service
                    # SUTs register via WebSocket, no manual scan needed
                    return jsonify({
                        "status": "success",
                        "mode": "external",
                        "message": "Using external SUT Discovery Service - SUTs auto-register via WebSocket"
                    })
                scan_result = self.discovery_service.force_discovery_scan()
                return jsonify({
                    "status": "success",
                    "scan_result": scan_result
                })
            except Exception as e:
                logger.error(f"Error forcing discovery scan: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/discovery/status', methods=['GET'])
        def get_discovery_status():
            """Get discovery service status"""
            try:
                if self.use_external_discovery:
                    # External mode - return info about external service
                    return jsonify({
                        "mode": "external",
                        "service_url": "http://localhost:5001",
                        "message": "Using external SUT Discovery Service"
                    })
                else:
                    status = self.discovery_service.get_discovery_status()
                    return jsonify(status)
            except Exception as e:
                logger.error(f"Error getting discovery status: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/discovery/targets', methods=['POST'])
        def add_discovery_target():
            """Add IP to discovery targets"""
            try:
                data = request.get_json()
                ip = data.get('ip')
                
                if not ip:
                    return jsonify({"error": "IP address required"}), 400
                    
                self.discovery_service.add_target_ip(ip)
                return jsonify({"status": "success", "ip": ip})
            except Exception as e:
                logger.error(f"Error adding discovery target: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/discovery/targets/<ip>', methods=['DELETE'])
        def remove_discovery_target(ip):
            """Remove IP from discovery targets"""
            try:
                self.discovery_service.remove_target_ip(ip)
                return jsonify({"status": "success", "ip": ip})
            except Exception as e:
                logger.error(f"Error removing discovery target: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/discovery/network-info', methods=['GET'])
        def get_network_info():
            """Get comprehensive network information"""
            try:
                from ..discovery.network_utils import NetworkDiscovery
                network_info = NetworkDiscovery.get_network_info()
                return jsonify(network_info)
            except Exception as e:
                logger.error(f"Error getting network info: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/discovery/rediscover-networks', methods=['POST'])
        def rediscover_networks():
            """Force rediscovery of network ranges and restart scanning"""
            try:
                # Reinitialize target IPs with fresh network discovery
                self.discovery_service._initialize_target_ips()
                
                # Force an immediate scan
                stats = self.discovery_service.force_discovery_scan()
                
                return jsonify({
                    "status": "success", 
                    "message": "Network rediscovery completed",
                    "stats": stats
                })
            except Exception as e:
                logger.error(f"Error rediscovering networks: {e}")
                return jsonify({"error": str(e)}), 500
                
        # SUT communication
        @app.route('/api/sut/<device_id>/status', methods=['GET'])
        def get_sut_status(device_id):
            """Get status from a specific SUT"""
            try:
                device = self.device_registry.get_device_by_id(device_id)
                if not device:
                    return jsonify({"error": f"Device {device_id} not found"}), 404
                    
                result = self.sut_client.get_status(device.ip, device.port)
                
                if result.success:
                    return jsonify({
                        "status": "success",
                        "data": result.data,
                        "response_time": result.response_time
                    })
                else:
                    return jsonify({
                        "status": "error",
                        "error": result.error
                    }), 500
                    
            except Exception as e:
                logger.error(f"Error getting SUT status for {device_id}: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/sut/<device_id>/system_info', methods=['GET'])
        def get_sut_system_info(device_id):
            """Get detailed system information from a specific SUT"""
            try:
                device = self.device_registry.get_device_by_id(device_id)
                if not device:
                    return jsonify({"error": f"Device {device_id} not found"}), 404

                result = self.sut_client.get_system_info(device.ip, device.port)

                if result.success:
                    return jsonify({
                        "status": "success",
                        "data": result.data,
                        "response_time": result.response_time
                    })
                else:
                    return jsonify({
                        "status": "error",
                        "error": result.error
                    }), 500

            except Exception as e:
                logger.error(f"Error getting system info for {device_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/sut/by-ip/<ip>/system_info', methods=['GET'])
        def get_sut_system_info_by_ip(ip):
            """Get detailed system information from SUT by IP address"""
            try:
                result = self.sut_client.get_system_info(ip, 8080)

                if result.success:
                    return jsonify({
                        "status": "success",
                        "data": result.data,
                        "response_time": result.response_time
                    })
                else:
                    return jsonify({
                        "status": "error",
                        "error": result.error
                    }), 500

            except Exception as e:
                logger.error(f"Error getting system info for IP {ip}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/sut/<device_id>/screenshot', methods=['GET'])
        def take_sut_screenshot(device_id):
            """Take screenshot from a specific SUT"""
            try:
                device = self.device_registry.get_device_by_id(device_id)

                # If not found by ID, check external discovery service
                if not device and self.use_external_discovery and self.discovery_client:
                    try:
                        suts = self.discovery_client.get_suts_sync()
                        for sut in suts:
                            if sut.get("unique_id") == device_id or sut.get("ip") == device_id:
                                class DeviceProxy:
                                    def __init__(self, data):
                                        self.ip = data.get("ip")
                                        self.port = data.get("port", 8080)
                                device = DeviceProxy(sut)
                                break
                    except Exception as e:
                        logger.warning(f"Discovery service error: {e}")

                if not device:
                    return jsonify({"error": f"Device {device_id} not found"}), 404

                # Create temporary file for screenshot
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                    
                result = self.sut_client.take_screenshot(device.ip, device.port, tmp_path)
                
                if result.success:
                    return send_file(tmp_path, mimetype='image/png')
                else:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                    return jsonify({
                        "status": "error",
                        "error": result.error
                    }), 500
                    
            except Exception as e:
                logger.error(f"Error taking screenshot from {device_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/sut/<device_id>/display/resolutions', methods=['GET'])
        def get_sut_display_resolutions(device_id):
            """Get supported display resolutions from a specific SUT"""
            try:
                import requests as http_requests

                # Find device by ID or IP
                device = self.device_registry.get_device_by_id(device_id)

                # If not found by ID, check external discovery service
                if not device and self.use_external_discovery and self.discovery_client:
                    try:
                        suts = self.discovery_client.get_suts_sync()
                        for sut in suts:
                            if sut.get("unique_id") == device_id or sut.get("ip") == device_id:
                                class DeviceProxy:
                                    def __init__(self, data):
                                        self.ip = data.get("ip")
                                        self.port = data.get("port", 8080)
                                device = DeviceProxy(sut)
                                break
                    except Exception as e:
                        logger.warning(f"Discovery service error: {e}")

                if not device:
                    return jsonify({"error": f"Device {device_id} not found"}), 404

                # Query SUT for supported resolutions
                try:
                    common_only = request.args.get('common_only', 'true').lower() == 'true'
                    url = f"http://{device.ip}:{device.port}/display/resolutions"
                    if common_only:
                        url += "?common_only=true"

                    response = http_requests.get(url, timeout=10)
                    response.raise_for_status()
                    data = response.json()

                    return jsonify({
                        "status": "success",
                        "resolutions": data.get("resolutions", []),
                        "device_id": device_id
                    })

                except http_requests.RequestException as e:
                    logger.error(f"Failed to get resolutions from SUT {device_id}: {e}")
                    return jsonify({
                        "status": "error",
                        "error": f"Failed to connect to SUT: {str(e)}"
                    }), 500

            except Exception as e:
                logger.error(f"Error getting display resolutions for {device_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/sut/<device_id>/action', methods=['POST'])
        def perform_sut_action(device_id):
            """Perform action on a specific SUT"""
            try:
                device = self.device_registry.get_device_by_id(device_id)
                if not device:
                    return jsonify({"error": f"Device {device_id} not found"}), 404
                    
                if not device.is_online:
                    return jsonify({"error": f"Device {device_id} is not online"}), 400
                    
                action_data = request.get_json()
                if not action_data:
                    return jsonify({"error": "Action data required"}), 400
                    
                # Mark device as busy
                self.device_registry.set_device_busy(device_id, f"Performing {action_data.get('type', 'action')}")
                
                try:
                    result = self.sut_client.perform_action(device.ip, device.port, action_data)
                    
                    if result.success:
                        return jsonify({
                            "status": "success",
                            "data": result.data,
                            "response_time": result.response_time
                        })
                    else:
                        return jsonify({
                            "status": "error",
                            "error": result.error
                        }), 500
                        
                finally:
                    # Mark device as available again
                    self.device_registry.set_device_online(device_id)
                    
            except Exception as e:
                logger.error(f"Error performing action on {device_id}: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/sut/<device_id>/launch', methods=['POST'])
        def launch_sut_application(device_id):
            """Launch application on a specific SUT"""
            try:
                device = self.device_registry.get_device_by_id(device_id)
                if not device:
                    return jsonify({"error": f"Device {device_id} not found"}), 404
                    
                if not device.is_online:
                    return jsonify({"error": f"Device {device_id} is not online"}), 400
                    
                launch_data = request.get_json()
                if not launch_data or 'path' not in launch_data:
                    return jsonify({"error": "Application path required"}), 400
                    
                app_path = launch_data['path']
                process_id = launch_data.get('process_id')
                
                result = self.sut_client.launch_application(device.ip, device.port, app_path, process_id)
                
                if result.success:
                    return jsonify({
                        "status": "success",
                        "data": result.data,
                        "response_time": result.response_time
                    })
                else:
                    return jsonify({
                        "status": "error",
                        "error": result.error
                    }), 500
                    
            except Exception as e:
                logger.error(f"Error launching application on {device_id}: {e}")
                return jsonify({"error": str(e)}), 500
                
        # Omniparser integration
        @app.route('/api/omniparser/status', methods=['GET'])
        def get_omniparser_status():
            """Get Omniparser server status"""
            try:
                status = self.omniparser_client.get_server_status()
                return jsonify(status)
            except Exception as e:
                logger.error(f"Error getting Omniparser status: {e}")
                return jsonify({"error": str(e)}), 500
                
        @app.route('/api/omniparser/analyze', methods=['POST'])
        def analyze_with_omniparser():
            """Analyze screenshot with Omniparser"""
            try:
                if 'screenshot' not in request.files:
                    return jsonify({"error": "Screenshot file required"}), 400

                file = request.files['screenshot']
                if file.filename == '':
                    return jsonify({"error": "No file selected"}), 400

                # Extract OCR config from form data
                ocr_config = {}
                if request.form.get('use_paddleocr') is not None:
                    ocr_config['use_paddleocr'] = request.form.get('use_paddleocr').lower() == 'true'
                if request.form.get('text_threshold'):
                    try:
                        ocr_config['text_threshold'] = float(request.form.get('text_threshold'))
                    except ValueError:
                        pass
                if request.form.get('box_threshold'):
                    try:
                        ocr_config['box_threshold'] = float(request.form.get('box_threshold'))
                    except ValueError:
                        pass
                if request.form.get('iou_threshold'):
                    try:
                        ocr_config['iou_threshold'] = float(request.form.get('iou_threshold'))
                    except ValueError:
                        pass

                # Save uploaded file temporarily
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    file.save(tmp_file.name)
                    tmp_path = tmp_file.name

                try:
                    # Pass OCR config if any parameters were provided
                    if ocr_config:
                        result = self.omniparser_client.analyze_screenshot(tmp_path, ocr_config=ocr_config)
                    else:
                        result = self.omniparser_client.analyze_screenshot(tmp_path)
                    
                    if result.success:
                        response_data = {
                            "status": "success",
                            "elements": result.elements,
                            "response_time": result.response_time,
                            "element_count": len(result.elements or [])
                        }
                        
                        # If annotated image is requested, include it
                        # Check both query params and form data for include_annotation
                        include_annotation = request.args.get('include_annotation') == 'true' or request.form.get('include_annotation') == 'true'
                        if include_annotation and result.annotated_image_data:
                            import base64
                            response_data["annotated_image_base64"] = base64.b64encode(result.annotated_image_data).decode('utf-8')
                            
                        return jsonify(response_data)
                    else:
                        return jsonify({
                            "status": "error",
                            "error": result.error
                        }), 500
                        
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                        
            except Exception as e:
                logger.error(f"Error analyzing with Omniparser: {e}")
                return jsonify({"error": str(e)}), 500
                
        # WebSocket client management
        @app.route('/api/websocket/clients', methods=['GET'])
        def get_websocket_clients():
            """Get connected WebSocket clients info"""
            try:
                clients = self.websocket_handler.get_client_info()
                return jsonify({
                    "client_count": len(clients),
                    "clients": clients
                })
            except Exception as e:
                logger.error(f"Error getting WebSocket clients: {e}")
                return jsonify({"error": str(e)}), 500

        # Game configuration management
        @app.route('/api/games', methods=['GET'])
        def get_games():
            """Get all game configurations"""
            try:
                if not self.game_manager:
                    return jsonify({"games": {}})
                
                games = self.game_manager.to_dict()
                return jsonify({"games": games})
            except Exception as e:
                logger.error(f"Error getting games: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/games/<game_name>', methods=['GET'])
        def get_game(game_name):
            """Get specific game configuration"""
            try:
                if not self.game_manager:
                    return jsonify({"error": "Game manager not available"}), 500
                
                game = self.game_manager.get_game(game_name)
                if not game:
                    return jsonify({"error": f"Game '{game_name}' not found"}), 404
                
                return jsonify({"game": game.__dict__})
            except Exception as e:
                logger.error(f"Error getting game {game_name}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/games/reload', methods=['POST'])
        def reload_games():
            """Reload game configurations from disk"""
            try:
                if not self.game_manager:
                    return jsonify({"error": "Game manager not available"}), 500
                
                stats = self.game_manager.reload_configurations()
                
                # Emit updated games to WebSocket clients
                games_data = self.game_manager.to_dict()
                self.websocket_handler.broadcast_message('games_update', games_data)
                
                return jsonify(stats)
            except Exception as e:
                logger.error(f"Error reloading games: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/games/stats', methods=['GET'])
        def get_game_stats():
            """Get game statistics"""
            try:
                if not self.game_manager:
                    return jsonify({"error": "Game manager not available"}), 500

                stats = self.game_manager.get_game_stats()
                return jsonify(stats)
            except Exception as e:
                logger.error(f"Error getting game stats: {e}")
                return jsonify({"error": str(e)}), 500

        # ============== Workflow YAML CRUD Endpoints ==============

        @app.route('/api/workflows', methods=['GET'])
        def list_workflows():
            """Get list of all workflows with summaries for sidebar display"""
            try:
                if not self.game_manager:
                    return jsonify({"workflows": []})

                workflows = self.game_manager.list_workflows()
                return jsonify({"workflows": workflows})
            except Exception as e:
                logger.error(f"Error listing workflows: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/games/<game_name>/yaml', methods=['GET'])
        def get_game_yaml(game_name):
            """Get raw YAML content for a game configuration"""
            try:
                if not self.game_manager:
                    return jsonify({"error": "Game manager not available"}), 500

                yaml_content = self.game_manager.get_game_yaml(game_name)
                if yaml_content is None:
                    return jsonify({"error": f"Game '{game_name}' not found"}), 404

                return jsonify({
                    "game_name": game_name,
                    "yaml": yaml_content
                })
            except Exception as e:
                logger.error(f"Error getting YAML for {game_name}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/games/<game_name>/yaml', methods=['PUT'])
        def save_game_yaml(game_name):
            """Save raw YAML content for an existing game configuration"""
            try:
                if not self.game_manager:
                    return jsonify({"error": "Game manager not available"}), 500

                data = request.get_json()
                if not data or 'yaml' not in data:
                    return jsonify({"error": "Missing 'yaml' in request body"}), 400

                result = self.game_manager.save_game_yaml(game_name, data['yaml'])

                if result['status'] == 'error':
                    return jsonify(result), 400

                # Broadcast update to WebSocket clients
                games_data = self.game_manager.to_dict()
                self.websocket_handler.broadcast_message('games_update', games_data)

                return jsonify(result)
            except Exception as e:
                logger.error(f"Error saving YAML for {game_name}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/games', methods=['POST'])
        def create_game():
            """Create a new game configuration"""
            try:
                if not self.game_manager:
                    return jsonify({"error": "Game manager not available"}), 500

                data = request.get_json()
                if not data:
                    return jsonify({"error": "Missing request body"}), 400

                name = data.get('name')
                yaml_content = data.get('yaml')

                if not name:
                    return jsonify({"error": "Missing 'name' in request body"}), 400
                if not yaml_content:
                    return jsonify({"error": "Missing 'yaml' in request body"}), 400

                result = self.game_manager.create_game(name, yaml_content)

                if result['status'] == 'error':
                    return jsonify(result), 400

                # Broadcast update to WebSocket clients
                games_data = self.game_manager.to_dict()
                self.websocket_handler.broadcast_message('games_update', games_data)

                return jsonify(result), 201
            except Exception as e:
                logger.error(f"Error creating game: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/games/<game_name>', methods=['DELETE'])
        def delete_game(game_name):
            """Delete a game configuration"""
            try:
                if not self.game_manager:
                    return jsonify({"error": "Game manager not available"}), 500

                result = self.game_manager.delete_game(game_name)

                if result['status'] == 'error':
                    return jsonify(result), 400

                # Broadcast update to WebSocket clients
                games_data = self.game_manager.to_dict()
                self.websocket_handler.broadcast_message('games_update', games_data)

                return jsonify(result)
            except Exception as e:
                logger.error(f"Error deleting game {game_name}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/games/<game_name>/validate', methods=['POST'])
        def validate_game_yaml(game_name):
            """Validate YAML content without saving"""
            try:
                if not self.game_manager:
                    return jsonify({"error": "Game manager not available"}), 500

                data = request.get_json()
                if not data or 'yaml' not in data:
                    return jsonify({"error": "Missing 'yaml' in request body"}), 400

                result = self.game_manager.validate_yaml(data['yaml'])
                return jsonify(result)
            except Exception as e:
                logger.error(f"Error validating YAML: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/games/<game_name>/steps', methods=['GET'])
        def get_game_steps(game_name):
            """Get automation steps for a game (for debug mode step selector)"""
            try:
                import yaml as yaml_lib

                if not self.game_manager:
                    return jsonify({"error": "Game manager not available"}), 500

                yaml_content = self.game_manager.get_game_yaml(game_name)
                if yaml_content is None:
                    return jsonify({"error": f"Game '{game_name}' not found"}), 404

                # Parse YAML to extract steps
                config = yaml_lib.safe_load(yaml_content)
                steps_dict = config.get('steps', {})

                # Convert to list format with step number and description
                steps = []
                for step_num in sorted(steps_dict.keys(), key=lambda x: int(x)):
                    step_data = steps_dict[step_num]
                    steps.append({
                        "step": int(step_num),
                        "description": step_data.get('description', f'Step {step_num}'),
                        "action_type": step_data.get('action', {}).get('type', 'unknown'),
                    })

                return jsonify({
                    "game_name": game_name,
                    "total_steps": len(steps),
                    "steps": steps
                })
            except Exception as e:
                logger.error(f"Error getting steps for {game_name}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/games/<game_name>/check-availability', methods=['GET'])
        def check_game_availability(game_name):
            """
            Check if a game is available (installed) on a specific SUT.
            Fast path: Direct SUT query for Steam App ID/name matching.
            Fallback: Preset-manager for abbreviation matching (e.g., ffxiv).

            Query Parameters:
                sut_ip: IP address of the SUT to check

            Returns:
                {
                    "available": true/false,
                    "game_name": "Shadow of the Tomb Raider",
                    "steam_app_id": "750920",
                    "install_path": "D:\\Games\\SOTR",
                    "sut_ip": "192.168.0.103",
                    "match_method": "steam_app_id" | "name" | null
                }
            """
            try:
                import requests as http_requests

                sut_ip = request.args.get('sut_ip')
                if not sut_ip:
                    return jsonify({"error": "sut_ip query parameter required"}), 400

                # Get game config to get steam_app_id
                if not self.game_manager:
                    return jsonify({"error": "Game manager not available"}), 500

                game_config = self.game_manager.get_game(game_name)
                if not game_config:
                    return jsonify({"error": f"Game '{game_name}' not found in configuration"}), 404

                config_steam_app_id = getattr(game_config, 'steam_app_id', None)

                # FAST PATH: Query SUT directly for installed games
                try:
                    response = http_requests.get(
                        f"http://{sut_ip}:8080/installed_games",
                        timeout=5
                    )

                    if response.status_code != 200:
                        return jsonify({
                            "available": False,
                            "game_name": game_name,
                            "steam_app_id": config_steam_app_id,
                            "sut_ip": sut_ip,
                            "error": f"SUT returned status {response.status_code}",
                            "match_method": None
                        })

                    data = response.json()
                    installed_games = data.get("games", [])

                    # PRIORITY 1: Match by Steam App ID (fastest, most reliable)
                    if config_steam_app_id:
                        for game in installed_games:
                            sut_app_id = game.get("steam_app_id")
                            if sut_app_id and str(sut_app_id) == str(config_steam_app_id):
                                if game.get("exists", True):
                                    logger.info(f"Game '{game_name}' available on SUT {sut_ip} via steam_app_id {config_steam_app_id}")
                                    return jsonify({
                                        "available": True,
                                        "game_name": game.get("name", game_name),
                                        "steam_app_id": str(config_steam_app_id),
                                        "install_path": game.get("install_path"),
                                        "sut_ip": sut_ip,
                                        "match_method": "steam_app_id"
                                    })

                    # PRIORITY 2: Match by game name substring
                    game_name_lower = game_name.lower()
                    for game in installed_games:
                        installed_name = game.get("name", "").lower()
                        if game_name_lower in installed_name or installed_name in game_name_lower:
                            if game.get("exists", True):
                                logger.info(f"Game '{game_name}' available on SUT {sut_ip} via name match")
                                return jsonify({
                                    "available": True,
                                    "game_name": game.get("name", game_name),
                                    "steam_app_id": game.get("steam_app_id"),
                                    "install_path": game.get("install_path"),
                                    "sut_ip": sut_ip,
                                    "match_method": "name"
                                })

                    # PRIORITY 2.5: Match standalone games by folder_names from config
                    folder_names = []
                    if hasattr(game_config, 'metadata') and game_config.metadata:
                        folder_names = game_config.metadata.get('folder_names', [])

                    if folder_names:
                        for game in installed_games:
                            installed_name = game.get("name", "").lower()
                            install_dir = game.get("install_dir", "").lower()
                            for folder_name in folder_names:
                                folder_lower = folder_name.lower()
                                if folder_lower in installed_name or folder_lower == install_dir:
                                    if game.get("exists", True):
                                        logger.info(f"Game '{game_name}' available on SUT {sut_ip} via folder_name match: {folder_name}")
                                        return jsonify({
                                            "available": True,
                                            "game_name": game.get("name", game_name),
                                            "steam_app_id": game.get("steam_app_id"),
                                            "install_path": game.get("install_path"),
                                            "sut_ip": sut_ip,
                                            "match_method": "folder_name"
                                        })

                    # PRIORITY 3: Fallback to preset-manager for abbreviation matching (e.g., ffxiv)
                    # Only do this if we have a preset_id to match against
                    import re
                    preset_id = None
                    if hasattr(game_config, 'metadata') and game_config.metadata:
                        preset_id = game_config.metadata.get('preset_id')
                    if not preset_id:
                        preset_id = re.sub(r'[^a-z0-9]+', '-', game_name.lower()).strip('-')

                    # Check if any installed game was matched by preset-manager
                    for game in installed_games:
                        installed_name = game.get("name", "").lower()
                        # Check for abbreviation patterns (e.g., ffxiv in name)
                        if any(abbr in installed_name for abbr in ['ffxiv', 'ff14', 'bmw', 'rdr2', 'gta5', 'sotr', 'sottr']):
                            # This might be an abbreviation match - check via preset-manager
                            try:
                                pm_response = http_requests.get(
                                    f"http://localhost:5002/api/sync/sut-games/{sut_ip}?port=8080",
                                    timeout=10
                                )
                                if pm_response.status_code == 200:
                                    pm_data = pm_response.json()
                                    for pm_game in pm_data.get("games", []):
                                        if pm_game.get("preset_short_name") == preset_id:
                                            logger.info(f"Game '{game_name}' available on SUT {sut_ip} via preset abbreviation match")
                                            return jsonify({
                                                "available": True,
                                                "game_name": pm_game.get("name", game_name),
                                                "steam_app_id": pm_game.get("steam_app_id"),
                                                "install_path": pm_game.get("install_path"),
                                                "sut_ip": sut_ip,
                                                "match_method": "name"
                                            })
                            except Exception as e:
                                logger.warning(f"Preset-manager fallback failed: {e}")
                            break

                    # Not found
                    logger.info(f"Game '{game_name}' NOT available on SUT {sut_ip}")
                    return jsonify({
                        "available": False,
                        "game_name": game_name,
                        "steam_app_id": config_steam_app_id,
                        "sut_ip": sut_ip,
                        "match_method": None,
                        "installed_games_count": len(installed_games)
                    })

                except http_requests.RequestException as e:
                    logger.warning(f"Failed to query SUT {sut_ip}: {e}")
                    return jsonify({
                        "available": False,
                        "game_name": game_name,
                        "steam_app_id": config_steam_app_id,
                        "sut_ip": sut_ip,
                        "error": f"Failed to connect to SUT: {str(e)}",
                        "match_method": None
                    })

            except Exception as e:
                logger.error(f"Error checking game availability: {e}")
                return jsonify({"error": str(e)}), 500

        # ==========================================================================
        # PRESET APPLICATION ENDPOINTS (RPX + Preset-Manager Integration)
        # ==========================================================================

        @app.route('/api/presets/apply', methods=['POST'])
        def apply_presets():
            """
            Apply PPG presets to SUTs before automation.

            This endpoint integrates with Preset-Manager to apply graphics presets
            to selected SUTs and games before starting automation runs.

            Request body:
            {
                "sut_ips": ["192.168.0.102", "192.168.0.103"],
                "games": ["cyberpunk-2077", "cs2"],
                "preset": {
                    "resolution": "1920x1080",
                    "graphics": "high"
                }
            }

            Response:
            {
                "successful": [...],
                "failed": [...],
                "skipped": [...],
                "summary": {...}
            }
            """
            try:
                data = request.get_json()
                if not data:
                    return jsonify({"error": "Request data required"}), 400

                sut_ips = data.get('sut_ips', [])
                games = data.get('games', [])
                preset = data.get('preset', {})

                if not sut_ips:
                    return jsonify({"error": "sut_ips list required"}), 400
                if not games:
                    return jsonify({"error": "games list required"}), 400

                resolution = preset.get('resolution', '1920x1080')
                graphics = preset.get('graphics', 'high')

                logger.info(f"Applying presets: {len(sut_ips)} SUTs, {len(games)} games, {graphics}@{resolution}")

                # Check if Preset-Manager client is available
                if not self.preset_manager_client:
                    return jsonify({
                        "error": "Preset-Manager client not available",
                        "successful": [],
                        "failed": [{"sut_ip": ip, "game": g, "error": "Preset-Manager not configured"}
                                    for ip in sut_ips for g in games],
                        "skipped": [],
                        "summary": {"error": "Preset-Manager not configured"}
                    }), 503

                # Call Preset-Manager's presets endpoint
                result = self.preset_manager_client.apply_presets_sync(
                    sut_ips=sut_ips,
                    games=games,
                    resolution=resolution,
                    graphics=graphics
                )

                if "error" in result and not result.get("successful"):
                    logger.error(f"Preset application failed: {result.get('error')}")
                    return jsonify(result), 500

                logger.info(f"Preset application results: {result.get('summary', {})}")
                return jsonify(result)

            except Exception as e:
                logger.error(f"Error applying presets: {e}", exc_info=True)
                return jsonify({"error": str(e)}), 500

        @app.route('/api/presets/validate', methods=['POST'])
        def validate_presets():
            """
            Validate which games have presets and are installed on SUTs.

            This is a read-only check before actually applying presets.
            """
            try:
                data = request.get_json()
                if not data:
                    return jsonify({"error": "Request data required"}), 400

                sut_ips = data.get('sut_ips', [])
                games = data.get('games', [])
                preset = data.get('preset', {})

                if not sut_ips or not games:
                    return jsonify({"error": "sut_ips and games lists required"}), 400

                # Build validation results
                validation = {
                    "suts": {},
                    "games_with_presets": [],
                    "games_without_presets": [],
                    "ready_for_automation": []
                }

                # For each SUT, check installed games
                for sut_ip in sut_ips:
                    sut_info = {"ip": sut_ip, "online": False, "installed_games": [], "missing_games": []}

                    # Find SUT in discovery
                    if self.use_external_discovery and self.discovery_client:
                        suts = self.discovery_client.get_suts_sync()
                        for sut in suts:
                            if sut.get("ip") == sut_ip:
                                sut_info["online"] = sut.get("status") == "online" or sut.get("is_online")
                                break
                    else:
                        device = self.device_registry.get_device_by_ip(sut_ip)
                        if device:
                            sut_info["online"] = device.is_online

                    # If online, get installed games
                    if sut_info["online"]:
                        import requests
                        try:
                            resp = requests.get(f"http://{sut_ip}:8080/installed_games", timeout=10)
                            if resp.status_code == 200:
                                installed = resp.json().get("games", [])
                                installed_names = [g.get("name", "").lower() for g in installed]

                                for game in games:
                                    game_lower = game.lower().replace("-", " ")
                                    if any(game_lower in name or name in game_lower for name in installed_names):
                                        sut_info["installed_games"].append(game)
                                    else:
                                        sut_info["missing_games"].append(game)
                        except Exception as e:
                            logger.warning(f"Could not get installed games from {sut_ip}: {e}")
                            sut_info["missing_games"] = games
                    else:
                        sut_info["missing_games"] = games

                    validation["suts"][sut_ip] = sut_info

                return jsonify(validation)

            except Exception as e:
                logger.error(f"Error validating presets: {e}")
                return jsonify({"error": str(e)}), 500


        # Automation runs management
        @app.route('/api/runs', methods=['POST'])
        def start_automation_run():
            """Start a new automation run"""
            try:
                logger.info(f"Received start automation run request from {request.remote_addr}")
                data = request.get_json()
                logger.info(f"Request data: {data}")
                if not data:
                    logger.warning("No request data provided")
                    return jsonify({"error": "Request data required"}), 400
                
                # Validate required fields
                sut_ip = data.get('sut_ip')
                game_name = data.get('game_name')
                iterations = data.get('iterations', 1)
                quality = data.get('quality')  # 'low' | 'medium' | 'high' | 'ultra'
                resolution = data.get('resolution')  # '720p' | '1080p' | '1440p' | '2160p'
                skip_steam_login = data.get('skip_steam_login', False)  # If true, skip Steam account management
                disable_tracing = data.get('disable_tracing', False)  # If true, disable SOCWatch/PTAT tracing
                cooldown_seconds = data.get('cooldown_seconds', 120)  # Cooldown between iterations (default 2 min, 0 to disable)
                tracing_agents = data.get('tracing_agents')  # Specific tracing agents to use (e.g., ['socwatch', 'ptat'])
                start_step = data.get('start_step')  # Step to start from (1-based, for testing specific steps)
                end_step = data.get('end_step')  # Step to end at (inclusive, for testing specific steps)

                if not sut_ip or not game_name:
                    return jsonify({"error": "sut_ip and game_name are required"}), 400
                
                # Validate SUT exists and is online
                device = None
                device_id = None

                if self.use_external_discovery and self.discovery_client:
                    # Use Discovery Service to find device by IP (sync version for Flask)
                    try:
                        suts = self.discovery_client.get_suts_sync()
                        # Find an online SUT with matching IP (prefer online over offline)
                        matching_suts = [s for s in suts if s.get("ip") == sut_ip]
                        online_sut = next((s for s in matching_suts if s.get("status") == "online" or s.get("is_online")), None)

                        if online_sut:
                            sut = online_sut
                        elif matching_suts:
                            # All matching SUTs are offline
                            return jsonify({"error": f"SUT {sut_ip} is not online"}), 400
                        else:
                            sut = None

                        if sut:
                            device_id = sut.get("unique_id")
                            # Create a simple object with required attributes
                            class DeviceProxy:
                                def __init__(self, data):
                                    self.unique_id = data.get("unique_id")
                                    self.ip = data.get("ip")
                                    self.port = data.get("port", 8080)
                                    self.hostname = data.get("hostname")
                                    self.is_online = data.get("is_online", data.get("status") == "online")
                            device = DeviceProxy(sut)
                    except Exception as e:
                        logger.error(f"Error querying Discovery Service: {e}")
                        return jsonify({"error": f"Failed to query Discovery Service: {str(e)}"}), 500
                else:
                    device = self.device_registry.get_device_by_ip(sut_ip)
                    if device:
                        device_id = device.unique_id

                if not device:
                    return jsonify({"error": f"SUT {sut_ip} not found"}), 404

                if not device.is_online:
                    return jsonify({"error": f"SUT {sut_ip} is not online"}), 400
                
                # Validate game exists
                if not self.game_manager:
                    return jsonify({"error": "Game manager not available"}), 500
                
                game = self.game_manager.get_game(game_name)
                if not game:
                    return jsonify({"error": f"Game '{game_name}' not found"}), 404
                
                # Queue the run (run_manager is passed from controller)
                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    logger.error("Run manager not available when trying to start run")
                    return jsonify({"error": "Run manager not available"}), 500
                
                logger.info(f"Run manager available, queuing run: {game_name} on {sut_ip} ({iterations} iterations)")
                
                try:
                    run_id = self.run_manager.queue_run(
                        game_name=game_name,
                        sut_ip=sut_ip,
                        sut_device_id=device.unique_id,
                        iterations=int(iterations),
                        quality=quality,
                        resolution=resolution,
                        skip_steam_login=skip_steam_login,
                        disable_tracing=disable_tracing,
                        cooldown_seconds=int(cooldown_seconds),
                        tracing_agents=tracing_agents,
                        start_step=int(start_step) if start_step else None,
                        end_step=int(end_step) if end_step else None
                    )
                    step_range_info = f", steps={start_step}-{end_step}" if start_step or end_step else ""
                    logger.info(f"Successfully queued run {run_id} (quality={quality}, resolution={resolution}, skip_steam={skip_steam_login}, disable_tracing={disable_tracing}, tracing_agents={tracing_agents}, cooldown={cooldown_seconds}s{step_range_info})")
                    
                    return jsonify({
                        "status": "success",
                        "run_id": run_id,
                        "message": f"Started automation run for {game_name} on {sut_ip}"
                    })
                    
                except Exception as queue_error:
                    logger.error(f"Failed to queue run: {queue_error}", exc_info=True)
                    return jsonify({"error": f"Failed to queue run: {str(queue_error)}"}), 500
                
            except Exception as e:
                logger.error(f"Error starting automation run: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/runs', methods=['GET'])
        def get_automation_runs():
            """Get all automation runs (active and history) with pagination

            Query params:
                page: Page number (default 1)
                per_page: Items per page (default 50, max 100)
            """
            try:
                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({"active": {}, "history": [], "pagination": {"page": 1, "per_page": 50, "total": 0, "total_pages": 1, "has_more": False}})

                # Parse pagination params
                page = request.args.get('page', 1, type=int)
                per_page = request.args.get('per_page', 50, type=int)

                # Validate params
                page = max(1, page)
                per_page = max(1, min(100, per_page))  # Cap at 100

                runs_data = self.run_manager.get_all_runs(page=page, per_page=per_page)
                return jsonify(runs_data)

            except Exception as e:
                logger.error(f"Error getting automation runs: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/runs/<run_id>', methods=['GET'])
        def get_automation_run(run_id):
            """Get specific automation run status"""
            try:
                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({"error": "Run manager not available"}), 500
                
                run_data = self.run_manager.get_run_status(run_id)
                if not run_data:
                    return jsonify({"error": f"Run {run_id} not found"}), 404
                
                return jsonify(run_data)
                
            except Exception as e:
                logger.error(f"Error getting run {run_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/runs/<run_id>/stop', methods=['POST'])
        def stop_automation_run(run_id):
            """Stop a specific automation run

            Optional JSON body:
            - kill_game: bool - If true, also kill the game on the SUT
            """
            try:
                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({"error": "Run manager not available"}), 500

                # Check if we should kill the game
                kill_game = False
                data = request.get_json(silent=True) or {}
                kill_game = data.get('kill_game', False)

                # Get run info before stopping (to get SUT IP and game)
                run = self.run_manager.get_run(run_id)
                sut_ip = run.sut_ip if run else None
                game_name = run.game_name if run else None

                success = self.run_manager.stop_run(run_id)
                if not success:
                    return jsonify({"error": f"Run {run_id} not found or not running"}), 404

                # Kill the game if requested
                game_killed = False
                if kill_game and sut_ip:
                    try:
                        # Get device from registry
                        device = self.device_registry.get_device_by_ip(sut_ip)
                        if device:
                            # Send kill command to SUT
                            result = self.sut_client.perform_action(device.ip, device.port, {
                                "type": "close_game"
                            })
                            game_killed = result.success
                            logger.info(f"Kill game result for {game_name} on {sut_ip}: {result.success}")
                    except Exception as kill_err:
                        logger.warning(f"Failed to kill game on {sut_ip}: {kill_err}")

                return jsonify({
                    "status": "success",
                    "message": f"Stopped run {run_id}" + (" and killed game" if game_killed else ""),
                    "game_killed": game_killed
                })

            except Exception as e:
                logger.error(f"Error stopping run {run_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/runs/<run_id>/logs', methods=['GET'])
        def get_run_logs(run_id):
            """Get logs for a specific automation run from blackbox files

            Query params:
                limit: Max number of log entries to return (default 500, max 2000)
                offset: Number of entries to skip (for pagination)
            """
            try:
                import re
                from pathlib import Path

                # Parse pagination params
                limit = min(int(request.args.get('limit', 500)), 2000)
                offset = int(request.args.get('offset', 0))

                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({"error": "Run manager not available"}), 500

                # Get manifest from storage
                manifest = self.run_manager.storage.get_manifest(run_id)
                if not manifest:
                    return jsonify({"logs": [], "message": f"Run {run_id} not in cache"})

                # Get run directory
                run_dir = self.run_manager.storage.get_run_dir(run_id)
                if not run_dir or not run_dir.exists():
                    return jsonify({"logs": [], "message": "Run directory not found"})

                # Parse log entries from all blackbox files
                logs = []
                log_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},?\d*)\s*-\s*(\S+)\s*-\s*(\w+)\s*-\s*(.*)$')

                # Find blackbox log files using targeted glob patterns
                # Limit depth to avoid slow recursive search
                search_patterns = [
                    'blackbox*',           # Direct in run_dir
                    'perf-run-*/blackbox*', # In iteration folder
                    'perf-run-*/perf-run-*/blackbox*',  # Legacy double-nested
                ]

                log_files = set()
                for pattern in search_patterns:
                    for f in run_dir.glob(pattern):
                        if f.is_file() and f.name.startswith('blackbox'):
                            log_files.add(f)

                # If no logs found, return early
                if not log_files:
                    return jsonify({"logs": [], "run_id": run_id, "folder_name": manifest.folder_name, "total_entries": 0, "message": "No log files found"})

                for log_file in sorted(log_files):
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue

                                match = log_pattern.match(line)
                                if match:
                                    timestamp_str, module, level, message = match.groups()
                                    # Convert timestamp to ISO format
                                    try:
                                        # Handle both "2025-12-28 17:39:18" and "2025-12-28 17:39:18,123"
                                        timestamp_str = timestamp_str.replace(',', '.')
                                        logs.append({
                                            "timestamp": timestamp_str,
                                            "level": level.lower(),
                                            "message": f"[{module}] {message}"
                                        })
                                    except:
                                        logs.append({
                                            "timestamp": timestamp_str,
                                            "level": level.lower(),
                                            "message": f"[{module}] {message}"
                                        })
                                else:
                                    # Line doesn't match pattern, append as continuation
                                    if logs:
                                        logs[-1]["message"] += "\n" + line
                    except Exception as e:
                        logger.warning(f"Error reading log file {log_file}: {e}")

                # Apply pagination
                total_entries = len(logs)
                paginated_logs = logs[offset:offset + limit]

                return jsonify({
                    "logs": paginated_logs,
                    "run_id": run_id,
                    "folder_name": manifest.folder_name,
                    "total_entries": total_entries,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total_entries
                })

            except Exception as e:
                logger.error(f"Error getting logs for run {run_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/runs/<run_id>/timeline', methods=['GET'])
        def get_run_timeline(run_id):
            """Get timeline events for a specific automation run"""
            try:
                import json
                from pathlib import Path
                from ..core.run_manager import RunStatus

                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({"error": "Run manager not available"}), 500

                # First check if run is currently active
                active_run = self.run_manager.get_run(run_id)
                if active_run:
                    # Check if run is queued (hasn't started executing yet)
                    if active_run.status == RunStatus.QUEUED:
                        return jsonify({
                            "run_id": run_id,
                            "run_status": "queued",
                            "events": [],
                            "message": "Run is queued, waiting to start",
                            "source": "active"
                        })

                    # Check if run has timeline in memory (actively executing)
                    if hasattr(active_run, 'timeline') and active_run.timeline:
                        # Return timeline from active run
                        return jsonify({
                            "run_id": run_id,
                            "events": active_run.timeline.get_events_dict(),
                            "source": "active"
                        })

                # Fall back to timeline.json file in run directory
                manifest = self.run_manager.storage.get_manifest(run_id)
                if not manifest:
                    # Try reloading history - run might have just completed
                    self.run_manager.storage.load_run_history()
                    manifest = self.run_manager.storage.get_manifest(run_id)

                if not manifest:
                    return jsonify({"error": f"Run {run_id} not found"}), 404

                run_dir = self.run_manager.storage.get_run_dir(run_id)
                if not run_dir or not run_dir.exists():
                    return jsonify({"events": [], "message": "Run directory not found"})

                timeline_file = run_dir / 'timeline.json'
                if not timeline_file.exists():
                    return jsonify({"events": [], "message": "Timeline not available for this run"})

                try:
                    with open(timeline_file, 'r') as f:
                        timeline_data = json.load(f)
                    return jsonify({
                        "run_id": run_id,
                        "events": timeline_data.get('events', []),
                        "source": "file"
                    })
                except Exception as e:
                    logger.warning(f"Error reading timeline file: {e}")
                    return jsonify({"events": [], "error": str(e)})

            except Exception as e:
                logger.error(f"Error getting timeline for run {run_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/runs/<run_id>/story', methods=['GET'])
        def get_run_story(run_id):
            """Get comprehensive run story data for the Story View visualization.

            Returns aggregated data including:
            - Timeline events (with service calls and element matches)
            - Screenshot paths and OmniParser JSON paths
            - Run metadata (game, SUT, status)
            """
            try:
                import json
                from pathlib import Path
                from ..core.run_manager import RunStatus

                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({"error": "Run manager not available"}), 500

                # Get run info from manifest or active run
                manifest = self.run_manager.storage.get_manifest(run_id)
                active_run = self.run_manager.get_run(run_id)

                if not manifest and not active_run:
                    # Try reloading history
                    self.run_manager.storage.load_run_history()
                    manifest = self.run_manager.storage.get_manifest(run_id)

                if not manifest and not active_run:
                    return jsonify({"error": f"Run {run_id} not found"}), 404

                # Extract data from manifest or active run
                # RunManifest has: config.games[0], sut.ip, created_at, config.iterations
                # ActiveRun has: game_name, sut_ip, started_at, iterations
                if manifest:
                    game_name = manifest.config.games[0] if manifest.config and manifest.config.games else "Unknown"
                    sut_ip = manifest.sut.ip if manifest.sut else None
                    status = manifest.status
                    started_at = manifest.created_at
                    completed_at = manifest.completed_at
                    iterations = manifest.config.iterations if manifest.config else 1
                elif active_run:
                    game_name = active_run.game_name
                    sut_ip = active_run.sut_ip
                    status = active_run.status.value if hasattr(active_run.status, 'value') else str(active_run.status)
                    started_at = active_run.started_at.isoformat() if active_run.started_at else None
                    completed_at = active_run.completed_at.isoformat() if active_run.completed_at else None
                    iterations = active_run.iterations
                else:
                    game_name = "Unknown"
                    sut_ip = None
                    status = "unknown"
                    started_at = None
                    completed_at = None
                    iterations = 1

                # Build response
                response = {
                    "run_id": run_id,
                    "game_name": game_name,
                    "sut_ip": sut_ip,
                    "status": status,
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "iterations": iterations,
                    "timeline_events": [],
                    "service_calls": [],
                    "element_matches": [],
                    "screenshots": [],
                }

                # Get run directory
                run_dir = self.run_manager.storage.get_run_dir(run_id)

                # Load timeline events
                if active_run and hasattr(active_run, 'timeline') and active_run.timeline:
                    # Get events from active run's timeline (in memory)
                    events = active_run.timeline.get_events_dict()
                elif run_dir and run_dir.exists():
                    # Load from timeline.json file
                    timeline_file = run_dir / 'timeline.json'
                    if timeline_file.exists():
                        try:
                            with open(timeline_file, 'r') as f:
                                timeline_data = json.load(f)
                            events = timeline_data.get('events', [])
                        except Exception as e:
                            logger.warning(f"Error reading timeline file: {e}")
                            events = []
                    else:
                        events = []
                else:
                    events = []

                response["timeline_events"] = events

                # Extract service calls from timeline events
                service_calls = []
                for event in events:
                    if event.get('event_type', '').startswith('service_call_'):
                        service_calls.append({
                            'call_id': event.get('event_id'),
                            'timestamp': event.get('timestamp'),
                            'source': event.get('metadata', {}).get('source_service'),
                            'target': event.get('metadata', {}).get('target_service'),
                            'endpoint': event.get('metadata', {}).get('endpoint'),
                            'method': event.get('metadata', {}).get('method', 'POST'),
                            'duration_ms': event.get('metadata', {}).get('duration_ms') or event.get('duration_ms'),
                            'status': event.get('status'),
                            'linked_event_id': event.get('metadata', {}).get('linked_event_id'),
                        })
                response["service_calls"] = service_calls

                # Extract element matches from step events
                element_matches = []
                for event in events:
                    if event.get('event_type') == 'step_started':
                        metadata = event.get('metadata', {})
                        if metadata.get('expected_element') or metadata.get('matched_element'):
                            element_matches.append({
                                'step': metadata.get('step'),
                                'description': metadata.get('description'),
                                'expected': metadata.get('expected_element'),
                                'actual': metadata.get('matched_element'),
                                'click_coordinates': metadata.get('click_coordinates'),
                                'screenshot_index': metadata.get('screenshot_index'),
                            })
                response["element_matches"] = element_matches

                # Collect screenshot info from run directory
                screenshots = []
                if run_dir and run_dir.exists():
                    # Search in iteration directories
                    for iter_dir in sorted(run_dir.glob('*-run-*')):
                        screenshots_dir = iter_dir / 'screenshots'
                        if screenshots_dir.exists():
                            iteration_match = iter_dir.name  # e.g., "perf-run-1"
                            import re
                            for screenshot_file in sorted(screenshots_dir.glob('screenshot_*.png')):
                                # Extract step number from filename (handles screenshot_1.png, screenshot_1_retry1.png, etc.)
                                stem = screenshot_file.stem.replace('screenshot_', '')
                                # Use regex to extract just the leading number
                                match = re.match(r'^(\d+)', stem)
                                step_num = int(match.group(1)) if match else None

                                # Skip retry screenshots (only use the final screenshot for each step)
                                if '_retry' in screenshot_file.name:
                                    continue

                                screenshot_info = {
                                    'index': step_num,
                                    'step': step_num,
                                    'path': f"/api/runs/{run_id}/screenshots/step_{step_num}.png" if step_num else str(screenshot_file.name),
                                    'iteration': iteration_match,
                                }

                                # Check for OmniParser JSON
                                omniparser_file = screenshots_dir / f"screenshot_{step_num}.json"
                                if omniparser_file.exists():
                                    screenshot_info['omniparser_path'] = f"/api/runs/{run_id}/omniparser/{iteration_match}/screenshot_{step_num}.json"

                                # Check for parsed/annotated image (SOM image from OmniParser)
                                parsed_image_file = screenshots_dir / f"omniparser_screenshot_{step_num}.png"
                                if parsed_image_file.exists():
                                    screenshot_info['parsed_image_path'] = f"/api/runs/{run_id}/screenshots/omniparser_step_{step_num}.png"

                                screenshots.append(screenshot_info)

                response["screenshots"] = screenshots

                return jsonify(response)

            except Exception as e:
                logger.error(f"Error getting story for run {run_id}: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({"error": str(e)}), 500

        @app.route('/api/runs/<run_id>/omniparser/<path:filepath>', methods=['GET'])
        def get_run_omniparser_json(run_id, filepath):
            """Get OmniParser JSON analysis file from a run"""
            try:
                from pathlib import Path

                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({"error": "Run manager not initialized"}), 500

                run_dir = self.run_manager.storage.get_run_dir(run_id)
                if not run_dir or not run_dir.exists():
                    return jsonify({"error": f"Run {run_id} not found"}), 404

                # filepath could be: perf-run-1/screenshot_1.json
                json_path = run_dir / filepath.replace('/', os.sep)

                # Also check in screenshots subdirectory
                if not json_path.exists():
                    parts = filepath.split('/')
                    if len(parts) >= 2:
                        json_path = run_dir / parts[0] / 'screenshots' / parts[1]

                if not json_path.exists():
                    return jsonify({"error": f"OmniParser file not found: {filepath}"}), 404

                with open(json_path, 'r') as f:
                    data = json.load(f)

                return jsonify(data)

            except Exception as e:
                logger.error(f"Error getting OmniParser JSON for run {run_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/runs/<run_id>/screenshots/<path:filename>', methods=['GET'])
        def get_run_screenshot(run_id, filename):
            """Get a screenshot file from a run's screenshots directory"""
            try:
                from pathlib import Path

                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({"error": "Run manager not initialized"}), 500

                storage = self.run_manager.storage
                if not storage:
                    return jsonify({"error": "Storage manager not initialized"}), 500

                # Get the run directory
                run_dir = storage.get_run_dir(run_id)
                if not run_dir:
                    # Try loading from history if not in cache
                    storage.load_run_history()
                    run_dir = storage.get_run_dir(run_id)

                if not run_dir:
                    return jsonify({"error": f"Run {run_id} not found"}), 404

                if not run_dir.exists():
                    return jsonify({"error": f"Run directory not found: {run_dir}"}), 404

                # Screenshots can be in iteration subdirectories (perf-run-1, perf-run-2, etc.)
                # First, try to find the file directly in the requested path
                # Expected format: step_{N}.png -> look for screenshot_{N}.png

                # Map URL filename to actual filename
                # URL: step_1.png -> File: screenshot_1.png
                # URL: omniparser_step_1.png -> File: omniparser_screenshot_1.png
                actual_filename = filename
                if filename.startswith('omniparser_step_'):
                    # Convert omniparser_step_N.png to omniparser_screenshot_N.png
                    step_num = filename.replace('omniparser_step_', '').replace('.png', '')
                    actual_filename = f"omniparser_screenshot_{step_num}.png"
                elif filename.startswith('step_'):
                    # Convert step_N.png to screenshot_N.png
                    step_num = filename.replace('step_', '').replace('.png', '')
                    actual_filename = f"screenshot_{step_num}.png"

                # Search in iteration directories for the screenshot
                screenshot_path = None

                # Check each *-run-* directory (perf-run-N, tracing-run-N, trace-run-N, etc.)
                for iter_dir in sorted(run_dir.glob('*-run-*')):
                    candidate = iter_dir / 'screenshots' / actual_filename
                    if candidate.exists():
                        screenshot_path = candidate
                        break
                    # Also check with original filename in case it matches
                    candidate2 = iter_dir / 'screenshots' / filename
                    if candidate2.exists():
                        screenshot_path = candidate2
                        break

                # Also check trace-run if exists
                if not screenshot_path:
                    trace_dir = run_dir / 'trace-run' / 'screenshots'
                    if trace_dir.exists():
                        candidate = trace_dir / actual_filename
                        if candidate.exists():
                            screenshot_path = candidate
                        candidate2 = trace_dir / filename
                        if candidate2.exists():
                            screenshot_path = candidate2

                # Fallback: check root screenshots directory (old structure)
                if not screenshot_path:
                    root_screenshots = run_dir / 'screenshots'
                    if root_screenshots.exists():
                        candidate = root_screenshots / actual_filename
                        if candidate.exists():
                            screenshot_path = candidate
                        candidate2 = root_screenshots / filename
                        if candidate2.exists():
                            screenshot_path = candidate2

                if not screenshot_path or not screenshot_path.exists():
                    logger.warning(f"Screenshot not found: {filename} (tried {actual_filename}) in run {run_id}")
                    return jsonify({"error": f"Screenshot {filename} not found"}), 404

                logger.debug(f"Serving screenshot: {screenshot_path}")
                return send_file(str(screenshot_path), mimetype='image/png')

            except Exception as e:
                logger.error(f"Error getting screenshot {filename} for run {run_id}: {e}")
                return jsonify({"error": str(e)}), 500

        # =====================================================================
        # Trace Download Endpoints
        # =====================================================================

        @app.route('/api/runs/<run_id>/traces', methods=['GET'])
        def list_run_traces(run_id):
            """List available trace files for a run"""
            try:
                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({"error": "Run manager not available"}), 500

                from pathlib import Path
                run_dir = self.run_manager.storage.get_run_dir(run_id)
                if not run_dir:
                    return jsonify({"error": f"Run {run_id} not found"}), 404

                traces_dir = Path(run_dir) / "traces"
                agents = {}
                total_files = 0

                if traces_dir.exists() and traces_dir.is_dir():
                    for agent_dir in sorted(traces_dir.iterdir()):
                        if agent_dir.is_dir():
                            files = sorted([f.name for f in agent_dir.iterdir() if f.is_file()])
                            if files:
                                agents[agent_dir.name] = files
                                total_files += len(files)

                return jsonify({
                    "has_traces": total_files > 0,
                    "agents": agents,
                    "total_files": total_files,
                })

            except Exception as e:
                logger.error(f"Error listing traces for run {run_id}: {e}")
                return jsonify({"error": str(e)}), 500

        def _package_traces(run_ids: list, agent_filter: str = None) -> tuple:
            """Package trace files into a zip buffer.

            Collects traces from one or more runs into a consistent folder structure:
                <Agent>/<Game>/<trace_file>

            Args:
                run_ids: List of run IDs to collect traces from.
                agent_filter: Optional agent name to filter by.

            Returns:
                (BytesIO buffer, file_count) — the zip buffer and number of files added.
            """
            from pathlib import Path
            buf = io.BytesIO()
            file_count = 0

            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                for run_id in run_ids:
                    run_dir = self.run_manager.storage.get_run_dir(run_id)
                    if not run_dir:
                        continue

                    traces_dir = Path(run_dir) / "traces"
                    if not traces_dir.exists():
                        continue

                    manifest = self.run_manager.storage.get_manifest(run_id)
                    game_name = (manifest.config.games[0] if manifest and manifest.config and manifest.config.games else 'unknown')
                    safe_game = game_name.replace(' ', '_').replace(':', '').replace("'", '')

                    for agent_dir in sorted(traces_dir.iterdir()):
                        if not agent_dir.is_dir():
                            continue
                        if agent_filter and agent_dir.name != agent_filter:
                            continue
                        agent_display = agent_dir.name.capitalize()
                        for trace_file in sorted(agent_dir.iterdir()):
                            if trace_file.is_file():
                                arcname = f"{agent_display}/{safe_game}/{trace_file.name}"
                                zf.write(str(trace_file), arcname)
                                file_count += 1

            buf.seek(0)
            return buf, file_count

        @app.route('/api/runs/<run_id>/traces/download', methods=['GET'])
        def download_run_traces(run_id):
            """Download traces for a single run as a zip file"""
            try:
                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({"error": "Run manager not available"}), 500

                run_dir = self.run_manager.storage.get_run_dir(run_id)
                if not run_dir:
                    return jsonify({"error": f"Run {run_id} not found"}), 404

                agent_filter = request.args.get('agent')
                buf, file_count = _package_traces([run_id], agent_filter)

                if file_count == 0:
                    return jsonify({"error": "No trace files found"}), 404

                manifest = self.run_manager.storage.get_manifest(run_id)
                game_name = (manifest.config.games[0] if manifest and manifest.config and manifest.config.games else 'unknown')
                safe_game = game_name.replace(' ', '_').replace(':', '').replace("'", '')
                zip_name = f"traces_{safe_game}_{run_id[:8]}.zip"

                return send_file(buf, mimetype='application/zip', as_attachment=True, download_name=zip_name)

            except Exception as e:
                logger.error(f"Error downloading traces for run {run_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/runs/<run_id>/traces/<agent>/<filename>', methods=['GET'])
        def download_single_trace(run_id, agent, filename):
            """Download a single trace file"""
            try:
                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({"error": "Run manager not available"}), 500

                from pathlib import Path
                run_dir = self.run_manager.storage.get_run_dir(run_id)
                if not run_dir:
                    return jsonify({"error": f"Run {run_id} not found"}), 404

                trace_path = (Path(run_dir) / "traces" / agent / filename).resolve()
                traces_root = (Path(run_dir) / "traces").resolve()
                if not str(trace_path).startswith(str(traces_root)):
                    return jsonify({"error": "Invalid path"}), 400

                if not trace_path.exists() or not trace_path.is_file():
                    return jsonify({"error": f"Trace file not found: {agent}/{filename}"}), 404

                suffix = trace_path.suffix.lower()
                mimetype = 'text/csv' if suffix == '.csv' else 'application/octet-stream'

                return send_file(str(trace_path), mimetype=mimetype, as_attachment=True, download_name=filename)

            except Exception as e:
                logger.error(f"Error downloading trace {agent}/{filename} for run {run_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/campaigns/<campaign_id>/traces/download', methods=['GET'])
        def download_campaign_traces(campaign_id):
            """Download traces for a campaign as a zip file"""
            try:
                if not hasattr(self, 'campaign_manager') or self.campaign_manager is None:
                    return jsonify({"error": "Campaign manager not available"}), 500

                campaign = self.campaign_manager.get_campaign(campaign_id)
                if not campaign:
                    for c in self.campaign_manager.get_campaign_history():
                        if c.campaign_id == campaign_id:
                            campaign = c
                            break

                if not campaign:
                    return jsonify({"error": f"Campaign {campaign_id} not found"}), 404

                agent_filter = request.args.get('agent')
                buf, file_count = _package_traces(campaign.run_ids, agent_filter)

                if file_count == 0:
                    return jsonify({"error": "No trace files found in this campaign"}), 404

                zip_name = f"traces_campaign_{campaign_id[:8]}.zip"
                return send_file(buf, mimetype='application/zip', as_attachment=True, download_name=zip_name)

            except Exception as e:
                logger.error(f"Error downloading campaign traces for {campaign_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/runs/stats', methods=['GET'])
        def get_runs_stats():
            """Get automation runs statistics"""
            try:
                if not hasattr(self, 'run_manager') or self.run_manager is None:
                    return jsonify({
                        "active_runs": 0,
                        "queued_runs": 0,
                        "total_history": 0,
                        "completed_runs": 0,
                        "failed_runs": 0
                    })
                
                stats = self.run_manager.get_stats()
                return jsonify(stats)

            except Exception as e:
                logger.error(f"Error getting runs stats: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/accounts/status', methods=['GET'])
        def get_account_status():
            """Get Steam account lock status for multi-SUT coordination

            Response:
            {
                "af": {
                    "locked": true,
                    "holder_sut": "192.168.0.103",
                    "game_running": "Assassin's Creed Mirage",
                    "locked_at": "2024-01-06T12:00:00"
                },
                "gz": {
                    "locked": false,
                    "holder_sut": null,
                    "game_running": null,
                    "locked_at": null
                }
            }
            """
            try:
                from ..core.account_scheduler import get_account_scheduler
                scheduler = get_account_scheduler()
                status = scheduler.get_status()
                return jsonify(status)
            except Exception as e:
                logger.error(f"Error getting account status: {e}")
                return jsonify({"error": str(e)}), 500

        # =====================================================================
        # Campaign Management (Multi-Game Runs)
        # =====================================================================

        @app.route('/api/campaigns', methods=['POST'])
        def create_campaign():
            """
            Create a new multi-game campaign.

            Request body:
            {
                "sut_ip": "192.168.0.102",
                "games": ["Black Myth: Wukong", "Cyberpunk 2077", "Hitman 3"],
                "iterations": 3,
                "name": "Full Benchmark Suite"  // optional
            }

            Response:
            {
                "campaign_id": "uuid",
                "name": "BMW-CP2-HM3",
                "run_ids": ["uuid1", "uuid2", "uuid3"],
                "total_games": 3,
                "status": "queued"
            }
            """
            try:
                logger.info(f"Received create campaign request from {request.remote_addr}")

                if not hasattr(self, 'campaign_manager') or self.campaign_manager is None:
                    return jsonify({"error": "Campaign manager not available"}), 500

                data = request.get_json()
                if not data:
                    return jsonify({"error": "Request data required"}), 400

                # Validate required fields
                sut_ip = data.get('sut_ip')
                games = data.get('games', [])
                iterations = data.get('iterations', 1)
                name = data.get('name')
                quality = data.get('quality')  # 'low' | 'medium' | 'high' | 'ultra'
                resolution = data.get('resolution')  # '720p' | '1080p' | '1440p' | '2160p'
                skip_steam_login = data.get('skip_steam_login', False)  # If true, skip Steam account management
                disable_tracing = data.get('disable_tracing', False)  # If true, disable SOCWatch/PTAT tracing
                cooldown_seconds = data.get('cooldown_seconds', 120)  # Cooldown between iterations (default 2 min, 0 to disable)
                tracing_agents = data.get('tracing_agents')  # Specific tracing agents to use (e.g., ['socwatch', 'ptat'])

                if not sut_ip:
                    return jsonify({"error": "sut_ip is required"}), 400
                if not games or not isinstance(games, list) or len(games) == 0:
                    return jsonify({"error": "games must be a non-empty list"}), 400

                # Validate SUT exists and is online
                device = None
                device_id = None

                if self.use_external_discovery and self.discovery_client:
                    try:
                        suts = self.discovery_client.get_suts_sync()
                        matching_suts = [s for s in suts if s.get("ip") == sut_ip]
                        online_sut = next((s for s in matching_suts if s.get("status") == "online" or s.get("is_online")), None)

                        if online_sut:
                            device_id = online_sut.get("unique_id") or online_sut.get("device_id")
                        else:
                            # Allow offline SUTs for campaigns (runs will queue)
                            if matching_suts:
                                device_id = matching_suts[0].get("unique_id") or matching_suts[0].get("device_id")
                    except Exception as e:
                        logger.warning(f"Discovery service error: {e}")

                if not device_id:
                    device = self.device_registry.get_device_by_ip(sut_ip)
                    if device:
                        device_id = device.device_id

                if not device_id:
                    return jsonify({"error": f"SUT with IP {sut_ip} not found"}), 404

                # Validate all games exist
                for game in games:
                    game_config = self.game_manager.get_game(game)
                    if not game_config:
                        return jsonify({"error": f"Game '{game}' not found in configurations"}), 404

                # Create campaign
                campaign = self.campaign_manager.create_campaign(
                    sut_ip=sut_ip,
                    sut_device_id=device_id,
                    games=games,
                    iterations=iterations,
                    name=name,
                    quality=quality,
                    resolution=resolution,
                    skip_steam_login=skip_steam_login,
                    disable_tracing=disable_tracing,
                    cooldown_seconds=int(cooldown_seconds),
                    tracing_agents=tracing_agents
                )

                logger.info(f"Campaign created: {campaign.campaign_id} with {len(campaign.run_ids)} runs")

                return jsonify({
                    "status": "success",
                    "campaign_id": campaign.campaign_id,
                    "name": campaign.name,
                    "run_ids": campaign.run_ids,
                    "total_games": len(games),
                    "iterations_per_game": iterations,
                    "campaign_status": campaign.status.value,
                    "message": f"Campaign '{campaign.name}' created with {len(games)} games"
                })

            except Exception as e:
                logger.error(f"Error creating campaign: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({"error": str(e)}), 500

        @app.route('/api/campaigns', methods=['GET'])
        def get_campaigns():
            """Get all campaigns (active and history)"""
            try:
                if not hasattr(self, 'campaign_manager') or self.campaign_manager is None:
                    return jsonify({"active": [], "history": []})

                # Always force_update to ensure status is current (campaigns may have
                # completed since last event processing). This recalculates progress
                # from actual run states rather than relying on cached progress.
                active = [c.to_dict() for c in self.campaign_manager.get_all_campaigns(force_update=True)]
                history = [c.to_dict() for c in self.campaign_manager.get_campaign_history()]

                return jsonify({
                    "active": active,
                    "history": history
                })

            except Exception as e:
                logger.error(f"Error getting campaigns: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/campaigns/<campaign_id>', methods=['GET'])
        def get_campaign(campaign_id):
            """Get specific campaign status with all runs"""
            try:
                if not hasattr(self, 'campaign_manager') or self.campaign_manager is None:
                    return jsonify({"error": "Campaign manager not available"}), 500

                campaign = self.campaign_manager.get_campaign(campaign_id)
                if not campaign:
                    # Check history
                    for c in self.campaign_manager.get_campaign_history():
                        if c.campaign_id == campaign_id:
                            campaign = c
                            break

                if not campaign:
                    return jsonify({"error": f"Campaign {campaign_id} not found"}), 404

                # Get detailed run info for each run in the campaign
                runs = []
                for run_id in campaign.run_ids:
                    run_data = self.run_manager.get_run_status(run_id)
                    if run_data:
                        runs.append(run_data)

                result = campaign.to_dict()
                result['runs'] = runs

                return jsonify(result)

            except Exception as e:
                logger.error(f"Error getting campaign {campaign_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/campaigns/<campaign_id>/stop', methods=['POST'])
        def stop_campaign(campaign_id):
            """Stop all runs in a campaign"""
            try:
                if not hasattr(self, 'campaign_manager') or self.campaign_manager is None:
                    return jsonify({"error": "Campaign manager not available"}), 500

                success = self.campaign_manager.stop_campaign(campaign_id)
                if not success:
                    return jsonify({"error": f"Campaign {campaign_id} not found"}), 404

                return jsonify({
                    "status": "success",
                    "message": f"Campaign {campaign_id} stopped"
                })

            except Exception as e:
                logger.error(f"Error stopping campaign {campaign_id}: {e}")
                return jsonify({"error": str(e)}), 500

        # SUT Pairing Management
        @app.route('/api/suts/pair', methods=['POST'])
        def pair_sut():
            """Pair a SUT device"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({"error": "Request data required"}), 400

                device_id = data.get('device_id')
                paired_by = data.get('paired_by', 'user')

                if not device_id:
                    return jsonify({"error": "device_id is required"}), 400

                # Verify SUT exists in device registry
                device = self.device_registry.get_device_by_id(device_id)
                if not device:
                    return jsonify({"error": f"SUT {device_id} not found"}), 404

                # Pair the SUT using DeviceRegistry
                success = self.device_registry.pair_device(device_id, paired_by)
                if success:
                    # Get updated paired devices for broadcasting
                    paired_devices = self.device_registry.get_paired_devices()
                    paired_suts_data = []

                    for device in paired_devices:
                        paired_suts_data.append({
                            "device_id": device.unique_id,
                            "ip": device.ip,
                            "port": device.port,
                            "hostname": device.hostname,
                            "is_online": device.is_online,
                            "paired_at": device.paired_at.isoformat() if device.paired_at else None,
                            "paired_by": device.paired_by,
                            "capabilities": device.capabilities,
                            "success_rate": device.success_rate
                        })

                    # Broadcast update to WebSocket clients
                    self.websocket_handler.broadcast_message('paired_suts_update', paired_suts_data)

                    return jsonify({
                        "status": "success",
                        "message": f"SUT {device_id} paired successfully",
                        "paired_by": paired_by,
                        "paired_at": device.paired_at.isoformat() if device.paired_at else None
                    })
                else:
                    return jsonify({"error": "Failed to pair SUT"}), 500

            except Exception as e:
                logger.error(f"Error pairing SUT: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/suts/unpair/<device_id>', methods=['POST'])
        def unpair_sut(device_id):
            """Unpair a SUT device (forget device)"""
            try:
                # Verify SUT exists in device registry
                device = self.device_registry.get_device_by_id(device_id)
                if not device:
                    return jsonify({"error": f"SUT {device_id} not found"}), 404

                # Check if device is currently paired
                if not device.is_paired:
                    return jsonify({"error": f"SUT {device_id} is not paired"}), 400

                # Unpair the SUT using DeviceRegistry
                success = self.device_registry.unpair_device(device_id)
                if success:
                    # Get updated paired devices for broadcasting
                    paired_devices = self.device_registry.get_paired_devices()
                    paired_suts_data = []

                    for device in paired_devices:
                        paired_suts_data.append({
                            "device_id": device.unique_id,
                            "ip": device.ip,
                            "port": device.port,
                            "hostname": device.hostname,
                            "is_online": device.is_online,
                            "paired_at": device.paired_at.isoformat() if device.paired_at else None,
                            "paired_by": device.paired_by,
                            "capabilities": device.capabilities,
                            "success_rate": device.success_rate
                        })

                    # Broadcast update to WebSocket clients
                    self.websocket_handler.broadcast_message('paired_suts_update', paired_suts_data)

                    return jsonify({
                        "status": "success",
                        "message": f"SUT {device_id} unpaired successfully"
                    })
                else:
                    return jsonify({"error": "Failed to unpair SUT"}), 500

            except Exception as e:
                logger.error(f"Error unpairing SUT {device_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/suts/paired', methods=['GET'])
        def get_paired_suts():
            """Get all paired SUTs"""
            try:
                # Get paired devices from DeviceRegistry
                paired_devices = self.device_registry.get_paired_devices()
                paired_suts_data = []

                for device in paired_devices:
                    paired_suts_data.append({
                        "device_id": device.unique_id,
                        "ip": device.ip,
                        "port": device.port,
                        "hostname": device.hostname,
                        "is_online": device.is_online,
                        "status": device.status.value,
                        "paired_at": device.paired_at.isoformat() if device.paired_at else None,
                        "paired_by": device.paired_by,
                        "pair_priority": device.pair_priority,
                        "capabilities": device.capabilities,
                        "success_rate": device.success_rate,
                        "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                        "error_count": device.error_count,
                        "pairing_age_seconds": device.pairing_age_seconds
                    })

                return jsonify({
                    "paired_suts": paired_suts_data,
                    "count": len(paired_suts_data)
                })

            except Exception as e:
                logger.error(f"Error getting paired SUTs: {e}")
                return jsonify({"error": str(e)}), 500

        # Discovery Settings Management
        @app.route('/api/settings/discovery', methods=['GET'])
        def get_discovery_settings():
            """Get current discovery settings"""
            try:
                discovery_status = self.discovery_service.get_discovery_status()

                settings = {
                    "discovery_interval": self.discovery_service.config.discovery_interval,
                    "discovery_timeout": self.discovery_service.config.discovery_timeout,
                    "paired_devices_scan_interval": self.discovery_service.config.paired_devices_scan_interval,
                    "unpaired_discovery_interval": self.discovery_service.config.unpaired_discovery_interval,
                    "enable_priority_scanning": self.discovery_service.config.enable_priority_scanning,
                    "instant_paired_discovery": self.discovery_service.config.instant_paired_discovery,
                    "sut_port": self.discovery_service.config.sut_port,
                    "running": discovery_status.get("running", False),
                    "target_ips": discovery_status.get("target_ips", 0),
                    "priority_scan_count": discovery_status.get("priority_scan_count", 0),
                    "general_scan_count": discovery_status.get("general_scan_count", 0),
                    "paired_devices_count": discovery_status.get("paired_devices_count", 0)
                }

                return jsonify({"settings": settings})

            except Exception as e:
                logger.error(f"Error getting discovery settings: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/settings/discovery', methods=['PUT'])
        def update_discovery_settings():
            """Update discovery settings"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({"error": "Request data required"}), 400

                # Update config settings
                if "discovery_interval" in data:
                    self.discovery_service.config.discovery_interval = float(data["discovery_interval"])

                if "discovery_timeout" in data:
                    self.discovery_service.config.discovery_timeout = float(data["discovery_timeout"])

                if "paired_devices_scan_interval" in data:
                    self.discovery_service.config.paired_devices_scan_interval = float(data["paired_devices_scan_interval"])

                if "unpaired_discovery_interval" in data:
                    self.discovery_service.config.unpaired_discovery_interval = float(data["unpaired_discovery_interval"])

                if "enable_priority_scanning" in data:
                    self.discovery_service.config.enable_priority_scanning = bool(data["enable_priority_scanning"])

                if "instant_paired_discovery" in data:
                    self.discovery_service.config.instant_paired_discovery = bool(data["instant_paired_discovery"])

                if "sut_port" in data:
                    self.discovery_service.config.sut_port = int(data["sut_port"])

                # Broadcast settings update to WebSocket clients
                discovery_status = self.discovery_service.get_discovery_status()
                updated_settings = {
                    "discovery_interval": self.discovery_service.config.discovery_interval,
                    "discovery_timeout": self.discovery_service.config.discovery_timeout,
                    "paired_devices_scan_interval": self.discovery_service.config.paired_devices_scan_interval,
                    "unpaired_discovery_interval": self.discovery_service.config.unpaired_discovery_interval,
                    "enable_priority_scanning": self.discovery_service.config.enable_priority_scanning,
                    "instant_paired_discovery": self.discovery_service.config.instant_paired_discovery,
                    "sut_port": self.discovery_service.config.sut_port,
                    "running": discovery_status.get("running", False)
                }

                self.websocket_handler.broadcast_message('discovery_settings_update', {"settings": updated_settings})

                return jsonify({
                    "status": "success",
                    "message": "Discovery settings updated successfully",
                    "settings": updated_settings
                })

            except Exception as e:
                logger.error(f"Error updating discovery settings: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/settings/discovery/reset', methods=['POST'])
        def reset_discovery_settings():
            """Reset discovery settings to defaults"""
            try:
                from ..core.config import BackendConfig
                default_config = BackendConfig()

                # Reset to default values
                self.discovery_service.config.discovery_interval = default_config.discovery_interval
                self.discovery_service.config.discovery_timeout = default_config.discovery_timeout
                self.discovery_service.config.paired_devices_scan_interval = default_config.paired_devices_scan_interval
                self.discovery_service.config.unpaired_discovery_interval = default_config.unpaired_discovery_interval
                self.discovery_service.config.enable_priority_scanning = default_config.enable_priority_scanning
                self.discovery_service.config.instant_paired_discovery = default_config.instant_paired_discovery
                self.discovery_service.config.sut_port = default_config.sut_port

                # Broadcast settings update to WebSocket clients
                discovery_status = self.discovery_service.get_discovery_status()
                reset_settings = {
                    "discovery_interval": self.discovery_service.config.discovery_interval,
                    "discovery_timeout": self.discovery_service.config.discovery_timeout,
                    "paired_devices_scan_interval": self.discovery_service.config.paired_devices_scan_interval,
                    "unpaired_discovery_interval": self.discovery_service.config.unpaired_discovery_interval,
                    "enable_priority_scanning": self.discovery_service.config.enable_priority_scanning,
                    "instant_paired_discovery": self.discovery_service.config.instant_paired_discovery,
                    "sut_port": self.discovery_service.config.sut_port,
                    "running": discovery_status.get("running", False)
                }

                self.websocket_handler.broadcast_message('discovery_settings_update', {"settings": reset_settings})

                return jsonify({
                    "status": "success",
                    "message": "Discovery settings reset to defaults",
                    "settings": reset_settings
                })

            except Exception as e:
                logger.error(f"Error resetting discovery settings: {e}")
                return jsonify({"error": str(e)}), 500

        # =================================================================
        # Tracing Configuration API
        # =================================================================

        @app.route('/api/tracing/config', methods=['GET'])
        def get_tracing_config():
            """Get the centralized tracing configuration."""
            try:
                from modules.tracing_config import get_tracing_config
                config = get_tracing_config()
                return jsonify({
                    "status": "success",
                    "config": config.to_dict()
                })
            except Exception as e:
                logger.error(f"Error getting tracing config: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/tracing/config', methods=['PUT'])
        def update_tracing_config():
            """Update the centralized tracing configuration."""
            try:
                from modules.tracing_config import get_tracing_config
                data = request.get_json()
                if not data:
                    return jsonify({"error": "No data provided"}), 400

                config = get_tracing_config()
                if config.update(data):
                    return jsonify({
                        "status": "success",
                        "message": "Tracing configuration updated",
                        "config": config.to_dict()
                    })
                else:
                    return jsonify({"error": "Failed to save configuration"}), 500
            except Exception as e:
                logger.error(f"Error updating tracing config: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/tracing/agents', methods=['GET'])
        def get_tracing_agents():
            """Get all configured tracing agents."""
            try:
                from modules.tracing_config import get_tracing_config
                config = get_tracing_config()
                return jsonify({
                    "status": "success",
                    "agents": config.agents,
                    "enabled_agents": list(config.get_enabled_agents().keys())
                })
            except Exception as e:
                logger.error(f"Error getting tracing agents: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/tracing/agents/check-availability', methods=['GET'])
        def check_tracing_agents_availability():
            """Check which tracing agents are installed on a specific SUT."""
            try:
                import requests as http_requests
                from modules.tracing_config import get_tracing_config

                sut_ip = request.args.get('sut_ip')
                if not sut_ip:
                    return jsonify({"error": "sut_ip query parameter required"}), 400

                config = get_tracing_config()
                agents_config = config.agents or {}

                # Build tools dict from config
                tools = {}
                for name, agent in agents_config.items():
                    tools[name] = {
                        "path": agent.get("path", ""),
                        "description": agent.get("description", name),
                    }

                # Query SUT client
                agents_result = {}
                installed_count = 0
                total_count = len(tools)
                error_msg = None

                try:
                    response = http_requests.post(
                        f"http://{sut_ip}:8080/installed_tools",
                        json={"tools": tools},
                        timeout=10
                    )

                    if response.status_code == 200:
                        sut_data = response.json()
                        sut_tools = sut_data.get("tools", {})
                        installed_count = sut_data.get("installed_count", 0)

                        for name, agent in agents_config.items():
                            sut_tool = sut_tools.get(name, {})
                            agents_result[name] = {
                                "installed": sut_tool.get("installed", False),
                                "enabled": agent.get("enabled", False),
                                "description": agent.get("description", name),
                                "path": agent.get("path", ""),
                                "file_size": sut_tool.get("file_size"),
                            }
                    else:
                        error_msg = f"SUT returned status {response.status_code}"
                        for name, agent in agents_config.items():
                            agents_result[name] = {
                                "installed": None,
                                "enabled": agent.get("enabled", False),
                                "description": agent.get("description", name),
                                "path": agent.get("path", ""),
                                "file_size": None,
                            }

                except http_requests.exceptions.RequestException as e:
                    error_msg = f"Could not connect to SUT: {str(e)}"
                    for name, agent in agents_config.items():
                        agents_result[name] = {
                            "installed": None,
                            "enabled": agent.get("enabled", False),
                            "description": agent.get("description", name),
                            "path": agent.get("path", ""),
                            "file_size": None,
                        }

                result = {
                    "status": "success",
                    "sut_ip": sut_ip,
                    "agents": agents_result,
                    "installed_count": installed_count,
                    "total_count": total_count,
                }
                if error_msg:
                    result["error"] = error_msg

                return jsonify(result)

            except Exception as e:
                logger.error(f"Error checking tracing agent availability: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/tracing/agents/<agent_name>', methods=['PUT'])
        def update_tracing_agent(agent_name):
            """Update a specific tracing agent's configuration."""
            try:
                from modules.tracing_config import get_tracing_config
                data = request.get_json()
                if not data:
                    return jsonify({"error": "No data provided"}), 400

                config = get_tracing_config()
                if config.update_agent(agent_name, data):
                    return jsonify({
                        "status": "success",
                        "message": f"Agent '{agent_name}' configuration updated",
                        "agent": config.get_agent(agent_name)
                    })
                else:
                    return jsonify({"error": "Failed to save agent configuration"}), 500
            except Exception as e:
                logger.error(f"Error updating tracing agent: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/tracing/agents/<agent_name>/toggle', methods=['POST'])
        def toggle_tracing_agent(agent_name):
            """Enable or disable a tracing agent."""
            try:
                from modules.tracing_config import get_tracing_config
                config = get_tracing_config()

                agent = config.get_agent(agent_name)
                if not agent:
                    return jsonify({"error": f"Agent '{agent_name}' not found"}), 404

                # Toggle enabled state
                agent["enabled"] = not agent.get("enabled", False)

                if config.update_agent(agent_name, agent):
                    return jsonify({
                        "status": "success",
                        "message": f"Agent '{agent_name}' {'enabled' if agent['enabled'] else 'disabled'}",
                        "enabled": agent["enabled"]
                    })
                else:
                    return jsonify({"error": "Failed to save agent configuration"}), 500
            except Exception as e:
                logger.error(f"Error toggling tracing agent: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/tracing/output-dir', methods=['PUT'])
        def update_tracing_output_dir():
            """Update the tracing output directory."""
            try:
                from modules.tracing_config import get_tracing_config
                data = request.get_json()
                output_dir = data.get("output_dir")

                if not output_dir:
                    return jsonify({"error": "output_dir is required"}), 400

                config = get_tracing_config()
                if config.set_output_dir(output_dir):
                    return jsonify({
                        "status": "success",
                        "message": "Output directory updated",
                        "output_dir": output_dir
                    })
                else:
                    return jsonify({"error": "Failed to save output directory"}), 500
            except Exception as e:
                logger.error(f"Error updating tracing output dir: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/tracing/reload', methods=['POST'])
        def reload_tracing_config():
            """Reload tracing configuration from disk."""
            try:
                from modules.tracing_config import get_tracing_config
                config = get_tracing_config()
                config.reload()
                return jsonify({
                    "status": "success",
                    "message": "Tracing configuration reloaded",
                    "config": config.to_dict()
                })
            except Exception as e:
                logger.error(f"Error reloading tracing config: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/ssh/public-key', methods=['GET'])
        def get_master_ssh_public_key():
            """
            Get the Master's SSH public key.

            SUTs use this endpoint during setup to fetch and install the Master's
            public key into their authorized_keys file, enabling passwordless SSH
            access for trace file pulling.

            The key is read from ~/.ssh/master_ed25519.pub by default, falling back
            to other common key locations.
            """
            from pathlib import Path
            import os

            # List of potential public key paths (in order of preference)
            key_paths = [
                Path.home() / ".ssh" / "master_ed25519.pub",
                Path.home() / ".ssh" / "id_ed25519.pub",
                Path.home() / ".ssh" / "id_rsa.pub",
            ]

            # Try to find and read the public key
            for key_path in key_paths:
                if key_path.exists():
                    try:
                        public_key = key_path.read_text().strip()
                        if public_key and (public_key.startswith("ssh-") or public_key.startswith("ecdsa-")):
                            logger.info(f"Serving Master's public key from {key_path}")
                            return jsonify({
                                "status": "success",
                                "public_key": public_key,
                                "key_file": str(key_path)
                            })
                    except Exception as e:
                        logger.warning(f"Could not read key from {key_path}: {e}")
                        continue

            # No key found - return error with instructions
            logger.warning("No SSH public key found on Master")
            return jsonify({
                "status": "error",
                "error": "No SSH public key found on Master",
                "message": "Generate an SSH key with: ssh-keygen -t ed25519 -f ~/.ssh/master_ed25519"
            }), 404

        @app.route('/api/tracing/ssh/diagnose/<sut_ip>', methods=['GET'])
        def diagnose_ssh_connection(sut_ip: str):
            """
            Diagnose SSH connectivity to a SUT for trace file pulling.

            Returns detailed diagnostic information including:
            - TCP port 22 reachability
            - SSH handshake status
            - Specific error messages
            - Recommendations for fixing issues
            """
            try:
                from backend.core.trace_puller import diagnose_sut_ssh
                from modules.tracing_config import get_tracing_config

                # Get SSH settings from config
                config = get_tracing_config()
                ssh_config = config.config.get("ssh", {})
                ssh_user = ssh_config.get("user") or None

                results = diagnose_sut_ssh(sut_ip, ssh_user)
                return jsonify({
                    "status": "success",
                    "sut_ip": sut_ip,
                    "diagnostics": results
                })
            except Exception as e:
                logger.error(f"Error diagnosing SSH to {sut_ip}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/tracing/ssh/test/<sut_ip>', methods=['GET'])
        def test_ssh_connection(sut_ip: str):
            """
            Quick test of SSH connectivity to a SUT.

            Returns simple success/failure without detailed diagnostics.
            """
            try:
                from backend.core.trace_puller import TracePuller
                from modules.tracing_config import get_tracing_config

                # Get SSH settings from config
                config = get_tracing_config()
                ssh_config = config.config.get("ssh", {})
                ssh_user = ssh_config.get("user") or None
                ssh_timeout = ssh_config.get("timeout", 60)

                puller = TracePuller(sut_ip, ssh_user, ssh_timeout=ssh_timeout)
                success, message = puller.test_connection(with_retry=False)

                return jsonify({
                    "status": "success" if success else "failed",
                    "sut_ip": sut_ip,
                    "ssh_user": puller.ssh_user,
                    "connected": success,
                    "message": message
                })
            except Exception as e:
                logger.error(f"Error testing SSH to {sut_ip}: {e}")
                return jsonify({"error": str(e)}), 500

        # ── Tool deployment ──────────────────────────────────────────

        @app.route('/api/tools/deploy/<sut_ip>', methods=['POST'])
        def deploy_tools_to_sut(sut_ip: str):
            """
            Deploy tracing tools from master to a SUT.

            Walks each tools/<agent>/ directory on master and uploads all files
            to the agent's deploy_dir on the SUT, preserving subdirectory structure.

            Optional JSON body:
            {
                "agents": ["presentmon"],  // Only deploy specific agents (default: all)
                "force": false             // Re-deploy even if exe already exists
            }
            """
            try:
                import requests as http_requests
                from modules.tracing_config import get_tracing_config

                data = request.get_json() or {}
                only_agents = data.get("agents")
                force = data.get("force", False)

                config = get_tracing_config()
                agents_config = config.agents or {}
                tools_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "tools")

                deployed = {}
                skipped = {}
                failed = {}

                for agent_name, agent_cfg in agents_config.items():
                    if only_agents and agent_name not in only_agents:
                        continue

                    agent_path = agent_cfg.get("path", "")
                    deploy_dir = agent_cfg.get("deploy_dir", "")
                    if not agent_path or not deploy_dir:
                        skipped[agent_name] = "no path or deploy_dir configured"
                        continue

                    # Local tool directory on master: tools/<agent_name>/
                    local_dir = os.path.join(tools_dir, agent_name)
                    if not os.path.isdir(local_dir):
                        skipped[agent_name] = f"not bundled on master (no {local_dir})"
                        continue

                    # Check if main exe already installed on SUT (skip unless force)
                    if not force:
                        try:
                            check_resp = http_requests.post(
                                f"http://{sut_ip}:8080/installed_tools",
                                json={"tools": {agent_name: {"path": agent_path}}},
                                timeout=10
                            )
                            if check_resp.status_code == 200:
                                tool_info = check_resp.json().get("tools", {}).get(agent_name, {})
                                if tool_info.get("installed"):
                                    exe_local = os.path.join(local_dir, os.path.relpath(agent_path, deploy_dir))
                                    if os.path.isfile(exe_local):
                                        local_size = os.path.getsize(exe_local)
                                        remote_size = tool_info.get("file_size", 0)
                                        if local_size == remote_size:
                                            skipped[agent_name] = "already installed (same size)"
                                            continue
                        except Exception as e:
                            logger.warning(f"Could not check {agent_name} on SUT: {e}")

                    # Walk local tool directory and upload every file
                    files_uploaded = 0
                    total_size = 0
                    agent_errors = []

                    for root, dirs, files in os.walk(local_dir):
                        for fname in files:
                            local_path = os.path.join(root, fname)
                            # Relative path from agent dir (e.g. "64/socwatch.exe")
                            rel_path = os.path.relpath(local_path, local_dir)
                            # Destination directory on SUT
                            rel_dir = os.path.dirname(rel_path)
                            if rel_dir:
                                sut_dest_dir = deploy_dir + "\\" + rel_dir.replace("/", "\\")
                            else:
                                sut_dest_dir = deploy_dir

                            try:
                                with open(local_path, 'rb') as f:
                                    upload_resp = http_requests.post(
                                        f"http://{sut_ip}:8080/file_upload",
                                        files={"file": (fname, f, "application/octet-stream")},
                                        data={"path": sut_dest_dir},
                                        timeout=120
                                    )
                                if upload_resp.status_code == 200:
                                    result = upload_resp.json()
                                    files_uploaded += 1
                                    total_size += result.get("size", 0)
                                else:
                                    agent_errors.append(f"{rel_path}: {upload_resp.status_code}")
                            except Exception as e:
                                agent_errors.append(f"{rel_path}: {str(e)}")

                    if agent_errors:
                        failed[agent_name] = {
                            "files_uploaded": files_uploaded,
                            "errors": agent_errors
                        }
                    else:
                        deployed[agent_name] = {
                            "deploy_dir": deploy_dir,
                            "files": files_uploaded,
                            "total_size": total_size
                        }
                        logger.info(f"Deployed {agent_name} to {sut_ip}:{deploy_dir} ({files_uploaded} files, {total_size:,} bytes)")

                return jsonify({
                    "status": "success" if not failed else "partial",
                    "sut_ip": sut_ip,
                    "deployed": deployed,
                    "skipped": skipped,
                    "failed": failed
                })

            except Exception as e:
                logger.error(f"Error deploying tools to {sut_ip}: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/tools/available', methods=['GET'])
        def list_available_tools():
            """
            List tools available on master for deployment.

            Returns which agent tools are bundled locally and ready to push.
            """
            try:
                from modules.tracing_config import get_tracing_config

                config = get_tracing_config()
                agents_config = config.agents or {}
                tools_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "tools")

                tools = {}
                for agent_name, agent_cfg in agents_config.items():
                    agent_path = agent_cfg.get("path", "")
                    deploy_dir = agent_cfg.get("deploy_dir", "")

                    local_dir = os.path.join(tools_dir, agent_name)
                    bundled = os.path.isdir(local_dir)

                    # Count files and total size
                    file_count = 0
                    total_size = 0
                    if bundled:
                        for root, dirs, files in os.walk(local_dir):
                            for f in files:
                                file_count += 1
                                total_size += os.path.getsize(os.path.join(root, f))

                    tools[agent_name] = {
                        "exe_name": os.path.basename(agent_path) if agent_path else "",
                        "deploy_dir": deploy_dir,
                        "dest_path": agent_path,
                        "bundled": bundled,
                        "file_count": file_count,
                        "total_size": total_size,
                        "description": agent_cfg.get("description", agent_name),
                    }

                return jsonify({
                    "status": "success",
                    "tools_dir": tools_dir,
                    "tools": tools
                })

            except Exception as e:
                logger.error(f"Error listing available tools: {e}")
                return jsonify({"error": str(e)}), 500