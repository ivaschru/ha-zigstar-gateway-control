"""Coordinator for polling one ZigStar gateway."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZigStarGatewayApi, ZigStarGatewayConnectionError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, MANUFACTURER
from .parsing import ZigStarDeviceInfo

_LOGGER = logging.getLogger(__name__)


class ZigStarGatewayCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll one gateway once and fan the data out to all entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: ZigStarGatewayApi,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            always_update=False,
        )
        self.api = api
        self.device_info = ZigStarDeviceInfo(
            host=api.host,
            name=f"ZigStar Gateway {api.host}",
            backend="unknown",
            manufacturer=MANUFACTURER,
        )

    @property
    def device_identifier(self) -> str:
        """Return the most stable identifier available for this gateway."""
        if self.device_info.zigbee_ieee:
            return self.device_info.zigbee_ieee.lower()
        if self.device_info.mac_address:
            return self.device_info.mac_address.lower()
        return self.api.host

    async def _async_setup(self) -> None:
        """Load static device metadata before the first status refresh."""
        try:
            self.device_info = await self.api.async_fetch_device_info()
        except ZigStarGatewayConnectionError as err:
            # The first real update will surface a proper ConfigEntryNotReady.
            # Keeping this debug-only avoids hiding useful status payloads when
            # one optional metadata endpoint changes across firmware builds.
            _LOGGER.debug("Unable to fetch gateway metadata before first poll: %s", err)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest gateway status."""
        try:
            payload = await self.api.async_fetch_status()
        except ZigStarGatewayConnectionError as err:
            raise UpdateFailed(str(err)) from err

        # Device info can improve after the first successful poll, especially
        # when a legacy page did not expose all fields during setup.
        self.device_info = ZigStarDeviceInfo(
            host=self.api.host,
            name=str(payload.get("name") or self.device_info.name),
            backend=str(payload.get("backend") or self.device_info.backend),
            manufacturer=MANUFACTURER,
            model=payload.get("model") or self.device_info.model,
            firmware_version=payload.get("firmware_version") or self.device_info.firmware_version,
            serial_number=payload.get("zigbee_ieee")
            or payload.get("mac_address")
            or self.device_info.serial_number,
            mac_address=payload.get("mac_address") or self.device_info.mac_address,
            zigbee_ieee=payload.get("zigbee_ieee") or self.device_info.zigbee_ieee,
        )
        return payload
