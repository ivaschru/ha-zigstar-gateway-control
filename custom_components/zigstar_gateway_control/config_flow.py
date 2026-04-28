"""Config flow for ZigStar Gateway Control."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ZigStarGatewayApi, ZigStarGatewayAuthError, ZigStarGatewayConnectionError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _credential_fields(
    *,
    username: str = "",
    password: str = "",
) -> dict[vol.Optional, type | selector.TextSelector]:
    """Return the optional web-auth fields shared by setup and options."""
    return {
        vol.Optional(CONF_USERNAME, default=username): str,
        vol.Optional(CONF_PASSWORD, default=password): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        **_credential_fields(),
    }
)


def _entry_value(entry: config_entries.ConfigEntry, key: str) -> str:
    """Return data/options value for forms, preserving deliberate empty options."""
    if key in entry.options:
        return entry.options[key] or ""
    return entry.data.get(key, "") or ""


def _credentials_from_input(
    user_input: dict[str, Any],
    *,
    include_empty: bool = False,
) -> tuple[dict[str, str], str | None]:
    """Normalize optional credentials and validate that they are a pair."""
    username = user_input.get(CONF_USERNAME, "").strip()
    password = user_input.get(CONF_PASSWORD, "")
    if bool(username) != bool(password):
        return {}, "credentials_incomplete"
    if username and password or include_empty:
        return {CONF_USERNAME: username, CONF_PASSWORD: password}, None
    return {}, None


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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow used to update web-auth credentials."""
        return ZigStarGatewayOptionsFlow(config_entry)

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
            credentials, error = _credentials_from_input(user_input)
            if error:
                errors["base"] = error
            else:
                data.update(credentials)

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


class ZigStarGatewayOptionsFlow(config_entries.OptionsFlow):
    """Handle editable options for an existing ZigStar gateway entry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Keep the entry so options can validate against its existing host."""
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Update optional XZG web UI credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {
                CONF_HOST: self._config_entry.data[CONF_HOST],
            }
            credentials, error = _credentials_from_input(user_input, include_empty=True)
            if error:
                errors["base"] = error
            else:
                data.update(credentials)

            if not errors:
                try:
                    await _validate_input(self.hass, data)
                except ZigStarGatewayAuthError:
                    errors["base"] = "invalid_auth"
                except ZigStarGatewayConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error while updating ZigStar gateway options")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(title="", data=credentials)

        data_schema = vol.Schema(
            _credential_fields(
                username=_entry_value(self._config_entry, CONF_USERNAME),
                password=_entry_value(self._config_entry, CONF_PASSWORD),
            )
        )
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )
