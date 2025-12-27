"""
Configuration for SUT Discovery Service.
"""

import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DiscoveryServiceConfig:
    """SUT Discovery Service configuration settings."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 5001

    # Discovery settings
    udp_port: int = 9999
    udp_broadcast_interval: float = 1.0
    sut_port: int = 8080

    # Device settings
    offline_timeout: int = 30  # Seconds before device is marked offline
    stale_device_timeout: int = 300  # Seconds before unpaired offline devices are removed (default 5 min)
    paired_devices_file: str = "paired_devices.json"

    # Network settings
    network_ranges: List[str] = None

    # Logging
    log_level: str = "INFO"
    log_file: str = "sut_discovery.log"

    @classmethod
    def from_env(cls) -> "DiscoveryServiceConfig":
        """Load configuration from environment variables."""
        return cls(
            host=os.getenv("DISCOVERY_HOST", "0.0.0.0"),
            port=int(os.getenv("DISCOVERY_PORT", "5001")),
            udp_port=int(os.getenv("DISCOVERY_UDP_PORT", "9999")),
            udp_broadcast_interval=float(os.getenv("DISCOVERY_UDP_INTERVAL", "1.0")),
            sut_port=int(os.getenv("SUT_PORT", "8080")),
            offline_timeout=int(os.getenv("DISCOVERY_OFFLINE_TIMEOUT", "30")),
            stale_device_timeout=int(os.getenv("DISCOVERY_STALE_TIMEOUT", "300")),
            paired_devices_file=os.getenv("PAIRED_DEVICES_FILE", "paired_devices.json"),
            log_level=os.getenv("DISCOVERY_LOG_LEVEL", "INFO"),
            log_file=os.getenv("DISCOVERY_LOG_FILE", "sut_discovery.log"),
        )


# Global config instance
_config: Optional[DiscoveryServiceConfig] = None


def get_config() -> DiscoveryServiceConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = DiscoveryServiceConfig.from_env()
    return _config


def set_config(config: DiscoveryServiceConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
