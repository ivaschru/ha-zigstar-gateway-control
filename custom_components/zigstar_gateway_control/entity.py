"""Shared entity helpers for ZigStar Gateway Control platforms."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZigStarGatewayCoordinator


class ZigStarGatewayEntity(CoordinatorEntity[ZigStarGatewayCoordinator]):
    """Base class that ties an entity to the gateway device registry entry."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ZigStarGatewayCoordinator) -> None:
        """Initialize the entity with a shared coordinator."""
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        """Return Home Assistant device registry metadata."""
        info = self.coordinator.device_info
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_identifier)},
            name=info.name,
            manufacturer=info.manufacturer,
            model=info.model,
            sw_version=info.firmware_version,
            serial_number=info.serial_number,
            configuration_url=self.coordinator.api.configuration_url,
        )
