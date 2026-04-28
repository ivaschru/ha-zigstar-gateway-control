"""Pure parsing helpers for ZigStar Gateway and XZG payloads.

The supported gateways expose two different local web UIs:

* modern XZG firmware has a small HTTP API at ``/api?action=...``;
* older ZigStar GW RUS firmware renders status directly into HTML pages.

This module normalizes both variants into one dictionary so the Home Assistant
entity layer does not need to know which web UI produced the data.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import json
import re
from typing import Any

BACKEND_XZG = "xzg"
BACKEND_LEGACY_RUS = "legacy_rus"

ROLE_NAMES = {
    1: "Coordinator",
    2: "Router",
    3: "OpenThread",
}

_DIV_RE_TEMPLATE = r"<div\s+id=[\"']{id}[\"'][^>]*>(?P<body>.*?)</div>"
_STRONG_RE = re.compile(
    r"<strong(?:\s+[^>]*)?>(?P<label>.*?)</strong>(?P<value>.*?)(?:<br>|</div>|$)",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_SERIAL_PORT_RE = re.compile(
    r"name=[\"']port[\"'][^>]*value=[\"'](?P<port>\d+)[\"']",
    re.IGNORECASE | re.DOTALL,
)
_SERIAL_BAUD_RE = re.compile(
    r"<option[^>]*value=[\"'](?P<baud>\d+)[\"'][^>]*\bselected\b",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(slots=True)
class ZigStarDeviceInfo:
    """Static metadata used for the Home Assistant device registry."""

    host: str
    name: str
    backend: str
    manufacturer: str = "ZigStar"
    model: str | None = None
    firmware_version: str | None = None
    serial_number: str | None = None
    mac_address: str | None = None
    zigbee_ieee: str | None = None


def normalize_base_url(host: str) -> str:
    """Return a normalized HTTP base URL for user-provided host input."""
    host = host.strip()
    if not host:
        raise ValueError("Host is empty")

    if "://" not in host:
        host = f"http://{host}"

    return host.rstrip("/") + "/"


def parse_numeric(value: Any) -> float | int | None:
    """Extract the leading number from vendor values like ``100 Mbps``."""
    if value is None:
        return None

    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    if match is None:
        return None

    parsed = float(match.group(0))
    if parsed.is_integer():
        return int(parsed)
    return parsed


def parse_duration_text(value: str | None) -> int | None:
    """Parse Russian legacy durations such as ``0 д 02:33:36`` into seconds."""
    if not value:
        return None

    match = re.search(r"(?P<days>\d+)\s*д\s*(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+)", value)
    if match is None:
        return None

    return (
        int(match.group("days")) * 86400
        + int(match.group("hours")) * 3600
        + int(match.group("minutes")) * 60
        + int(match.group("seconds"))
    )


def parse_xzg_json(text: str) -> dict[str, Any]:
    """Decode an XZG API JSON object and reject non-object responses."""
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("XZG response is not a JSON object")
    return parsed


def parse_xzg_serial_settings(values: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize serial settings returned in the XZG ``respValuesArr`` header."""
    values = values or {}
    return {
        "serial_baud": _first_selected_baud(values),
        "socket_port": parse_numeric(values.get("socketPort")),
        "operational_mode": _operational_mode_name(values.get("lanMode")),
        "zigbee_role": _role_name(values.get("zbRole")),
    }


