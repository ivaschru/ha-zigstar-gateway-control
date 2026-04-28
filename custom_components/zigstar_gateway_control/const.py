"""Constants for the ZigStar Gateway Control integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "zigstar_gateway_control"

DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 10
DEFAULT_ZIGBEE_SOCKET_PORT = 6638

MANUFACTURER = "ZigStar"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]
