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


@dataclass
class SteamAccountPair:
    """Steam account pair for multi-SUT automation.

    Each pair has two accounts:
    - af_account: Used for games starting with A-F
    - gz_account: Used for games starting with G-Z

    This allows running two games concurrently on different SUTs
    without Steam login conflicts.
    """
    name: str  # Friendly name, e.g., "Pair 1"
    af_username: str  # Account for A-F games
    af_password: str
    gz_username: str  # Account for G-Z games
    gz_password: str
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "af_username": self.af_username,
            "af_password": self.af_password,
            "gz_username": self.gz_username,
            "gz_password": self.gz_password,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SteamAccountPair":
        return cls(
            name=data.get("name", ""),
            af_username=data.get("af_username", ""),
            af_password=data.get("af_password", ""),
            gz_username=data.get("gz_username", ""),
            gz_password=data.get("gz_password", ""),
            enabled=data.get("enabled", True),
        )

    def to_env_string(self) -> str:
        """Convert to string format for environment variable.

        Format: name:af_user:af_pass:gz_user:gz_pass
        """
        return f"{self.name}:{self.af_username}:{self.af_password}:{self.gz_username}:{self.gz_password}"

    @classmethod
    def from_env_string(cls, s: str) -> "SteamAccountPair":
        """Parse from environment variable string format."""
        parts = s.split(":")
        if len(parts) >= 5:
            return cls(
                name=parts[0],
                af_username=parts[1],
                af_password=parts[2],
                gz_username=parts[3],
                gz_password=parts[4],
                enabled=True,
            )
        raise ValueError(f"Invalid account pair format: {s}")


class SettingsManager:
    """Manages JSON configuration for the service manager"""

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._services: Dict[str, ServiceSettings] = {}
        self._profiles: Dict[str, Profile] = {}
        self._omniparser_servers: List[OmniParserServer] = []
        self._omniparser_instance_count: int = 0  # 0 = disabled, 1-5 = local instances
        self._steam_account_pairs: List[SteamAccountPair] = []
        self._steam_login_timeout: int = 180  # Default 3 minutes for slow connections
        self._active_profile: str = "local"
        self._project_dir: str = ""  # Base directory for all services
        self._omniparser_dir: str = ""  # OmniParser installation directory
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

            # Parse OmniParser instance count
            self._omniparser_instance_count = self._config.get("omniparser_instance_count", 0)

            # Parse Steam account pairs
            self._steam_account_pairs = [
                SteamAccountPair.from_dict(p)
                for p in self._config.get("steam_account_pairs", [])
            ]

            # Parse Steam login timeout
            self._steam_login_timeout = self._config.get("steam_login_timeout", 180)

            # Parse directory settings
            self._project_dir = self._config.get("project_dir", "")
            self._omniparser_dir = self._config.get("omniparser_dir", "")

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
                "project_dir": self._project_dir,
                "omniparser_dir": self._omniparser_dir,
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
                "omniparser_instance_count": self._omniparser_instance_count,
                "steam_account_pairs": [
                    pair.to_dict() for pair in self._steam_account_pairs
                ],
                "steam_login_timeout": self._steam_login_timeout,
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

    def get_omniparser_instance_count(self) -> int:
        """Get the number of local OmniParser instances to manage"""
        return self._omniparser_instance_count

    def set_omniparser_instance_count(self, count: int):
        """Set the number of local OmniParser instances to manage (0-5)"""
        self._omniparser_instance_count = max(0, min(5, count))

    def get_omniparser_urls_env(self) -> str:
        """Get enabled servers as comma-separated URLs for OMNIPARSER_URLS env var.

        If local instances are configured, generates localhost URLs for them.
        Otherwise, uses manually configured server URLs.
        """
        # If local instances are configured, generate URLs for them
        if self._omniparser_instance_count > 0:
            urls = [f"http://localhost:{8000 + i}" for i in range(self._omniparser_instance_count)]
            return ",".join(urls)

        # Otherwise use manually configured servers
        enabled = [s.url for s in self._omniparser_servers if s.enabled]
        return ",".join(enabled) if enabled else ""

    def get_project_dir(self) -> str:
        """Get the project base directory"""
        return self._project_dir

    def set_project_dir(self, path: str):
        """Set the project base directory"""
        self._project_dir = path

    def get_omniparser_dir(self) -> str:
        """Get the OmniParser installation directory"""
        return self._omniparser_dir

    def set_omniparser_dir(self, path: str):
        """Set the OmniParser installation directory"""
        self._omniparser_dir = path

    def get_steam_account_pairs(self) -> List[SteamAccountPair]:
        """Get all configured Steam account pairs"""
        return self._steam_account_pairs.copy()

    def set_steam_account_pairs(self, pairs: List[SteamAccountPair]):
        """Set the Steam account pairs list"""
        self._steam_account_pairs = pairs

    def get_steam_accounts_env(self) -> str:
        """Get enabled account pairs as a string for STEAM_ACCOUNT_PAIRS env var.

        Format: pair1_name:af_user:af_pass:gz_user:gz_pass|pair2_name:...
        Each pair is separated by |, fields within pair separated by :
        """
        enabled = [p for p in self._steam_account_pairs if p.enabled]
        if not enabled:
            return ""
        return "|".join(p.to_env_string() for p in enabled)

    def get_steam_login_timeout(self) -> int:
        """Get Steam login timeout in seconds"""
        return self._steam_login_timeout

    def set_steam_login_timeout(self, timeout: int):
        """Set Steam login timeout in seconds (min 30, max 600)"""
        self._steam_login_timeout = max(30, min(600, timeout))


# Global settings instance
_settings_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """Get the global settings manager instance"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
