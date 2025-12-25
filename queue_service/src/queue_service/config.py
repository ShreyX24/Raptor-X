"""
Configuration for Queue Service.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QueueServiceConfig:
    """Queue Service configuration settings."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 9000

    # OmniParser target
    omniparser_url: str = "http://localhost:8000"

    # Queue settings
    request_timeout: int = 120  # Timeout for OmniParser requests in seconds
    max_queue_size: int = 100   # Maximum number of requests in queue

    # Dashboard settings
    stats_history_size: int = 100  # Number of historical stats to keep
    job_history_size: int = 50     # Number of jobs to keep in history

    # Logging
    log_level: str = "INFO"
    log_file: str = "queue_service.log"

    @classmethod
    def from_env(cls) -> "QueueServiceConfig":
        """Load configuration from environment variables."""
        return cls(
            host=os.getenv("QUEUE_SERVICE_HOST", "0.0.0.0"),
            port=int(os.getenv("QUEUE_SERVICE_PORT", "9000")),
            omniparser_url=os.getenv("OMNIPARSER_URL", "http://localhost:8000"),
            request_timeout=int(os.getenv("QUEUE_REQUEST_TIMEOUT", "120")),
            max_queue_size=int(os.getenv("QUEUE_MAX_SIZE", "100")),
            stats_history_size=int(os.getenv("QUEUE_STATS_HISTORY", "100")),
            job_history_size=int(os.getenv("QUEUE_JOB_HISTORY", "50")),
            log_level=os.getenv("QUEUE_LOG_LEVEL", "INFO"),
            log_file=os.getenv("QUEUE_LOG_FILE", "queue_service.log"),
        )


# Global config instance
_config: Optional[QueueServiceConfig] = None


def get_config() -> QueueServiceConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = QueueServiceConfig.from_env()
    return _config


def set_config(config: QueueServiceConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
