"""
Service configuration definitions
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

BASE_DIR = Path("D:/Code/Gemma")


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


SERVICES = [
    ServiceConfig(
        name="sut-discovery",
        display_name="SUT Discovery",
        command=["sut-discovery", "--port", "5001"],
        working_dir=BASE_DIR / "sut_discovery_service",
        port=5001,
        group="Core Services",
    ),
    ServiceConfig(
        name="queue-service",
        display_name="Queue Service",
        command=["queue-service", "--port", "9000"],
        working_dir=BASE_DIR / "queue_service",
        port=9000,
        group="Core Services",
    ),
    ServiceConfig(
        name="gemma-backend",
        display_name="Gemma Backend",
        command=["gemma", "--port", "5000"],
        working_dir=BASE_DIR / "Gemma",
        port=5000,
        group="Gemma",
        depends_on=["sut-discovery"],
    ),
    ServiceConfig(
        name="gemma-frontend",
        display_name="Gemma Frontend",
        command=["cmd", "/c", "npm", "run", "dev", "--", "--host"],
        working_dir=BASE_DIR / "Gemma" / "admin",
        port=3000,
        group="Gemma",
        depends_on=["gemma-backend"],
        startup_delay=2.0,
    ),
    ServiceConfig(
        name="preset-manager",
        display_name="Preset Manager",
        command=["preset-manager", "--port", "5002"],
        working_dir=BASE_DIR / "preset-manager",
        port=5002,
        group="Preset Manager",
        depends_on=["sut-discovery"],
        env_vars={"USE_EXTERNAL_DISCOVERY": "true"},
    ),
    ServiceConfig(
        name="pm-frontend",
        display_name="PM Frontend",
        command=["cmd", "/c", "npm", "run", "dev", "--", "--host", "--port", "3001"],
        working_dir=BASE_DIR / "preset-manager" / "admin",
        port=3001,
        group="Preset Manager",
        depends_on=["preset-manager"],
        startup_delay=2.0,
    ),
    ServiceConfig(
        name="sut-client",
        display_name="SUT Client",
        command=["sut-client"],
        working_dir=BASE_DIR / "preset-manager",
        port=8080,
        group="SUT",
        env_vars={"SUT_CLIENT_PORT": "8080"},
        enabled=False,  # Not needed on server, user can start manually for testing
    ),
]


def get_service_by_name(name: str) -> Optional[ServiceConfig]:
    """Get service config by name"""
    for service in SERVICES:
        if service.name == name:
            return service
    return None


def get_services_by_group() -> dict:
    """Get services organized by group"""
    groups = {}
    for service in SERVICES:
        if service.group not in groups:
            groups[service.group] = []
        groups[service.group].append(service)
    return groups


def apply_settings_to_services():
    """Apply JSON settings to service configs"""
    from .settings import get_settings_manager

    settings = get_settings_manager()

    for service in SERVICES:
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
