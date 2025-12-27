"""
Device registry for tracking SUT devices and their states.
"""

import logging
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from enum import Enum

from .events import event_bus, EventType

logger = logging.getLogger(__name__)


class SUTStatus(Enum):
    """SUT status enumeration."""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class SUTDevice:
    """SUT device information with pairing support."""
    ip: str
    port: int
    unique_id: str
    hostname: str = ""
    status: SUTStatus = SUTStatus.UNKNOWN
    capabilities: List[str] = field(default_factory=list)
    last_seen: datetime = field(default_factory=datetime.now)
    first_discovered: datetime = field(default_factory=datetime.now)
    current_task: Optional[str] = None
    error_count: int = 0
    total_pings: int = 0
    successful_pings: int = 0

    # Pairing mode fields
    is_paired: bool = False
    paired_at: Optional[datetime] = None
    paired_by: str = "system"
    pair_priority: int = 1

    # Display name and hardware info
    display_name: Optional[str] = None
    cpu_model: Optional[str] = None

    @property
    def success_rate(self) -> float:
        """Calculate ping success rate."""
        if self.total_pings == 0:
            return 0.0
        return self.successful_pings / self.total_pings

    @property
    def is_online(self) -> bool:
        """Check if device is considered online."""
        return self.status == SUTStatus.ONLINE

    @property
    def age_seconds(self) -> int:
        """Get age of device discovery in seconds."""
        return int((datetime.now() - self.first_discovered).total_seconds())

    @property
    def last_seen_seconds(self) -> int:
        """Get seconds since last seen."""
        return int((datetime.now() - self.last_seen).total_seconds())

    def pair_device(self, paired_by: str = "user") -> None:
        """Pair this device for priority scanning."""
        self.is_paired = True
        self.paired_at = datetime.now()
        self.paired_by = paired_by
        self.pair_priority = 1

    def unpair_device(self) -> None:
        """Unpair this device."""
        self.is_paired = False
        self.paired_at = None
        self.paired_by = "system"
        self.pair_priority = 1

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            "unique_id": self.unique_id,
            "ip": self.ip,
            "port": self.port,
            "hostname": self.hostname,
            "status": self.status.value,
            "is_online": self.is_online,
            "is_paired": self.is_paired,
            "display_name": self.display_name,
            "cpu_model": self.cpu_model,
            "capabilities": self.capabilities,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "first_discovered": self.first_discovered.isoformat() if self.first_discovered else None,
            "paired_at": self.paired_at.isoformat() if self.paired_at else None,
            "success_rate": round(self.success_rate, 2),
            "error_count": self.error_count,
        }


class DevicePersistence:
    """Handles persistence of paired SUT devices to JSON file."""

    def __init__(self, persistence_file: str = "paired_devices.json"):
        self.persistence_file = persistence_file
        self.cpu_directory: Dict[str, int] = {}
        logger.info(f"DevicePersistence initialized with file: {self.persistence_file}")

    def save_paired_devices(self, devices: Dict[str, SUTDevice]) -> bool:
        """Save paired devices to JSON file."""
        try:
            paired_devices = {
                device_id: device for device_id, device in devices.items()
                if device.is_paired
            }

            if not paired_devices:
                logger.info("No paired devices to save")
                return True

            serializable_data = {
                "version": "1.0",
                "saved_at": datetime.now().isoformat(),
                "paired_devices": {},
                "cpu_directory": self.cpu_directory
            }

            for device_id, device in paired_devices.items():
                device_dict = asdict(device)
                device_dict['last_seen'] = device.last_seen.isoformat() if device.last_seen else None
                device_dict['first_discovered'] = device.first_discovered.isoformat() if device.first_discovered else None
                device_dict['paired_at'] = device.paired_at.isoformat() if device.paired_at else None
                device_dict['status'] = device.status.value
                serializable_data["paired_devices"][device_id] = device_dict

            with open(self.persistence_file, 'w') as f:
                json.dump(serializable_data, f, indent=2)

            logger.info(f"Saved {len(paired_devices)} paired devices to {self.persistence_file}")
            return True

        except Exception as e:
            logger.error(f"Error saving paired devices: {str(e)}")
            return False

    def load_paired_devices(self) -> Dict[str, SUTDevice]:
        """Load paired devices from JSON file."""
        if not os.path.exists(self.persistence_file):
            logger.info(f"Paired devices file not found: {self.persistence_file}")
            return {}

        try:
            with open(self.persistence_file, 'r') as f:
                data = json.load(f)

            self.cpu_directory = data.get("cpu_directory", {})
            paired_devices = {}
            devices_data = data.get("paired_devices", {})

            for device_id, device_dict in devices_data.items():
                if device_dict.get('last_seen'):
                    device_dict['last_seen'] = datetime.fromisoformat(device_dict['last_seen'])
                if device_dict.get('first_discovered'):
                    device_dict['first_discovered'] = datetime.fromisoformat(device_dict['first_discovered'])
                if device_dict.get('paired_at'):
                    device_dict['paired_at'] = datetime.fromisoformat(device_dict['paired_at'])
                if 'status' in device_dict:
                    device_dict['status'] = SUTStatus(device_dict['status'])

                device = SUTDevice(**device_dict)
                paired_devices[device_id] = device

            logger.info(f"Loaded {len(paired_devices)} paired devices from {self.persistence_file}")
            return paired_devices

        except Exception as e:
            logger.error(f"Error loading paired devices: {str(e)}")
            return {}

    def suggest_display_name(self, cpu_model: str) -> str:
        """Suggest a display name based on CPU model."""
        import re
        if not cpu_model:
            return "SUT"

        # Intel Core Ultra series
        match = re.search(r'Ultra\s+\d+\s+\w+', cpu_model, re.IGNORECASE)
        if match:
            short_name = match.group(0)
        # Intel Core i-series
        elif match := re.search(r'i[3579]-\w+', cpu_model, re.IGNORECASE):
            short_name = match.group(0)
        # AMD Ryzen series
        elif match := re.search(r'Ryzen\s+\d+\s+\w+', cpu_model, re.IGNORECASE):
            short_name = match.group(0)
        else:
            parts = cpu_model.split()
            short_name = ' '.join(parts[-2:]) if len(parts) >= 2 else cpu_model

        current_count = self.cpu_directory.get(cpu_model, 0)
        next_number = current_count + 1

        if next_number == 1:
            return short_name
        else:
            return f"{short_name} - {next_number}"


