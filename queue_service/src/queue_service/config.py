"""
Configuration for Queue Service.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List


def _parse_omniparser_urls() -> List[str]:
    """Parse OmniParser URLs from environment.

    Supports both OMNIPARSER_URLS (comma-separated list from Service Manager)
    and OMNIPARSER_URL (single URL) for backwards compatibility.
    """
    # Check plural form first (from Service Manager)
    urls_str = os.getenv("OMNIPARSER_URLS", "")
    if urls_str:
        return [url.strip() for url in urls_str.split(",") if url.strip()]
    # Fall back to singular form
    single = os.getenv("OMNIPARSER_URL", "http://localhost:8000")
    return [single]


@dataclass
class QueueServiceConfig:
    """Queue Service configuration settings."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 9000

    # OmniParser targets (supports multiple servers for load balancing)
    omniparser_urls: List[str] = field(default_factory=lambda: ["http://localhost:8000"])

    # Queue settings
    request_timeout: int = 120  # Timeout for OmniParser requests in seconds
    max_queue_size: int = 100   # Maximum number of requests in queue
    num_workers: int = 0        # Number of parallel workers (0 = auto: one per OmniParser URL)

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
            omniparser_urls=_parse_omniparser_urls(),
            request_timeout=int(os.getenv("QUEUE_REQUEST_TIMEOUT", "120")),
            max_queue_size=int(os.getenv("QUEUE_MAX_SIZE", "100")),
            num_workers=int(os.getenv("QUEUE_NUM_WORKERS", "0")),  # 0 = auto
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
