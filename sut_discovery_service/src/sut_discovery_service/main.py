"""
SUT Discovery Service - FastAPI application entry point.
"""

import argparse
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .config import get_config, set_config, DiscoveryServiceConfig
from .discovery import get_device_registry, get_ws_manager, UDPAnnouncer
from .utils import NetworkDiscovery
from .api import suts_router, proxy_router, health_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# Global announcer instance
_udp_announcer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    global _udp_announcer
    config = get_config()

    # Add file handler if configured
    if config.log_file:
        file_handler = logging.FileHandler(config.log_file)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        logging.getLogger().addHandler(file_handler)
        logger.info(f"Logging to file: {config.log_file}")

    # Startup
    logger.info("=" * 60)
    logger.info("SUT Discovery Service v1.0.0")
    logger.info("=" * 60)
    logger.info(f"Host: {config.host}:{config.port}")
    logger.info(f"UDP Port: {config.udp_port}")
    logger.info("=" * 60)

    # Get host IP for broadcasting
    host_ip = NetworkDiscovery.get_host_ip()
    logger.info(f"Broadcasting on IP: {host_ip}")

    # Initialize device registry
    registry = get_device_registry()
    stats = registry.get_device_stats()
    logger.info(f"Loaded {stats['paired_devices']} paired devices")

    # Start UDP announcer
    _udp_announcer = UDPAnnouncer(
        service_ip=host_ip,
        ws_port=config.port,
        udp_port=config.udp_port,
        interval=config.udp_broadcast_interval,
        service_name="sut-discovery-service"
    )
    _udp_announcer.start()
    logger.info(f"UDP Announcer started on port {config.udp_port}")

    logger.info("=" * 60)
    logger.info("Discovery Service ready - SUTs can now connect")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("Shutting down SUT Discovery Service")
    if _udp_announcer:
        _udp_announcer.stop()
    registry.save_paired_devices()
    logger.info("Discovery Service stopped")


# FastAPI app with lifespan
app = FastAPI(
    title="SUT Discovery Service",
    description="Central gateway for all SUT communication",
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

# Register routers with /api prefix
app.include_router(suts_router, prefix="/api")
app.include_router(proxy_router, prefix="/api")
app.include_router(health_router)


def main():
    """Run the SUT Discovery Service."""
    parser = argparse.ArgumentParser(description="SUT Discovery Service")
    parser.add_argument(
        "--port",
        type=int,
        default=5001,
        help="Port to run the service on (default: 5001)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--udp-port",
        type=int,
        default=9999,
        help="UDP broadcast port (default: 9999)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )

    args = parser.parse_args()

    # Update configuration
    config = DiscoveryServiceConfig(
        host=args.host,
        port=args.port,
        udp_port=args.udp_port,
        log_level=args.log_level,
    )
    set_config(config)

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    logger.info(f"Starting SUT Discovery Service on {args.host}:{args.port}")

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
    )


if __name__ == "__main__":
    main()
