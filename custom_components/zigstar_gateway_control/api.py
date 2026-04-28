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
    BACKEND_LEGACY_RUS,
    BACKEND_XZG,
    ZigStarDeviceInfo,
    cookie_header_from_set_cookie_headers,
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


class ZigStarGatewayAuthError(ZigStarGatewayError):
    """Raised when the gateway requires or rejects web UI credentials."""


class ZigStarGatewayApi:
    """Small async client for one ZigStar/XZG gateway."""

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        host: str,
        username: str | None = None,
        password: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the client without making network calls."""
        self._session = session
        try:
            self._base_url = normalize_base_url(host)
        except ValueError as err:
            raise ZigStarGatewayConnectionError("Host is empty") from err
        self.host = self._base_url.removeprefix("http://").removeprefix("https://").rstrip("/")
        self._username = username.strip() if username else None
        self._password = password
        self._timeout = timeout
        self._authenticated = False
        self._cookie_header: str | None = None
        self._last_payload: dict[str, Any] | None = None

    @property
    def configuration_url(self) -> str:
        """Return the gateway web UI URL shown in Home Assistant device info."""
        return self._base_url

    @property
    def supports_restart(self) -> bool:
        """Return true when the detected backend has a known restart command."""
        return bool(
            self._last_payload
            and self._last_payload.get("backend") in {BACKEND_XZG, BACKEND_LEGACY_RUS}
        )

    async def async_fetch_device_info(self) -> ZigStarDeviceInfo:
        """Fetch a status snapshot and return static device metadata."""
        payload = await self.async_fetch_status()
        return device_info_from_payload(self.host, payload)

    async def async_login(self, *, force: bool = False) -> None:
        """Authenticate against the XZG web UI and keep its session cookie."""
        if self._authenticated and not force:
            return
        if not self._username or not self._password:
            raise ZigStarGatewayAuthError("Gateway requires web UI credentials")
        if force:
            self._authenticated = False
            self._cookie_header = None

        # XZG firmware uses the same HTML form as the browser UI. A successful
        # login returns a redirect to "/" plus Set-Cookie: XZG_UID=<sha1 token>.
        payload = {
            "username": self._username,
            "password": self._password,
        }

        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.post(
                    urljoin(self._base_url, "login"),
                    data=payload,
                    allow_redirects=False,
                ) as response:
                    cookie_header = _cookie_header_from_response(response)
                    if response.status >= 400:
                        response.raise_for_status()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ZigStarGatewayConnectionError(f"Unable to connect to {self.host}") from err

        if not cookie_header:
            raise ZigStarGatewayAuthError("Gateway rejected the supplied credentials")

        self._cookie_header = cookie_header
        self._authenticated = True

    async def async_fetch_status(self) -> dict[str, Any]:
        """Fetch and normalize the latest gateway status."""
        try:
            payload = await self._async_fetch_xzg_status()
        except ZigStarGatewayAuthError:
            raise
        except (ZigStarGatewayConnectionError, ValueError) as xzg_err:
            _LOGGER.debug("XZG API probe failed for %s: %s", self.host, xzg_err)
            payload = await self._async_fetch_legacy_status()

        self._last_payload = payload
        return payload

    async def async_restart(self) -> None:
        """Ask the gateway to restart its ESP32 controller."""
        if not self.supports_restart:
            raise ZigStarGatewayConnectionError("Restart is not supported for this firmware")

        backend = self._last_payload.get("backend") if self._last_payload else None
        if backend == BACKEND_XZG:
            # XZG's JavaScript names command 3 as CMD_ESP_RES. It restarts the
            # gateway controller and temporarily disconnects any Zigbee socket.
            restart_path = "api?action=8&cmd=3"
        elif backend == BACKEND_LEGACY_RUS:
            # Legacy ZigStar GW RUS executes /reboot immediately. Keeping this
            # behind Home Assistant's ButtonEntity preserves the expected
            # "press means restart" behavior while avoiding discovery probes.
            restart_path = "reboot"
        else:
            raise ZigStarGatewayConnectionError("Restart is not supported for this firmware")

        try:
            await self._async_request_text("GET", restart_path)
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
        *,
        retry_auth: bool = True,
    ) -> tuple[str, Any]:
        """Run an HTTP request and return body plus headers."""
        url = urljoin(self._base_url, path)
        headers = {"Cookie": self._cookie_header} if self._cookie_header else None
        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.request(
                    method,
                    url,
                    headers=headers,
                    allow_redirects=False,
                ) as response:
                    if _response_asks_for_login(response):
                        if retry_auth:
                            self._authenticated = False
                            await self.async_login(force=True)
                            return await self._async_request_text_with_headers(
                                method,
                                path,
                                retry_auth=False,
                            )
                        raise ZigStarGatewayAuthError("Gateway requires web UI credentials")

                    response.raise_for_status()
                    text = await response.text()
                    if _looks_like_xzg_login_page(text):
                        if retry_auth:
                            self._authenticated = False
                            await self.async_login(force=True)
                            return await self._async_request_text_with_headers(
                                method,
                                path,
                                retry_auth=False,
                            )
                        raise ZigStarGatewayAuthError("Gateway requires web UI credentials")

                    return text, response.headers
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ZigStarGatewayConnectionError(
                f"Unable to fetch {path or '/'} from {self.host}"
            ) from err


def _cookie_header_from_response(response: aiohttp.ClientResponse) -> str | None:
    """Build a Cookie header from Set-Cookie headers returned by XZG.

    Home Assistant's shared aiohttp session uses the safe cookie policy, which
    may ignore cookies set by IP-address hosts. XZG gateways are usually added
    by IP, so the integration keeps the cookie value itself.
    """
    return cookie_header_from_set_cookie_headers(response.headers.getall("Set-Cookie", []))


def _response_asks_for_login(response: aiohttp.ClientResponse) -> bool:
    """Return true when XZG redirects an unauthenticated request to login."""
    auth_header = response.headers.get("Authentication", "").casefold()
    location = response.headers.get("Location", "").casefold()
    return auth_header == "fail" or (
        response.status in {301, 302, 303, 307, 308, 401, 403} and "/login" in location
    )


def _looks_like_xzg_login_page(text: str) -> bool:
    """Return true when a gateway returned the XZG login HTML instead of data."""
    lowered = text.casefold()
    return "<html" in lowered and 'action="/login"' in lowered and 'name="password"' in lowered
