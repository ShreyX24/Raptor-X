"""
Service configuration definitions
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

# Default paths (used if settings not configured)
_DEFAULT_BASE_DIR = Path("C:/Users/shrey/OneDrive/Documents/Code/Gemma/Gemma-e2e")
_DEFAULT_OMNIPARSER_DIR = Path("C:/Users/shrey/OneDrive/Documents/Code/Gemma/Gemma-e2e/Omniparser server/omnitool/omniparserserver")

# OmniParser configuration
OMNIPARSER_BASE_PORT = 8000
OMNIPARSER_MAX_INSTANCES = 5


def get_base_dir() -> Path:
    """Get the project base directory from settings or default"""
    from .settings import get_settings_manager
    settings = get_settings_manager()
    project_dir = settings.get_project_dir()
    if project_dir:
        return Path(project_dir)
    return _DEFAULT_BASE_DIR


def get_omniparser_dir() -> Path:
    """Get the OmniParser directory from settings or default"""
    from .settings import get_settings_manager
    settings = get_settings_manager()
    omni_dir = settings.get_omniparser_dir()
    if omni_dir:
        return Path(omni_dir)
    return _DEFAULT_OMNIPARSER_DIR


@dataclass
class ServiceConfig:
    """Configuration for a single service"""
    name: str
    display_name: str
    command: List[str]
    working_dir: Path
    port: Optional[int] = None
    host: str = "localhost"
    group: str = "Services"
    depends_on: List[str] = field(default_factory=list)
    env_vars: dict = field(default_factory=dict)
    startup_delay: float = 0.0
    remote: bool = False
    enabled: bool = True
    health_path: str = "/"  # Path for health check endpoint


def get_services() -> List[ServiceConfig]:
    """Get list of service configurations with current base directory"""
    base_dir = get_base_dir()
    return [
        ServiceConfig(
            name="sut-discovery",
            display_name="SUT Discovery",
            command=["sut-discovery", "--port", "5001"],
            working_dir=base_dir / "sut_discovery_service",
            port=5001,
            group="Core Services",
            health_path="/health",  # No /api prefix for health router
        ),
        ServiceConfig(
            name="queue-service",
            display_name="Queue Service",
            command=["queue-service", "--port", "9000"],
            working_dir=base_dir / "queue_service",
            port=9000,
            group="Core Services",
            health_path="/health",
        ),
        ServiceConfig(
            name="gemma-backend",
            display_name="Gemma Backend",
            command=["gemma", "--port", "5000"],
            working_dir=base_dir / "Gemma",
            port=5000,
            group="Gemma",
            depends_on=["sut-discovery"],
            health_path="/api/status",
        ),
        ServiceConfig(
            name="gemma-frontend",
            display_name="Gemma Frontend",
            command=["cmd", "/c", "npm", "run", "dev", "--", "--host", "--port", "3000"],
            working_dir=base_dir / "Gemma" / "admin",
            port=3000,
            group="Gemma",
            depends_on=["gemma-backend"],
            startup_delay=3.0,  # Wait for backend to be ready
            health_path="/",  # Vite dev server
        ),
        ServiceConfig(
            name="preset-manager",
            display_name="Preset Manager",
            command=["preset-manager", "--port", "5002"],
            working_dir=base_dir / "preset-manager",
            port=5002,
            group="Preset Manager",
            depends_on=["sut-discovery"],
            env_vars={"USE_EXTERNAL_DISCOVERY": "true"},
            health_path="/health",  # No /api prefix
        ),
        ServiceConfig(
            name="pm-frontend",
            display_name="PM Frontend",
            command=["cmd", "/c", "npm", "run", "dev", "--", "--host", "--port", "3001"],
            working_dir=base_dir / "preset-manager" / "admin",
            port=3001,
            group="Preset Manager",
            depends_on=["preset-manager"],
            startup_delay=3.0,  # Wait for backend to be ready
            health_path="/",  # Vite dev server
        ),
        ServiceConfig(
            name="sut-client",
            display_name="SUT Client",
            command=["sut-client"],
            working_dir=base_dir / "sut_client",
            port=8080,
            group="SUT",
            env_vars={"SUT_CLIENT_PORT": "8080"},
            enabled=False,  # Not needed on server, user can start manually for testing
            health_path="/health",
        ),
    ]


def get_service_by_name(name: str) -> Optional[ServiceConfig]:
    """Get service config by name"""
    for service in get_services():
        if service.name == name:
            return service
    return None


def get_services_by_group() -> dict:
    """Get services organized by group"""
    groups = {}
    for service in get_services():
        if service.group not in groups:
            groups[service.group] = []
        groups[service.group].append(service)
    return groups


def apply_settings_to_services(services: List[ServiceConfig]):
    """Apply JSON settings to service configs"""
    from .settings import get_settings_manager

    settings = get_settings_manager()

    for service in services:
        svc_settings = settings.get_service_settings(service.name)
        service.host = svc_settings.host
        if svc_settings.port:
            service.port = svc_settings.port
        service.remote = svc_settings.remote
        service.enabled = svc_settings.enabled
        # Merge env vars (settings override defaults)
        if svc_settings.env_vars:
            service.env_vars = {**service.env_vars, **svc_settings.env_vars}


def get_host_port_display(service: ServiceConfig) -> str:
    """Get formatted host:port string for display"""
    if service.port:
        return f"{service.host}:{service.port}"
    return service.host


def create_omniparser_config(instance: int) -> ServiceConfig:
    """Create config for an OmniParser instance (0-indexed)"""
    port = OMNIPARSER_BASE_PORT + instance
    return ServiceConfig(
        name=f"omniparser-{port}",
        display_name=f"OmniParser {port}",
        # --no-reload ensures logs appear in service manager (no child process)
        command=["python", "-m", "omniparserserver", "--use_paddleocr", "--port", str(port), "--no-reload"],
        working_dir=get_omniparser_dir(),
        port=port,
        group="OmniParser",
        enabled=True,
        health_path="/probe/",  # OmniParser uses /probe/ for health checks
    )
