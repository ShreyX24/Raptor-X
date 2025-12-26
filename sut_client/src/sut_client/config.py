"""
SUT Client Configuration
"""

import os
import socket
import uuid
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


def get_machine_id() -> str:
    """Generate a unique machine ID"""
    hostname = socket.gethostname()
    mac = uuid.getnode()
    return f"sut_{hostname}_{mac:012x}"


class SUTSettings(BaseSettings):
    """SUT Client configuration"""

    # Service settings
    host: str = Field(default="0.0.0.0", description="Service host")
    port: int = Field(default=8080, description="Service port")

    # Device identification
    device_id: str = Field(default_factory=get_machine_id, description="Unique device ID")
    hostname: str = Field(default_factory=socket.gethostname, description="Machine hostname")

    # Backup settings
    backup_dir: Path = Field(
        default_factory=lambda: Path.cwd() / "data" / "backups",
        description="Backup directory"
    )
    max_backups_per_game: int = Field(default=5, description="Max backups per game")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    # Timeouts
    request_timeout: int = Field(default=30, description="HTTP request timeout")

    # ==========================================================================
    # Game Launch Settings (from KATANA Gemma v0.2)
    # ==========================================================================

    # Window detection timeouts (pywinauto)
    pywinauto_visible_timeout: int = Field(
        default=120,
        description="Timeout for window to become visible (seconds)"
    )
    pywinauto_ready_timeout: int = Field(
        default=30,
        description="Timeout for window to become ready/idle (seconds)"
    )

    # Launch retry settings
    launch_retry_count: int = Field(
        default=5,
        description="Number of retries for foreground detection"
    )
    launch_retry_interval: int = Field(
        default=10,
        description="Seconds between foreground detection retries"
    )

    # Process detection
    max_process_wait_time: int = Field(
        default=60,
        description="Max time to wait for game process to appear (seconds)"
    )

    model_config = {
        "env_prefix": "SUT_CLIENT_",
        "env_file": ".env",
        "extra": "ignore"
    }


def get_settings() -> SUTSettings:
    """Get SUT settings singleton"""
    if not hasattr(get_settings, '_settings'):
        get_settings._settings = SUTSettings()
    return get_settings._settings
