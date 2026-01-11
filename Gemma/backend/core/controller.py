# -*- coding: utf-8 -*-
"""
Main backend controller - orchestrates all communication between components
"""

import logging
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS

from .config import BackendConfig
from .events import event_bus, EventType
from ..discovery.device_registry import DeviceRegistry
from ..discovery.sut_discovery import SUTDiscoveryService
from ..communication.websocket_handler import WebSocketHandler
from ..communication.sut_client import SUTClient
from ..communication.omniparser_client import OmniparserClient
from ..api.routes import APIRoutes
from ..api.admin_routes import admin_bp
from .game_manager import GameConfigManager

# Service clients for microservices architecture
from modules.discovery_client import DiscoveryServiceClient, get_discovery_client
from modules.queue_service_client import QueueServiceClient, get_queue_client
from modules.preset_manager_client import PresetManagerClient, get_preset_manager_client

logger = logging.getLogger(__name__)


class BackendController:
    """Main controller for the backend system"""
    
    def __init__(self, config: BackendConfig):
        self.config = config
        self.running = False
        self._shutdown_event = threading.Event()
        self.use_external_discovery = config.use_external_discovery

        # Initialize Flask app and SocketIO
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = config.secret_key
        CORS(self.app, origins="*")

        self.socketio = SocketIO(
            self.app,
            cors_allowed_origins="*",
            async_mode='threading',
            logger=config.debug,
            engineio_logger=config.debug
        )

        # Initialize game manager (always needed)
        self.game_manager = GameConfigManager()

        # Initialize service clients for microservices architecture
        if self.use_external_discovery:
            logger.info("=" * 60)
            logger.info("Using EXTERNAL microservices architecture")
            logger.info(f"Discovery Service: {config.discovery_service_url}")
            logger.info(f"Queue Service: {config.queue_service_url}")
            logger.info(f"Preset-Manager: {config.preset_manager_url}")
            logger.info("=" * 60)

            # Initialize service clients
            self.discovery_client = get_discovery_client(config.discovery_service_url)
            self.queue_client = get_queue_client(config.queue_service_url)
            self.preset_manager_client = get_preset_manager_client(config.preset_manager_url)

            # Create a lightweight device registry for local caching
            self.device_registry = DeviceRegistry(offline_timeout=30)
            self.discovery_service = None  # Not used in external mode

            # Use queue client for omniparser (compatibility layer)
            self.omniparser_client = self.queue_client

            # SUT client still needed for direct SUT communication (system_info, screenshots)
            # Note: Frontend never talks to SUTs directly, but backend can
            self.sut_client = SUTClient(timeout=config.discovery_timeout)

            self.websocket_handler = WebSocketHandler(self.socketio, self.device_registry, self.game_manager)

        else:
            logger.info("Using INTERNAL discovery (legacy mode)")

            # Initialize core components (legacy)
            self.device_registry = DeviceRegistry(offline_timeout=30)
            self.discovery_service = SUTDiscoveryService(config, self.device_registry)
            self.websocket_handler = WebSocketHandler(self.socketio, self.device_registry, self.game_manager)

            # Initialize communication clients (legacy)
            self.sut_client = SUTClient(timeout=config.discovery_timeout)
            self.omniparser_client = OmniparserClient(
                api_url=config.omniparser_url,
                timeout=60.0
            )

            # No service clients in legacy mode
            self.discovery_client = None
            self.queue_client = None
            self.preset_manager_client = None

        # Initialize run manager, campaign manager, and automation orchestrator
        from .run_manager import RunManager
        from .automation_orchestrator import AutomationOrchestrator
        from .campaign_manager import CampaignManager

        self.automation_orchestrator = AutomationOrchestrator(
            self.game_manager,
            self.device_registry,
            self.omniparser_client,
            discovery_client=self.discovery_client if self.use_external_discovery else None,
            websocket_handler=self.websocket_handler
        )
        self.run_manager = RunManager(
            max_concurrent_runs=5,
            orchestrator=self.automation_orchestrator,
            sut_client=self.sut_client
        )

        # Connect storage manager from RunManager to Orchestrator
        # This allows orchestrator to save screenshots and logs to persistent storage
        self.automation_orchestrator.set_storage(self.run_manager.storage)

        # Initialize campaign manager for multi-game campaigns
        self.campaign_manager = CampaignManager(self.run_manager)
        # Set campaign_manager reference on run_manager for storage
        self.run_manager.campaign_manager = self.campaign_manager

        # Set up run manager callbacks for WebSocket events
        self.run_manager.on_run_started = self._on_run_started
        self.run_manager.on_run_progress = self._on_run_progress
        self.run_manager.on_run_completed = self._on_run_completed
        self.run_manager.on_run_failed = self._on_run_failed
        # Step-level callbacks for automation timeline
        self.run_manager.on_step_started = self._on_step_started
        self.run_manager.on_step_completed = self._on_step_completed
        self.run_manager.on_step_failed = self._on_step_failed

        # Initialize API routes
        self.api_routes = APIRoutes(
            self.device_registry,
            self.discovery_service,
            self.sut_client,
            self.omniparser_client,
            self.websocket_handler,
            self.game_manager
        )

        # Pass service clients and config to API routes for external mode
        self.api_routes.use_external_discovery = self.use_external_discovery
        self.api_routes.discovery_client = getattr(self, 'discovery_client', None)
        self.api_routes.queue_client = getattr(self, 'queue_client', None)
        self.api_routes.preset_manager_client = getattr(self, 'preset_manager_client', None)

        # Pass run manager and campaign manager to API routes
        self.api_routes.run_manager = self.run_manager
        self.api_routes.campaign_manager = self.campaign_manager

        # Register API routes with Flask app
        self.api_routes.register_routes(self.app)

        # Register admin API blueprint
        self.app.register_blueprint(admin_bp)

        # Background services
        self.monitor_thread: Optional[threading.Thread] = None

        logger.info("Backend controller initialized")
        
    def start(self):
        """Start all backend services with optimized startup sequence"""
        if self.running:
            logger.warning("Backend controller is already running")
            return

        logger.info("Starting backend controller with optimized startup sequence...")
        self.running = True
        self._shutdown_event.clear()

        if self.use_external_discovery:
            # External microservices mode
            logger.info("Step 1/3: Testing external service connections...")
            self._test_external_services()

            logger.info("Step 2/3: WebSocket handler ready for frontend connections")

            logger.info("Step 3/3: Starting run manager and monitoring...")
            self.run_manager.start()

            # Start monitoring thread
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="BackendMonitor",
                daemon=True
            )
            self.monitor_thread.start()

            logger.info("Backend controller started successfully (external services mode)")
            logger.info(f"WebSocket clients: {self.websocket_handler.get_connected_clients_count()}")

        else:
            # Legacy internal discovery mode
            # Step 1: Test Omniparser connection first (critical for automation)
            logger.info("Step 1/4: Testing Omniparser connection...")
            self._test_omniparser_connection()

            # Step 2: WebSocket/Frontend connection (already initialized in __init__)
            logger.info("Step 2/4: WebSocket handler ready for frontend connections")

            # Step 3: Start SUT Discovery with paired devices prioritized
            logger.info("Step 3/4: Starting SUT Discovery with paired device priority...")
            paired_count = len(self.device_registry.get_paired_devices())
            if paired_count > 0 and self.config.enable_priority_scanning:
                logger.info(f"Priority scanning enabled: {paired_count} paired devices will be scanned first")
                if self.config.instant_paired_discovery:
                    logger.info("Instant paired discovery enabled: paired SUTs will be connected immediately")
            else:
                logger.info("No paired devices found or priority scanning disabled")

            self.discovery_service.start()

            # Step 4: Start remaining services
            logger.info("Step 4/4: Starting run manager and monitoring...")
            self.run_manager.start()

            # Start monitoring thread
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="BackendMonitor",
                daemon=True
            )
            self.monitor_thread.start()

            logger.info("Backend controller started successfully")
            logger.info(f"WebSocket clients: {self.websocket_handler.get_connected_clients_count()}")
            logger.info(f"Discovery targets: {len(self.discovery_service.target_ips)} IPs")
            logger.info(f"Paired devices ready for priority scanning: {paired_count}")
        
    def stop(self):
        """Stop all backend services"""
        if not self.running:
            return
            
        logger.info("Stopping backend controller...")
        self.running = False
        self._shutdown_event.set()
        
        try:
            # Stop run manager first (most important)
            if hasattr(self, 'run_manager'):
                self.run_manager.stop()

            # Stop discovery service
            if hasattr(self, 'discovery_service'):
                self.discovery_service.stop()
            
            # Wait for monitor thread with timeout
            if self.monitor_thread and self.monitor_thread.is_alive():
                logger.info("Waiting for monitor thread to finish...")
                self.monitor_thread.join(timeout=3)
                if self.monitor_thread.is_alive():
                    logger.warning("Monitor thread did not shut down gracefully")
                
            # Close communication clients
            try:
                if hasattr(self, 'sut_client'):
                    self.sut_client.close()
            except Exception as e:
                logger.error(f"Error closing SUT client: {e}")
                
            try:
                if hasattr(self, 'omniparser_client'):
                    self.omniparser_client.close()
            except Exception as e:
                logger.error(f"Error closing Omniparser client: {e}")
                
            # Force close SocketIO connections
            try:
                if hasattr(self, 'socketio'):
                    logger.info("Closing SocketIO connections...")
                    # Disconnect all clients first
                    self.socketio.emit('disconnect')
                    # Stop the server
                    self.socketio.stop()
                    logger.info("SocketIO stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping SocketIO: {e}")
                
            # Additional cleanup - force close any remaining threads
            import threading
            active_threads = threading.active_count()
            if active_threads > 1:
                logger.warning(f"Still have {active_threads} active threads after shutdown")
        
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        
        logger.info("Backend controller stopped")
    
    # WebSocket event callbacks for run management
    def _on_run_started(self, run_id: str, run_data: Dict[str, Any]):
        """Callback when a run starts"""
        logger.info(f"Run started: {run_id}")
        self.websocket_handler.broadcast_message('run_started', {
            'run_id': run_id,
            'run': run_data
        })
        
        # Also emit runs_update
        runs_data = self.run_manager.get_all_runs()
        self.websocket_handler.broadcast_message('runs_update', runs_data)
    
    def _on_run_progress(self, run_id: str, run_data: Dict[str, Any]):
        """Callback when run progress updates"""
        self.websocket_handler.broadcast_message('run_progress', {
            'run_id': run_id,
            'run': run_data
        })
        
        # Also emit runs_update for consistency
        runs_data = self.run_manager.get_all_runs()
        self.websocket_handler.broadcast_message('runs_update', runs_data)
    
    def _on_run_completed(self, run_id: str, run_data: Dict[str, Any]):
        """Callback when a run completes successfully"""
        logger.info(f"Run completed: {run_id}")
        self.websocket_handler.broadcast_message('run_completed', {
            'run_id': run_id,
            'run': run_data
        })

        # Emit updated runs data
        runs_data = self.run_manager.get_all_runs()
        self.websocket_handler.broadcast_message('runs_update', runs_data)

        # Check if this run is part of a campaign and update campaign status
        self._check_campaign_completion(run_id, run_data)
    
    def _on_run_failed(self, run_id: str, run_data: Dict[str, Any]):
        """Callback when a run fails"""
        logger.warning(f"Run failed: {run_id}")
        
        # Emit run failed event
        self.websocket_handler.broadcast_message('run_failed', {
            'run_id': run_id,
            'run': run_data
        })
        
        # Emit specific error notification for better UX
        error_message = run_data.get('error_message', 'Unknown error')
        error_type = 'automation_error'
        
        # Determine error type based on error message
        if error_message and isinstance(error_message, str):
            error_lower = error_message.lower()
            if 'file not found' in error_lower or 'executable not found' in error_lower:
                error_type = 'file_not_found'
            elif 'launch failed' in error_lower or 'failed to launch' in error_lower:
                error_type = 'launch_failed'
            elif 'connection' in error_lower or 'timeout' in error_lower:
                error_type = 'connection_error'
        
        self.websocket_handler.broadcast_message('error_notification', {
            'type': error_type,
            'title': 'Automation Run Failed',
            'message': error_message,
            'run_id': run_id,
            'game_name': run_data.get('game_name'),
            'sut_ip': run_data.get('sut_ip'),
            'timestamp': datetime.now().isoformat()
        })
        
        # Emit updated runs data
        runs_data = self.run_manager.get_all_runs()
        self.websocket_handler.broadcast_message('runs_update', runs_data)

        # Check if this run is part of a campaign and update campaign status
        self._check_campaign_completion(run_id, run_data)

    def _check_campaign_completion(self, run_id: str, run_data: Dict[str, Any]):
        """Check if a campaign is completed after a run finishes"""
        try:
            campaign_id = run_data.get('campaign_id')
            if not campaign_id:
                return

            if not hasattr(self, 'campaign_manager') or not self.campaign_manager:
                return

            campaign = self.campaign_manager.get_campaign(campaign_id)
            if not campaign:
                # Campaign might already be in history - check there too
                for hist_campaign in self.campaign_manager.get_campaign_history():
                    if hist_campaign.campaign_id == campaign_id:
                        campaign = hist_campaign
                        break
            if not campaign:
                return

            # Update campaign manifest on disk with run_ids
            if hasattr(self.run_manager, 'storage') and self.run_manager.storage:
                self.run_manager.storage.update_campaign_manifest(
                    campaign_id,
                    run_ids=campaign.run_ids,
                    status=campaign.status.value,
                    completed_at=campaign.completed_at.isoformat() if campaign.completed_at else None
                )

            # Broadcast campaign update
            self.websocket_handler.broadcast_message('campaign_updated', {
                'campaign_id': campaign_id,
                'campaign': campaign.to_dict()
            })

            # If campaign is done, broadcast completion
            if campaign.status.value in ['completed', 'failed', 'partially_completed']:
                logger.info(f"Campaign {campaign_id[:8]} finished with status: {campaign.status.value}")
                self.websocket_handler.broadcast_message('campaign_completed', {
                    'campaign_id': campaign_id,
                    'campaign': campaign.to_dict()
                })

        except Exception as e:
            logger.error(f"Error checking campaign completion: {e}")

    def _on_step_started(self, run_id: str, step_data: Dict[str, Any]):
        """Callback when an automation step starts"""
        logger.debug(f"Step started: {run_id} - step {step_data.get('step_number')}")
        self.websocket_handler.broadcast_message('step_started', {
            'run_id': run_id,
            'step': step_data
        })

    def _on_step_completed(self, run_id: str, step_data: Dict[str, Any]):
        """Callback when an automation step completes"""
        logger.debug(f"Step completed: {run_id} - step {step_data.get('step_number')}")
        self.websocket_handler.broadcast_message('step_completed', {
            'run_id': run_id,
            'step': step_data
        })

    def _on_step_failed(self, run_id: str, step_data: Dict[str, Any]):
        """Callback when an automation step fails"""
        logger.debug(f"Step failed: {run_id} - step {step_data.get('step_number')}")
        self.websocket_handler.broadcast_message('step_failed', {
            'run_id': run_id,
            'step': step_data
        })

    def run_server(self, host: str = None, port: int = None, debug: bool = None):
        """Run the Flask-SocketIO server"""
        host = host or self.config.host
        port = port or self.config.port
        debug = debug if debug is not None else self.config.debug
        
        try:
            self.start()
            logger.info(f"Starting server on {host}:{port} (debug={debug})")
            self.socketio.run(self.app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
        except KeyboardInterrupt:
            logger.info("Server interrupted by user")
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise
        finally:
            self.stop()
            
    def _monitor_loop(self):
        """Background monitoring loop"""
        logger.info("Monitor loop started")
        
        while self.running and not self._shutdown_event.wait(30):  # Check every 30 seconds
            try:
                self._perform_health_checks()
                self._emit_system_status()
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                
        logger.info("Monitor loop ended")
        
    def _perform_health_checks(self):
        """Perform periodic health checks"""
        try:
            # Check Omniparser status
            omniparser_status = self.omniparser_client.get_server_status()
            if not omniparser_status:
                omniparser_status = {"status": "unknown"}

            # Check device registry health
            device_stats = self.device_registry.get_device_stats()
            if not device_stats:
                device_stats = {"online_devices": 0, "total_devices": 0}

            # Check discovery service health
            discovery_status = self.discovery_service.get_discovery_status()
            if not discovery_status:
                discovery_status = {"running": False}

            logger.debug(f"Health check - Omniparser: {omniparser_status.get('status', 'unknown')}, "
                        f"Devices: {device_stats.get('online_devices', 0)}/{device_stats.get('total_devices', 0)}, "
                        f"Discovery: {discovery_status.get('running', False)}")
        except Exception as e:
            logger.debug(f"Health check error: {e}")
                    
    def _emit_system_status(self):
        """Emit system status to WebSocket clients"""
        status = self.get_system_status()
        self.websocket_handler.broadcast_message('system_status', status)
        
    def _test_omniparser_connection(self):
        """Test connection to Omniparser on startup"""
        if self.omniparser_client.test_connection():
            logger.info("[OK] Omniparser connection successful")
            event_bus.emit(EventType.OMNIPARSER_STATUS_CHANGED, {
                "status": "online",
                "url": self.config.omniparser_url
            })
        else:
            logger.warning("[FAIL] Omniparser connection failed")
            event_bus.emit(EventType.OMNIPARSER_STATUS_CHANGED, {
                "status": "offline",
                "url": self.config.omniparser_url
            })

    def _test_external_services(self):
        """Test connections to external microservices on startup"""
        # Test Discovery Service
        if self.discovery_client and self.discovery_client.is_available():
            logger.info(f"[OK] Discovery Service available at {self.config.discovery_service_url}")
        else:
            logger.warning(f"[WARN] Discovery Service not available at {self.config.discovery_service_url}")

        # Test Queue Service (OmniParser)
        if self.queue_client and self.queue_client.is_available():
            logger.info(f"[OK] Queue Service available at {self.config.queue_service_url}")
            event_bus.emit(EventType.OMNIPARSER_STATUS_CHANGED, {
                "status": "online",
                "url": self.config.queue_service_url
            })
        else:
            logger.warning(f"[WARN] Queue Service not available at {self.config.queue_service_url}")
            event_bus.emit(EventType.OMNIPARSER_STATUS_CHANGED, {
                "status": "offline",
                "url": self.config.queue_service_url
            })

        # Test Preset-Manager
        if self.preset_manager_client and self.preset_manager_client.is_available():
            logger.info(f"[OK] Preset-Manager available at {self.config.preset_manager_url}")
        else:
            logger.warning(f"[WARN] Preset-Manager not available at {self.config.preset_manager_url}")
            
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        try:
            if self.use_external_discovery:
                # Get status from external services
                device_stats = self.discovery_client.get_device_stats_sync() if self.discovery_client else {}
                if not device_stats:
                    device_stats = {"total_devices": 0, "online_devices": 0, "offline_devices": 0, "paired_devices": 0}

                discovery_status = self.discovery_client.get_discovery_status_sync() if self.discovery_client else {}
                if not discovery_status:
                    discovery_status = {"running": False, "external": True}
                else:
                    discovery_status["external"] = True

                omniparser_status = self.queue_client.get_server_status() if self.queue_client else {}
                if not omniparser_status:
                    omniparser_status = {"status": "unknown", "url": self.config.queue_service_url}

                return {
                    "backend": {
                        "running": self.running,
                        "version": "2.0.0",
                        "mode": "external_services",
                        "uptime": time.time(),
                        "websocket_clients": self.websocket_handler.get_connected_clients_count()
                    },
                    "discovery": discovery_status,
                    "devices": device_stats,
                    "omniparser": omniparser_status,
                    "services": {
                        "discovery_service": {
                            "url": self.config.discovery_service_url,
                            "available": self.discovery_client.is_available() if self.discovery_client else False
                        },
                        "queue_service": {
                            "url": self.config.queue_service_url,
                            "available": self.queue_client.is_available() if self.queue_client else False
                        },
                        "preset_manager": {
                            "url": self.config.preset_manager_url,
                            "available": self.preset_manager_client.is_available() if self.preset_manager_client else False
                        }
                    },
                    "config": {
                        "use_external_discovery": True,
                        "discovery_service_url": self.config.discovery_service_url,
                        "queue_service_url": self.config.queue_service_url,
                        "preset_manager_url": self.config.preset_manager_url
                    }
                }
            else:
                # Legacy internal mode
                device_stats = self.device_registry.get_device_stats()
                if not device_stats:
                    device_stats = {"total_devices": 0, "online_devices": 0, "offline_devices": 0, "paired_devices": 0, "discovery_rate": "0/0"}

                discovery_status = self.discovery_service.get_discovery_status()
                if not discovery_status:
                    discovery_status = {"running": False, "target_ips": 0}

                omniparser_status = self.omniparser_client.get_server_status()
                if not omniparser_status:
                    omniparser_status = {"status": "unknown", "url": self.config.omniparser_url}

                return {
                    "backend": {
                        "running": self.running,
                        "version": "2.0.0",
                        "mode": "internal_discovery",
                        "uptime": time.time(),
                        "websocket_clients": self.websocket_handler.get_connected_clients_count()
                    },
                    "discovery": discovery_status,
                    "devices": device_stats,
                    "omniparser": omniparser_status,
                    "config": {
                        "discovery_interval": self.config.discovery_interval,
                        "discovery_timeout": self.config.discovery_timeout,
                        "sut_port": self.config.sut_port
                    }
                }
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "backend": {"running": self.running, "version": "2.0.0", "error": str(e)},
                "discovery": {"running": False},
                "devices": {"total_devices": 0, "online_devices": 0},
                "omniparser": {"status": "error"}
            }
        
    def force_discovery_scan(self) -> Dict[str, Any]:
        """Force an immediate discovery scan"""
        logger.info("Forcing discovery scan via controller")
        return self.discovery_service.force_discovery_scan()
        
    def get_device_by_id(self, device_id: str):
        """Get device by ID"""
        return self.device_registry.get_device_by_id(device_id)
        
    def get_device_by_ip(self, ip: str):
        """Get device by IP"""
        return self.device_registry.get_device_by_ip(ip)
        
    def get_all_devices(self):
        """Get all devices"""
        return self.device_registry.get_all_devices()
        
    def get_online_devices(self):
        """Get online devices"""
        return self.device_registry.get_online_devices()
        
    def perform_sut_action(self, device_id: str, action: Dict[str, Any]):
        """Perform action on a SUT device"""
        device = self.device_registry.get_device_by_id(device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found")
            
        if not device.is_online:
            raise ValueError(f"Device {device_id} is not online")
            
        # Mark device as busy
        self.device_registry.set_device_busy(device_id, f"Performing {action.get('type', 'action')}")
        
        try:
            # Perform the action
            result = self.sut_client.perform_action(device.ip, device.port, action)
            
            # Emit event
            event_bus.emit(EventType.AUTOMATION_STARTED if result.success else EventType.AUTOMATION_FAILED, {
                "device_id": device_id,
                "action": action,
                "result": result.data if result.success else {"error": result.error}
            })
            
            return result
            
        finally:
            # Mark device as available again
            self.device_registry.set_device_online(device_id)
            
    def analyze_screenshot_with_omniparser(self, screenshot_path: str):
        """Analyze screenshot using Omniparser"""
        return self.omniparser_client.analyze_screenshot(screenshot_path)
        
    # Context manager support
    def __enter__(self):
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()