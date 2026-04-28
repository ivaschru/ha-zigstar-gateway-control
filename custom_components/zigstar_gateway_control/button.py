"""Button entities for ZigStar gateway management."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .api import ZigStarGatewayError
from .const import DOMAIN
from .coordinator import ZigStarGatewayCoordinator
from .entity import ZigStarGatewayEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up management buttons for one ZigStar gateway config entry."""
    runtime_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ZigStarGatewayCoordinator = runtime_data.coordinator
    if coordinator.api.supports_restart:
        async_add_entities([ZigStarGatewayRestartButton(coordinator)])


class ZigStarGatewayRestartButton(ZigStarGatewayEntity, ButtonEntity):
    """Button that restarts the ESP32 controller on XZG firmware."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "restart"

    def __init__(self, coordinator: ZigStarGatewayCoordinator) -> None:
        """Initialize the restart button."""
        super().__init__(coordinator)
        device_slug = slugify(coordinator.device_info.name)
        self._attr_unique_id = f"{coordinator.device_identifier}_restart"
        self._attr_suggested_object_id = f"{device_slug}_restart"

    async def async_press(self) -> None:
        """Send the restart command to the gateway."""
        try:
            await self.coordinator.api.async_restart()
        except ZigStarGatewayError as err:
            _LOGGER.exception("Failed to restart ZigStar gateway")
            raise HomeAssistantError("Failed to restart ZigStar gateway") from err

        # Do not force an immediate refresh. A successful restart normally
        # drops the web UI and Zigbee socket before the next HTTP poll.
