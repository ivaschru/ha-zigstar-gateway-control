"""HTTP client for ZigStar Gateway and XZG devices."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib.parse import urljoin

import aiohttp

from .const import DEFAULT_TIMEOUT
from .parsing import (
    BACKEND_XZG,
    ZigStarDeviceInfo,
    device_info_from_payload,
    normalize_base_url,
    normalize_xzg_payload,
    parse_legacy_serial_html,
    parse_legacy_status_html,
    parse_xzg_json,
)

_LOGGER = logging.getLogger(__name__)


class ZigStarGatewayError(Exception):
    """Base exception for ZigStar Gateway communication errors."""


class ZigStarGatewayConnectionError(ZigStarGatewayError):
    """Raised when a gateway cannot be reached or returns unusable data."""


class ZigStarGatewayApi:
    """Small async client for one ZigStar/XZG gateway."""

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        host: str,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the client without making network calls."""
        self._session = session
        try:
            self._base_url = normalize_base_url(host)
        except ValueError as err:
            raise ZigStarGatewayConnectionError("Host is empty") from err
        self.host = self._base_url.removeprefix("http://").removeprefix("https://").rstrip("/")
        self._timeout = timeout
        self._last_payload: dict[str, Any] | None = None

    @property
    def configuration_url(self) -> str:
        """Return the gateway web UI URL shown in Home Assistant device info."""
        return self._base_url

    @property
    def supports_restart(self) -> bool:
        """Return true when the detected backend has a known safe restart command."""
        return bool(self._last_payload and self._last_payload.get("backend") == BACKEND_XZG)

    async def async_fetch_device_info(self) -> ZigStarDeviceInfo:
        """Fetch a status snapshot and return static device metadata."""
        payload = await self.async_fetch_status()
        return device_info_from_payload(self.host, payload)

    async def async_fetch_status(self) -> dict[str, Any]:
        """Fetch and normalize the latest gateway status."""
        try:
            payload = await self._async_fetch_xzg_status()
        except (ZigStarGatewayConnectionError, ValueError) as xzg_err:
            _LOGGER.debug("XZG API probe failed for %s: %s", self.host, xzg_err)
            payload = await self._async_fetch_legacy_status()

        self._last_payload = payload
        return payload

    async def async_restart(self) -> None:
        """Ask an XZG gateway to restart the ESP32 controller."""
        if not self.supports_restart:
            raise ZigStarGatewayConnectionError("Restart is only supported for XZG firmware")

        # XZG's JavaScript names command 3 as CMD_ESP_RES. It restarts the
        # gateway controller and temporarily disconnects any Zigbee socket.
        try:
            await self._async_request_text("GET", "api?action=8&cmd=3")
        except ZigStarGatewayConnectionError as err:
            # A successful restart may close the HTTP connection before a clean
            # response is received, so this is logged as debug and not fatal.
            _LOGGER.debug("Gateway disconnected while restart command was in flight: %s", err)

    async def _async_fetch_xzg_status(self) -> dict[str, Any]:
        """Fetch status from modern XZG firmware endpoints."""
        root = parse_xzg_json(await self._async_request_text("GET", "api?action=1&param=root"))
        if "VERSION" not in root and "connectedSocketStatus" not in root:
            raise ZigStarGatewayConnectionError("XZG root payload is missing expected fields")

        update_root: dict[str, Any] | None = None
        try:
            update_root = parse_xzg_json(
                await self._async_request_text("GET", "api?action=1&param=update_root")
            )
        except (ZigStarGatewayConnectionError, ValueError) as err:
            _LOGGER.debug("Unable to fetch XZG update_root payload: %s", err)

        serial_settings: dict[str, Any] | None = None
        try:
            _, headers = await self._async_request_text_with_headers(
                "GET",
                "api?action=0&page=3",
            )
            header_value = headers.get("respValuesArr")
            if header_value:
                serial_settings = json.loads(header_value)
        except (ZigStarGatewayConnectionError, ValueError) as err:
            _LOGGER.debug("Unable to fetch XZG serial settings: %s", err)

        return normalize_xzg_payload(
            self.host,
            root,
            update_root=update_root,
            serial_settings=serial_settings,
        )

    async def _async_fetch_legacy_status(self) -> dict[str, Any]:
        """Fetch status from legacy ZigStar GW RUS HTML pages."""
        html = await self._async_request_text("GET", "")
        if "ZigStar GW RUS" not in html:
            raise ZigStarGatewayConnectionError("Device does not look like ZigStar/XZG firmware")

        payload = parse_legacy_status_html(self.host, html)
        try:
            serial_html = await self._async_request_text("GET", "serial")
            payload.update(
                {
                    key: value
                    for key, value in parse_legacy_serial_html(serial_html).items()
                    if value is not None
                }
            )
        except ZigStarGatewayConnectionError as err:
            _LOGGER.debug("Unable to fetch legacy serial settings: %s", err)

        return payload

    async def _async_request_text(self, method: str, path: str) -> str:
        """Run an HTTP request and return the response body."""
        text, _ = await self._async_request_text_with_headers(method, path)
        return text

    async def _async_request_text_with_headers(
        self,
        method: str,
        path: str,
    ) -> tuple[str, Any]:
        """Run an HTTP request and return body plus headers."""
        url = urljoin(self._base_url, path)
        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.request(method, url) as response:
                    response.raise_for_status()
                    text = await response.text()
                    return text, response.headers
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ZigStarGatewayConnectionError(
                f"Unable to fetch {path or '/'} from {self.host}"
            ) from err
