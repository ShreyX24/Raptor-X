"""
Tracing Configuration Manager

Loads and manages the centralized tracing configuration from config/tracing.yaml.
Provides a single source of truth for all tracing agent settings.
"""

import os
import yaml
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Default config path relative to rpx-core
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "tracing.yaml"

# Fallback defaults if config file is missing
FALLBACK_CONFIG = {
    "output_dir": r"C:\Traces",
    "post_trace_buffer": 10,
    "ssh": {
        "timeout": 60,
        "max_retries": 3,
        "retry_delay": 5,
        "user": "",
    },
    "agents": {
        "socwatch": {
            "enabled": True,
            "description": "Intel SoC Watch",
            "path": r"C:\OWR\socwatch\64\socwatch.exe",
            "args": ["-f", "sys", "-f", "cpu", "-f", "power", "-f", "temp"],
            "duration_arg": "-t",
            "duration_style": "space",
            "output_arg": "-o",
            "output_style": "space",
            "has_duration": True,
        }
    }
}


class TracingConfig:
    """Manages tracing configuration loaded from YAML."""

    _instance: Optional['TracingConfig'] = None
    _config: Dict[str, Any] = {}
    _config_path: Path = DEFAULT_CONFIG_PATH

    def __new__(cls):
        """Singleton pattern - only one instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            if self._config_path.exists():
                with open(self._config_path, 'r') as f:
                    self._config = yaml.safe_load(f) or {}
                logger.info(f"Loaded tracing config from {self._config_path}")
            else:
                logger.warning(f"Tracing config not found at {self._config_path}, using fallback")
                self._config = FALLBACK_CONFIG.copy()
        except Exception as e:
            logger.error(f"Error loading tracing config: {e}, using fallback")
            self._config = FALLBACK_CONFIG.copy()

    def reload(self) -> None:
        """Reload configuration from disk."""
        self._load_config()

    @property
    def output_dir(self) -> str:
        """Base output directory for traces on SUT."""
        return self._config.get("output_dir", FALLBACK_CONFIG["output_dir"])

    @property
    def post_trace_buffer(self) -> int:
        """Seconds to wait after benchmark for agents to finish writing."""
        return self._config.get("post_trace_buffer", 10)

    @property
    def config(self) -> Dict[str, Any]:
        """Raw config dictionary (for direct access)."""
        return self._config

    @property
    def ssh_config(self) -> Dict[str, Any]:
        """SSH configuration for trace pulling."""
        return self._config.get("ssh", FALLBACK_CONFIG["ssh"])

    @property
    def ssh_timeout(self) -> int:
        """SSH connection timeout in seconds."""
        return self.ssh_config.get("timeout", 60)

    @property
    def ssh_max_retries(self) -> int:
        """Maximum SSH retry attempts."""
        return self.ssh_config.get("max_retries", 3)

    @property
    def ssh_user(self) -> Optional[str]:
        """SSH username (None to use current Windows user)."""
        user = self.ssh_config.get("user", "")
        return user if user else None

    @property
    def agents(self) -> Dict[str, Dict[str, Any]]:
        """All configured tracing agents."""
        return self._config.get("agents", {})

    def get_enabled_agents(self) -> Dict[str, Dict[str, Any]]:
        """Get only enabled tracing agents."""
        return {
            name: config
            for name, config in self.agents.items()
            if config.get("enabled", False)
        }

    def get_agent(self, name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific agent."""
        return self.agents.get(name)

    def is_agent_enabled(self, name: str) -> bool:
        """Check if an agent is enabled."""
        agent = self.get_agent(name)
        return agent.get("enabled", False) if agent else False

    def get_agent_command(self, name: str, duration: int, output_path: str) -> Optional[List[str]]:
        """
        Build the full command for an agent.

        Args:
            name: Agent name
            duration: Trace duration in seconds
            output_path: Full output path/prefix for trace files

        Returns:
            List of command arguments, or None if agent not found/disabled
        """
        agent = self.get_agent(name)
        if not agent or not agent.get("enabled", False):
            return None

        path = agent.get("path", "")
        if not path:
            logger.warning(f"Agent {name} has no path configured")
            return None

        # Start with base args
        args = list(agent.get("args", []))

        # Add duration argument
        duration_arg = agent.get("duration_arg", "")
        if duration_arg:
            if agent.get("duration_style") == "equals" or duration_arg.endswith("="):
                args.append(f"{duration_arg}{duration}")
            else:
                args.extend([duration_arg, str(duration)])

        # Add output argument
        output_arg = agent.get("output_arg", "")
        if output_arg:
            if agent.get("output_style") == "equals" or output_arg.endswith("="):
                args.append(f"{output_arg}{output_path}")
            else:
                args.extend([output_arg, output_path])

        return [path] + args

    def to_dict(self) -> Dict[str, Any]:
        """Return full config as dictionary (for API responses)."""
        return self._config.copy()

    def update(self, new_config: Dict[str, Any]) -> bool:
        """
        Update configuration and save to disk.

        Args:
            new_config: New configuration dictionary

        Returns:
            True if saved successfully
        """
        try:
            # Merge with existing config
            self._config.update(new_config)

            # Save to disk
            with open(self._config_path, 'w') as f:
                yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)

            logger.info(f"Saved tracing config to {self._config_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving tracing config: {e}")
            return False

    def update_agent(self, name: str, agent_config: Dict[str, Any]) -> bool:
        """
        Update a specific agent's configuration.

        Args:
            name: Agent name
            agent_config: New agent configuration

        Returns:
            True if saved successfully
        """
        if "agents" not in self._config:
            self._config["agents"] = {}

        self._config["agents"][name] = agent_config
        return self.update(self._config)

    def set_output_dir(self, output_dir: str) -> bool:
        """Update the base output directory."""
        self._config["output_dir"] = output_dir
        return self.update(self._config)


# Convenience function to get the singleton instance
def get_tracing_config() -> TracingConfig:
    """Get the tracing configuration singleton."""
    return TracingConfig()


# For backwards compatibility - convert to old format
def get_tracing_agents_dict() -> Dict[str, Dict[str, Any]]:
    """
    Get tracing agents in the legacy format used by simple_automation.py.

    Returns dict like:
    {
        "socwatch": {
            "path": "...",
            "base_args": [...],
            "duration_arg": "-t",
            "output_arg": "-o",
            "runs_indefinitely": False,
        }
    }
    """
    config = get_tracing_config()
    result = {}

    for name, agent in config.get_enabled_agents().items():
        result[name] = {
            "path": agent.get("path", ""),
            "base_args": agent.get("args", []),
            "duration_arg": agent.get("duration_arg", ""),
            "output_arg": agent.get("output_arg", ""),
            "runs_indefinitely": not agent.get("has_duration", True),
            "output_filename_only": agent.get("output_filename_only", False),
        }

    return result
