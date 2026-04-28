"""Config flow for ZigStar Gateway Control."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ZigStarGatewayApi, ZigStarGatewayAuthError, ZigStarGatewayConnectionError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


async def _validate_input(
    hass: HomeAssistant,
    user_input: dict[str, Any],
) -> tuple[str, str]:
    """Validate connectivity and return a title plus a stable unique id.

    Web UI credentials are optional because XZG ships with authentication
    disabled by default. When authentication is enabled, the API client will
    discover the login redirect, authenticate, and retry the same status read.
    """
    session = async_get_clientsession(hass)
    api = ZigStarGatewayApi(
        session=session,
        host=user_input[CONF_HOST],
        username=user_input.get(CONF_USERNAME),
        password=user_input.get(CONF_PASSWORD),
    )

    device_info = await api.async_fetch_device_info()
    unique_id = device_info.zigbee_ieee or device_info.mac_address or api.host
    return device_info.name, unique_id.lower()


class ZigStarGatewayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZigStar Gateway Control."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {
                CONF_HOST: user_input[CONF_HOST].strip(),
            }
            username = user_input.get(CONF_USERNAME, "").strip()
            password = user_input.get(CONF_PASSWORD, "")
            if bool(username) != bool(password):
                errors["base"] = "credentials_incomplete"
            elif username and password:
                data[CONF_USERNAME] = username
                data[CONF_PASSWORD] = password

            if not errors:
                try:
                    title, unique_id = await _validate_input(self.hass, data)
                except ZigStarGatewayAuthError:
                    errors["base"] = "invalid_auth"
                except ZigStarGatewayConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error while setting up ZigStar gateway")
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