class DeviceRegistry:
    """Registry for managing SUT devices."""

    def __init__(self, offline_timeout: int = 30, stale_device_timeout: int = 300, persistence_file: str = "paired_devices.json"):
        self.devices: Dict[str, SUTDevice] = {}
        self.ip_to_id_mapping: Dict[str, str] = {}
        self.offline_timeout = offline_timeout
        self.stale_device_timeout = stale_device_timeout  # Default 5 minutes
        self.persistence = DevicePersistence(persistence_file)
        self.load_paired_devices_on_startup()

    def register_device(
        self,
        ip: str,
        port: int,
        unique_id: str,
        capabilities: List[str] = None,
        hostname: str = "",
        cpu_model: str = None,
        display_name: str = None
    ) -> SUTDevice:
        """Register or update a SUT device."""
        capabilities = capabilities or []

        if unique_id in self.devices:
            device = self.devices[unique_id]
            old_status = device.status

            device.ip = ip
            device.port = port
            device.hostname = hostname
            device.capabilities = capabilities
            device.last_seen = datetime.now()
            device.successful_pings += 1
            device.total_pings += 1

            if cpu_model:
                device.cpu_model = cpu_model
            if display_name:
                device.display_name = display_name

            if device.status == SUTStatus.OFFLINE:
                device.status = SUTStatus.ONLINE
                device.error_count = 0
                logger.info(f"SUT {unique_id} came back online at {ip}:{port}")
                event_bus.emit(EventType.SUT_ONLINE, {
                    "device_id": unique_id,
                    "ip": ip,
                    "port": port,
                    "hostname": hostname
                })
        else:
            device = SUTDevice(
                ip=ip,
                port=port,
                unique_id=unique_id,
                hostname=hostname,
                status=SUTStatus.ONLINE,
                capabilities=capabilities,
                successful_pings=1,
                total_pings=1,
                cpu_model=cpu_model,
                display_name=display_name
            )

            self.devices[unique_id] = device
            logger.info(f"New SUT discovered: {unique_id} at {ip}:{port}")
            event_bus.emit(EventType.SUT_DISCOVERED, {
                "device_id": unique_id,
                "ip": ip,
                "port": port,
                "hostname": hostname,
                "capabilities": capabilities
            })

        self.ip_to_id_mapping[ip] = unique_id
        return device

    def mark_device_offline(self, unique_id: str):
        """Mark a device as offline."""
        if unique_id in self.devices:
            device = self.devices[unique_id]
            if device.status != SUTStatus.OFFLINE:
                device.status = SUTStatus.OFFLINE
                logger.info(f"SUT {unique_id} marked as offline")
                event_bus.emit(EventType.SUT_OFFLINE, {
                    "device_id": unique_id,
                    "ip": device.ip,
                    "port": device.port
                })

    def get_device_by_id(self, unique_id: str) -> Optional[SUTDevice]:
        """Get device by unique ID."""
        return self.devices.get(unique_id)

    def get_device_by_ip(self, ip: str) -> Optional[SUTDevice]:
        """Get device by IP address."""
        unique_id = self.ip_to_id_mapping.get(ip)
        return self.devices.get(unique_id) if unique_id else None

    def get_online_devices(self) -> List[SUTDevice]:
        """Get all online devices."""
        return [device for device in self.devices.values() if device.status == SUTStatus.ONLINE]

    def get_all_devices(self) -> List[SUTDevice]:
        """Get all devices."""
        return list(self.devices.values())

    def get_paired_devices(self) -> List[SUTDevice]:
        """Get all paired devices."""
        return [device for device in self.devices.values() if device.is_paired]

    def pair_device(self, unique_id: str, paired_by: str = "user") -> bool:
        """Pair a device for priority scanning."""
        device = self.get_device_by_id(unique_id)
        if not device:
            logger.warning(f"Cannot pair device {unique_id}: device not found")
            return False

        device.pair_device(paired_by)
        logger.info(f"Device {unique_id} ({device.ip}) paired by {paired_by}")

        event_bus.emit(EventType.SUT_PAIRED, {
            "device_id": unique_id,
            "ip": device.ip,
            "port": device.port,
            "hostname": device.hostname,
            "paired_by": paired_by
        })

        self.save_paired_devices()
        return True

    def unpair_device(self, unique_id: str) -> bool:
        """Unpair a device."""
        device = self.get_device_by_id(unique_id)
        if not device:
            logger.warning(f"Cannot unpair device {unique_id}: device not found")
            return False

        device.unpair_device()
        logger.info(f"Device {unique_id} ({device.ip}) unpaired")

        event_bus.emit(EventType.SUT_UNPAIRED, {
            "device_id": unique_id,
            "ip": device.ip,
            "port": device.port,
            "hostname": device.hostname
        })

        self.save_paired_devices()
        return True

    def set_display_name(self, unique_id: str, display_name: str) -> bool:
        """Set display name for a device."""
        device = self.get_device_by_id(unique_id)
        if not device:
            return False
        device.display_name = display_name
        if device.is_paired:
            self.save_paired_devices()
        return True

    def get_device_stats(self) -> Dict[str, any]:
        """Get registry statistics."""
        online_count = len(self.get_online_devices())
        total_count = len(self.devices)
        paired_count = len(self.get_paired_devices())

        return {
            "total_devices": total_count,
            "online_devices": online_count,
            "offline_devices": total_count - online_count,
            "paired_devices": paired_count,
        }

    def remove_stale_devices(self, timeout_seconds: int = None) -> Dict[str, any]:
        """
        Remove unpaired offline devices that haven't been seen for longer than timeout.

        Args:
            timeout_seconds: Override timeout in seconds (uses self.stale_device_timeout if None)

        Returns:
            Dict with removed device info and count
        """
        timeout = timeout_seconds if timeout_seconds is not None else self.stale_device_timeout
        now = datetime.now()
        removed_devices = []

        # Find stale devices (unpaired + offline + last_seen > timeout)
        devices_to_remove = []
        for device_id, device in self.devices.items():
            if not device.is_paired and device.status == SUTStatus.OFFLINE:
                seconds_since_seen = (now - device.last_seen).total_seconds()
                if seconds_since_seen > timeout:
                    devices_to_remove.append(device_id)
                    removed_devices.append({
                        "unique_id": device_id,
                        "ip": device.ip,
                        "hostname": device.hostname,
                        "last_seen": device.last_seen.isoformat(),
                        "seconds_since_seen": int(seconds_since_seen)
                    })

        # Remove stale devices
        for device_id in devices_to_remove:
            device = self.devices[device_id]
            # Remove from IP mapping
            if device.ip in self.ip_to_id_mapping:
                del self.ip_to_id_mapping[device.ip]
            # Remove device
            del self.devices[device_id]
            logger.info(f"Removed stale device: {device_id} (last seen {int((now - device.last_seen).total_seconds())}s ago)")

        return {
            "removed_count": len(removed_devices),
            "removed_devices": removed_devices,
            "timeout_used": timeout
        }

    def set_stale_timeout(self, timeout_seconds: int) -> None:
        """Set the stale device timeout."""
        self.stale_device_timeout = timeout_seconds
        logger.info(f"Stale device timeout set to {timeout_seconds} seconds")

    def get_stale_timeout(self) -> int:
        """Get the current stale device timeout."""
        return self.stale_device_timeout

    def load_paired_devices_on_startup(self) -> None:
        """Load paired devices from persistence file on startup."""
        logger.info("Loading paired devices from persistence...")
        paired_devices = self.persistence.load_paired_devices()

        for device_id, device in paired_devices.items():
            device.status = SUTStatus.OFFLINE
            self.devices[device_id] = device
            self.ip_to_id_mapping[device.ip] = device_id
            logger.info(f"Loaded paired device: {device.ip} ({device_id})")

        logger.info(f"Loaded {len(paired_devices)} paired devices from persistence")

    def save_paired_devices(self) -> bool:
        """Save current paired devices to persistence."""
        return self.persistence.save_paired_devices(self.devices)


# Global device registry instance
_device_registry: Optional[DeviceRegistry] = None


def get_device_registry() -> DeviceRegistry:
    """Get or create device registry singleton."""
    global _device_registry
    if _device_registry is None:
        from ..config import get_config
        config = get_config()
        _device_registry = DeviceRegistry(
            offline_timeout=config.offline_timeout,
            stale_device_timeout=config.stale_device_timeout,
            persistence_file=config.paired_devices_file
        )
    return _device_registry