def normalize_xzg_payload(
    host: str,
    root: dict[str, Any],
    *,
    update_root: dict[str, Any] | None = None,
    serial_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize XZG root/update payloads into one integration payload."""
    merged = dict(root)
    if update_root:
        merged.update(update_root)

    serial = parse_xzg_serial_settings(serial_settings)
    uptime_ms = parse_numeric(merged.get("uptime"))
    connected_since_ms = parse_numeric(merged.get("connectedSocket"))

    data: dict[str, Any] = {
        "backend": BACKEND_XZG,
        "host": host,
        "manufacturer": "ZigStar",
        "name": _xzg_name(host, merged),
        "model": _as_text(merged.get("hwRev")),
        "firmware_version": _as_text(merged.get("VERSION")),
        "mac_address": _normalize_mac(merged.get("ethMac")),
        "zigbee_ieee": _as_text(merged.get("zigbeeIeee")),
        "zigbee_firmware": _as_text(merged.get("zigbeeFwRev")),
        "zigbee_hardware": _as_text(merged.get("zigbeeHwRev")),
        "zigbee_flash_size": parse_numeric(merged.get("zigbeeFlSize")),
        "zigbee_role": _role_name(merged.get("zbRole")),
        "esp_model": _as_text(merged.get("espModel")),
        "esp_cores": parse_numeric(merged.get("espCores")),
        "esp_frequency": parse_numeric(merged.get("espFreq")),
        "esp_flash_size": parse_numeric(merged.get("espFlashSize")),
        "device_temperature": parse_numeric(merged.get("deviceTemp")),
        "uptime": _milliseconds_to_seconds(uptime_ms),
        "socket_clients": parse_numeric(merged.get("connectedSocketStatus")),
        "socket_connected": _truthy_number(merged.get("connectedSocketStatus")),
        "socket_connected_for": _socket_connected_for_seconds(uptime_ms, connected_since_ms),
        "ethernet_connected": _truthy_number(merged.get("ethConn")),
        "ethernet_dhcp": _truthy_number(merged.get("ethDhcp")),
        "ethernet_speed": parse_numeric(merged.get("ethSpd")),
        "ethernet_ip": _as_text(merged.get("ethIp")),
        "ethernet_mask": _as_text(merged.get("ethMask")),
        "ethernet_gateway": _as_text(merged.get("ethGate")),
        "ethernet_dns": _as_text(merged.get("ethDns")),
        "wifi_mac": _normalize_mac(merged.get("wifiMac")),
        "mqtt_broker": _as_text(merged.get("mqBroker")),
        "mqtt_connected": _truthy_number(merged.get("mqConnect")),
        "heap_used": parse_numeric(merged.get("espHeapUsed")),
        "heap_size": parse_numeric(merged.get("espHeapSize")),
        "nvs_used": parse_numeric(merged.get("espNvsUsed")),
        "nvs_size": parse_numeric(merged.get("espNvsSize")),
        "fs_used": parse_numeric(merged.get("espFsUsed")),
        "fs_size": parse_numeric(merged.get("espFsSize")),
        "local_time": _as_text(merged.get("localTime")),
        "raw": merged,
    }
    data.update({key: value for key, value in serial.items() if value is not None})
    return data


def parse_legacy_status_html(host: str, html: str) -> dict[str, Any]:
    """Parse the legacy ZigStar GW RUS status page into normalized data."""
    general = _legacy_label_values(_extract_div(html, "genConfig"))
    ethernet = _legacy_label_values(_extract_div(html, "ethConfig"))
    wifi = _legacy_label_values(_extract_div(html, "wifiConfig"))
    mqtt = _legacy_label_values(_extract_div(html, "mqttConfig"))

    connection_text = general.get("Подключений")
    uptime_text = general.get("В работе")
    heap_used, heap_size = _parse_pair(general.get("Свободная ОЗУ"))

    socket_clients = _parse_legacy_clients(connection_text)
    data = {
        "backend": BACKEND_LEGACY_RUS,
        "host": host,
        "manufacturer": "ZigStar",
        "name": f"ZigStar GW RUS {host}",
        "model": general.get("Оборудование"),
        "firmware_version": general.get("Версия прошивки"),
        "mac_address": _normalize_mac(ethernet.get("MAC")),
        "esp_model": general.get("ESP32 модель"),
        "device_temperature": parse_numeric(general.get("ESP температура")),
        "uptime": parse_duration_text(uptime_text),
        "socket_clients": socket_clients,
        "socket_connected": socket_clients is not None and socket_clients > 0,
        "socket_connected_for": parse_duration_text(connection_text),
        "ethernet_connected": _legacy_block_is_ok(_extract_div(html, "ethConfig"), "Подключен"),
        "ethernet_dhcp": ethernet.get("Режим", "").casefold() == "dhcp",
        "ethernet_speed": parse_numeric(ethernet.get("Скорость")),
        "ethernet_ip": ethernet.get("IP"),
        "ethernet_mask": ethernet.get("Маска"),
        "ethernet_gateway": ethernet.get("Шлюз"),
        "wifi_enabled": _legacy_block_is_ok(_extract_div(html, "wifiConfig"), "Включен"),
        "mqtt_broker": mqtt.get("Сервер"),
        "mqtt_connected": _legacy_block_is_ok(_extract_div(html, "mqttConfig"), "Подключен"),
        "heap_used": heap_used,
        "heap_size": heap_size,
        "raw": {
            "general": general,
            "ethernet": ethernet,
            "wifi": wifi,
            "mqtt": mqtt,
        },
    }
    return data


def parse_legacy_serial_html(html: str) -> dict[str, Any]:
    """Parse legacy serial configuration values without reading secret pages."""
    port = None
    port_match = _SERIAL_PORT_RE.search(html)
    if port_match:
        port = parse_numeric(port_match.group("port"))

    baud = None
    baud_match = _SERIAL_BAUD_RE.search(html)
    if baud_match:
        baud = parse_numeric(baud_match.group("baud"))

    return {
        "serial_baud": baud,
        "socket_port": port,
    }


def device_info_from_payload(host: str, payload: dict[str, Any]) -> ZigStarDeviceInfo:
    """Build static Home Assistant device metadata from normalized payload."""
    name = payload.get("name") or f"ZigStar Gateway {host}"
    return ZigStarDeviceInfo(
        host=host,
        name=str(name),
        backend=str(payload.get("backend") or BACKEND_XZG),
        model=_as_text(payload.get("model")),
        firmware_version=_as_text(payload.get("firmware_version")),
        serial_number=_as_text(payload.get("zigbee_ieee")) or _normalize_mac(payload.get("mac_address")),
        mac_address=_normalize_mac(payload.get("mac_address")),
        zigbee_ieee=_as_text(payload.get("zigbee_ieee")),
    )


def _extract_div(html: str, div_id: str) -> str:
    """Return a simple legacy div body by id."""
    match = re.search(
        _DIV_RE_TEMPLATE.format(id=re.escape(div_id)),
        html,
        re.IGNORECASE | re.DOTALL,
    )
    return match.group("body") if match else ""


def _legacy_label_values(block_html: str) -> dict[str, str]:
    """Extract ``<strong>Label:</strong> value`` pairs from legacy HTML."""
    values: dict[str, str] = {}
    for match in _STRONG_RE.finditer(block_html):
        label = _clean_text(match.group("label")).rstrip(":").strip()
        value = _clean_text(match.group("value"))
        if label:
            values[label] = value
    return values


def _clean_text(html: str) -> str:
    """Strip tags and normalize whitespace from a small HTML fragment."""
    text = _TAG_RE.sub(" ", html)
    text = unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _legacy_block_is_ok(block_html: str, label: str) -> bool | None:
    """Read legacy ``ok.png`` / ``nok.png`` status next to one label."""
    pattern = re.compile(
        r"<strong(?:\s+[^>]*)?>\s*" + re.escape(label) + r"\s*:?\s*</strong>(?P<value>.*?)(?:<br>|</div>|$)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(block_html)
    if match is None:
        return None
    value = match.group("value").casefold()
    if "ok.png" in value and "nok.png" not in value:
        return True
    if "nok.png" in value:
        return False
    return None


def _parse_legacy_clients(value: str | None) -> int | None:
    """Extract socket client count from legacy connection text."""
    if not value:
        return None
    match = re.search(r"\((?P<count>\d+)\s+клиент", value, re.IGNORECASE)
    return int(match.group("count")) if match else None


def _parse_pair(value: str | None) -> tuple[int | float | None, int | float | None]:
    """Parse values like ``222 / 300 KiB`` into a used/size pair."""
    if not value:
        return None, None
    numbers = re.findall(r"\d+(?:\.\d+)?", value)
    if len(numbers) < 2:
        return None, None
    return parse_numeric(numbers[0]), parse_numeric(numbers[1])


def _first_selected_baud(values: dict[str, Any]) -> int | float | None:
    """Find the selected baud entry in XZG serial settings."""
    for key, value in values.items():
        if str(key).isdigit() and _truthy_string(value):
            return parse_numeric(key)
    return None


def _role_name(value: Any) -> str | None:
    """Convert XZG Zigbee role number to a stable string."""
    number = parse_numeric(value)
    if number is None:
        return _as_text(value)
    return ROLE_NAMES.get(int(number), str(number))


def _operational_mode_name(value: Any) -> str | None:
    """Convert XZG operating mode flags to stable strings."""
    if value is None:
        return None
    return "Network" if _truthy_string(value) else "USB"


def _truthy_string(value: Any) -> bool:
    """Return true for vendor truthy values used in JSON/header payloads."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().casefold() in {"1", "true", "yes", "on", "checked"}


def _truthy_number(value: Any) -> bool | None:
    """Convert numeric connection state fields to booleans."""
    number = parse_numeric(value)
    if number is None:
        return None
    return number > 0


def _milliseconds_to_seconds(value: int | float | None) -> int | None:
    """Convert XZG millisecond durations to integer seconds."""
    if value is None:
        return None
    return int(value / 1000)


def _socket_connected_for_seconds(
    uptime_ms: int | float | None,
    connected_since_ms: int | float | None,
) -> int | None:
    """Convert XZG socket timestamp fields into a connection duration."""
    if uptime_ms is None or connected_since_ms is None:
        return None
    if uptime_ms < connected_since_ms:
        return None
    return int((uptime_ms - connected_since_ms) / 1000)


def _normalize_mac(value: Any) -> str | None:
    """Normalize MAC-like values for use as stable identifiers."""
    text = _as_text(value)
    return text.lower() if text else None


def _as_text(value: Any) -> str | None:
    """Return stripped text while preserving meaningful zero values."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _xzg_name(host: str, payload: dict[str, Any]) -> str:
    """Build a user-facing XZG device title."""
    model = _as_text(payload.get("hwRev"))
    ip = _as_text(payload.get("ethIp")) or host
    return f"{model or 'ZigStar Gateway'} {ip}"
