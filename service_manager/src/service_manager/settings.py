"""
Settings Manager - JSON configuration for service manager
"""

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
import os


# Config file location
CONFIG_DIR = Path.home() / ".gemma"
CONFIG_FILE = CONFIG_DIR / "service_manager_config.json"


@dataclass
class ServiceSettings:
    """Runtime settings for a service"""
    host: str = "localhost"
    port: int = 0
    enabled: bool = True
    remote: bool = False
    env_vars: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ServiceSettings":
        return cls(
            host=data.get("host", "localhost"),
            port=data.get("port", 0),
            enabled=data.get("enabled", True),
            remote=data.get("remote", False),
            env_vars=data.get("env_vars", {}),
        )


@dataclass
class Profile:
    """Configuration profile for different environments"""
    name: str
    description: str = ""
    overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "overrides": self.overrides,
        }

    @classmethod
    def from_dict(cls, name: str, data: dict) -> "Profile":
        return cls(
            name=name,
            description=data.get("description", ""),
            overrides=data.get("overrides", {}),
        )


@dataclass
class OmniParserServer:
    """Configuration for an OmniParser server instance"""
    name: str
    url: str
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OmniParserServer":
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            enabled=data.get("enabled", True),
        )


class SettingsManager:
    """Manages JSON configuration for the service manager"""

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._services: Dict[str, ServiceSettings] = {}
        self._profiles: Dict[str, Profile] = {}
        self._omniparser_servers: List[OmniParserServer] = []
        self._active_profile: str = "local"
        self._loaded = False

    @property
    def is_first_run(self) -> bool:
        """Check if this is first run (no config file exists)"""
        return not CONFIG_FILE.exists()

    @property
    def active_profile(self) -> str:
        return self._active_profile

    @active_profile.setter
    def active_profile(self, value: str):
        if value in self._profiles:
            self._active_profile = value

    def load(self) -> bool:
        """Load configuration from JSON file"""
        if not CONFIG_FILE.exists():
            return False

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                self._config = json.load(f)

            # Parse services
            for name, data in self._config.get("services", {}).items():
                self._services[name] = ServiceSettings.from_dict(data)

            # Parse profiles
            for name, data in self._config.get("profiles", {}).items():
                self._profiles[name] = Profile.from_dict(name, data)

            # Parse OmniParser servers
            self._omniparser_servers = [
                OmniParserServer.from_dict(s)
                for s in self._config.get("omniparser_servers", [])
            ]

            self._active_profile = self._config.get("active_profile", "local")
            self._loaded = True
            return True

        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config: {e}")
            return False

    def save(self) -> bool:
        """Save configuration to JSON file"""
        try:
            # Ensure config directory exists
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)

            # Build config dict
            config = {
                "version": "1.0",
                "default_host": self._config.get("default_host", "localhost"),
                "services": {
                    name: settings.to_dict()
                    for name, settings in self._services.items()
                },
                "profiles": {
                    name: profile.to_dict()
                    for name, profile in self._profiles.items()
                },
                "omniparser_servers": [
                    server.to_dict() for server in self._omniparser_servers
                ],
                "active_profile": self._active_profile,
            }

            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

            return True

        except IOError as e:
            print(f"Error saving config: {e}")
            return False

    def get_service_settings(self, service_name: str) -> ServiceSettings:
        """Get settings for a service, applying active profile overrides"""
        base = self._services.get(service_name, ServiceSettings())

        # Apply profile overrides
        profile = self._profiles.get(self._active_profile)
        if profile and service_name in profile.overrides:
            overrides = profile.overrides[service_name]
            return ServiceSettings(
                host=overrides.get("host", base.host),
                port=overrides.get("port", base.port),
                enabled=overrides.get("enabled", base.enabled),
                remote=overrides.get("remote", base.remote),
                env_vars={**base.env_vars, **overrides.get("env_vars", {})},
            )

        return base

    def set_service_settings(self, service_name: str, settings: ServiceSettings):
        """Set settings for a service"""
        self._services[service_name] = settings

    def get_all_services(self) -> Dict[str, ServiceSettings]:
        """Get all service settings"""
        return self._services.copy()

    def get_profiles(self) -> Dict[str, Profile]:
        """Get all profiles"""
        return self._profiles.copy()

    def add_profile(self, profile: Profile):
        """Add or update a profile"""
        self._profiles[profile.name] = profile

    def delete_profile(self, name: str) -> bool:
        """Delete a profile (cannot delete 'local')"""
        if name == "local" or name not in self._profiles:
            return False
        del self._profiles[name]
        if self._active_profile == name:
            self._active_profile = "local"
        return True

    def create_default_config(self, service_configs: list):
        """Create default configuration from service configs"""
        # Create default service settings
        for config in service_configs:
            self._services[config.name] = ServiceSettings(
                host="localhost",
                port=config.port or 0,
                enabled=True,
                remote=False,
                env_vars=dict(config.env_vars) if config.env_vars else {},
            )

        # Create default profiles
        self._profiles["local"] = Profile(
            name="local",
            description="All services on localhost",
            overrides={},
        )

        self._active_profile = "local"
        self._config["default_host"] = "localhost"

    def apply_wizard_config(self, service_settings: Dict[str, ServiceSettings]):
        """Apply configuration from setup wizard"""
        self._services.update(service_settings)

    def get_omniparser_servers(self) -> List[OmniParserServer]:
        """Get all configured OmniParser servers"""
        return self._omniparser_servers.copy()

    def set_omniparser_servers(self, servers: List[OmniParserServer]):
        """Set the OmniParser server list"""
        self._omniparser_servers = servers

    def get_omniparser_urls_env(self) -> str:
        """Get enabled servers as comma-separated URLs for OMNIPARSER_URLS env var"""
        enabled = [s.url for s in self._omniparser_servers if s.enabled]
        return ",".join(enabled) if enabled else ""


# Global settings instance
_settings_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """Get the global settings manager instance"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
