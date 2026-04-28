"""Home Assistant setup for the ZigStar Gateway Control integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ZigStarGatewayApi
from .const import DOMAIN, PLATFORMS
from .coordinator import ZigStarGatewayCoordinator


@dataclass
class ZigStarGatewayRuntimeData:
    """Runtime objects shared by the integration platforms."""

    api: ZigStarGatewayApi
    coordinator: ZigStarGatewayCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one ZigStar gateway config entry."""
    session = async_get_clientsession(hass)
    api = ZigStarGatewayApi(
        session=session,
        host=entry.data[CONF_HOST],
    )

    coordinator = ZigStarGatewayCoordinator(hass, entry, api)

    # The first refresh validates the HTTP API and gives entities initial state.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ZigStarGatewayRuntimeData(
        api=api,
        coordinator=coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload one ZigStar gateway config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok
