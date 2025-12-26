"""
Queue Service - FastAPI application entry point.
"""

import argparse
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .config import get_config, set_config, QueueServiceConfig
from .queue_manager import start_queue_manager, stop_queue_manager, get_queue_manager
from .api import parse_router, stats_router, health_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    config = get_config()

    # Add file handler if configured
    if config.log_file:
        file_handler = logging.FileHandler(config.log_file)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        logging.getLogger().addHandler(file_handler)

    # Startup
    logger.info("=" * 60)
    logger.info("Queue Service v1.0.0 - OmniParser Request Queue")
    logger.info("=" * 60)
    logger.info(f"OmniParser servers ({len(config.omniparser_urls)}): {config.omniparser_urls}")
    logger.info(f"Load balancing: round-robin")
    logger.info(f"Request timeout: {config.request_timeout}s")
    logger.info(f"Max queue size: {config.max_queue_size}")
    logger.info("=" * 60)

    await start_queue_manager()

    yield

    # Shutdown
    logger.info("Shutting down Queue Service")
    await stop_queue_manager()


# FastAPI app with lifespan
app = FastAPI(
    title="Queue Service",
    description="OmniParser request queue middleware with terminal dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(parse_router)
app.include_router(stats_router)
app.include_router(health_router)


def main():
    """Run the queue service."""
    parser = argparse.ArgumentParser(description="Queue Service - OmniParser Request Queue")
    parser.add_argument(
        "--port",
        type=int,
        default=9000,
        help="Port to run the service on (default: 9000)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--omniparser-urls",
        type=str,
        default=None,
        help="Comma-separated OmniParser server URLs (overrides OMNIPARSER_URLS env var)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Request timeout in seconds (default: 120)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )

    args = parser.parse_args()

    # Parse OmniParser URLs from CLI argument if provided
    omniparser_urls = None
    if args.omniparser_urls:
        omniparser_urls = [url.strip() for url in args.omniparser_urls.split(",") if url.strip()]

    # Update configuration (uses env vars if CLI args not provided)
    base_config = QueueServiceConfig.from_env()
    config = QueueServiceConfig(
        host=args.host,
        port=args.port,
        omniparser_urls=omniparser_urls or base_config.omniparser_urls,
        request_timeout=args.timeout,
        log_level=args.log_level,
    )
    set_config(config)

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    logger.info(f"Starting Queue Service on {args.host}:{args.port}")
    logger.info(f"OmniParser servers: {config.omniparser_urls}")

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
    )


if __name__ == "__main__":
    main()
