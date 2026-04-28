"""Tests for parser helpers that do not need a Home Assistant runtime."""

from pathlib import Path
import sys

INTEGRATION_DIR = Path(__file__).parents[1] / "custom_components" / "zigstar_gateway_control"
sys.path.insert(0, str(INTEGRATION_DIR))

from parsing import (  # noqa: E402
    BACKEND_LEGACY_RUS,
    BACKEND_XZG,
    cookie_header_from_set_cookie_headers,
    device_info_from_payload,
    normalize_xzg_payload,
    parse_duration_text,
    parse_legacy_serial_html,
    parse_legacy_status_html,
    parse_numeric,
)


def test_parse_numeric() -> None:
    """Numeric parser handles vendor strings with units."""
    assert parse_numeric("100 Mbps, FULL DUPLEX") == 100
    assert parse_numeric("33.89 °C") == 33.89
    assert parse_numeric("352") == 352
    assert parse_numeric(None) is None


def test_parse_duration_text() -> None:
    """Legacy Russian duration parser returns seconds."""
    assert parse_duration_text("0 д 02:33:36") == 9216
    assert parse_duration_text("1 д 00:00:05") == 86405
    assert parse_duration_text("not a duration") is None


def test_parse_xzg_root_payload() -> None:
    """XZG root/update payloads are normalized into integration keys."""
    root = {
        "connectedSocketStatus": 1,
        "connectedSocket": 1000,
        "VERSION": "20240914",
        "ethMac": "AA:BB:CC:DD:EE:FF",
        "ethConn": 1,
        "ethDhcp": 1,
        "ethSpd": 100,
        "ethIp": "192.0.2.10",
        "uptime": 61000,
        "deviceTemp": "33.33",
        "hwRev": "ZigStar LAN",
        "espModel": "ESP32-D0WD",
        "espHeapSize": 312,
        "espHeapUsed": 99,
        "espFsSize": 60,
        "espFsUsed": 8,
        "zigbeeFwRev": "20240710",
        "zigbeeHwRev": "CC2652P2_launchpad",
        "zigbeeIeee": "00:12:4B:00:00:00:00:01",
        "zigbeeFlSize": "352",
        "zbRole": 1,
        "mqBroker": "192.0.2.20",
        "mqConnect": 0,
    }
    serial = {
        "lanMode": "true",
        "115200": "true",
        "socketPort": "6638",
        "zbRole": 1,
    }

    payload = normalize_xzg_payload("192.0.2.10", root, serial_settings=serial)

    assert payload["backend"] == BACKEND_XZG
    assert payload["name"] == "ZigStar LAN 192.0.2.10"
    assert payload["mac_address"] == "aa:bb:cc:dd:ee:ff"
    assert payload["socket_connected"] is True
    assert payload["socket_connected_for"] == 60
    assert payload["socket_port"] == 6638
    assert payload["serial_baud"] == 115200
    assert payload["zigbee_role"] == "Coordinator"
    assert payload["mqtt_connected"] is False


def test_cookie_header_from_set_cookie_headers() -> None:
    """Cookie parser keeps only reusable name/value pairs for follow-up calls."""
    headers = [
        "XZG_UID=session-token; Path=/; HttpOnly",
        "theme=dark; SameSite=Lax",
    ]

    assert cookie_header_from_set_cookie_headers(headers) == "XZG_UID=session-token; theme=dark"


def test_cookie_header_from_empty_headers() -> None:
    """Missing Set-Cookie headers do not create an outbound Cookie header."""
    assert cookie_header_from_set_cookie_headers([]) is None


def test_xzg_device_info() -> None:
    """Device info uses Zigbee IEEE as the preferred serial number."""
    payload = {
        "backend": BACKEND_XZG,
        "name": "ZigStar LAN 192.0.2.10",
        "model": "ZigStar LAN",
        "firmware_version": "20240914",
        "mac_address": "aa:bb:cc:dd:ee:ff",
        "zigbee_ieee": "00:12:4B:00:00:00:00:01",
    }

    info = device_info_from_payload("192.0.2.10", payload)

    assert info.name == "ZigStar LAN 192.0.2.10"
    assert info.model == "ZigStar LAN"
    assert info.firmware_version == "20240914"
    assert info.serial_number == "00:12:4B:00:00:00:00:01"


def test_parse_legacy_status_html() -> None:
    """Legacy ZigStar GW RUS status HTML is normalized."""
    html = """
    <html><title>Статус - ZigStar GW RUS</title>
    <div id='genConfig'>
      <strong>Подключений : </strong><img src='/img/ok.png'> 0 д 00:00:25 (1 клиент)<br>
      <strong>В работе : </strong>0 д 00:00:41<br>
      <strong>ESP температура : </strong>33.89 &deg;C<br>
      <strong id='ver' v=0.1.3>Версия прошивки : </strong>0.1.3<br>
      <strong>Оборудование : </strong>WT32-ETH01<br>
      <strong>ESP32 модель : </strong>ESP32-D0WDQ5<br>
      <strong>Свободная ОЗУ : </strong>222 / 300 KiB
    </div>
    <div id='ethConfig'>
      <strong>Подключен : </strong><img src='/img/ok.png'><br>
      <strong>MAC : </strong>AA:BB:CC:DD:EE:FF<br>
      <strong>Скорость : </strong> 100 Mbps, FULL DUPLEX<br>
      <strong>Режим : </strong>DHCP<br>
      <strong>IP : </strong>192.0.2.11<br>
      <strong>Маска : </strong>255.255.255.0<br>
      <strong>Шлюз : </strong>192.0.2.1
    </div>
    <div id='wifiConfig'><strong>Включен : </strong><img src='/img/nok.png'></div>
    <div id='mqttConfig'>
      <strong>Включен : </strong><img src='/img/ok.png'><br>
      <strong>Сервер : </strong>192.0.2.20<br>
      <strong>Подключен : </strong><img src='/img/ok.png'>
    </div>
    </html>
    """

    payload = parse_legacy_status_html("192.0.2.11", html)

    assert payload["backend"] == BACKEND_LEGACY_RUS
    assert payload["model"] == "WT32-ETH01"
    assert payload["firmware_version"] == "0.1.3"
    assert payload["mac_address"] == "aa:bb:cc:dd:ee:ff"
    assert payload["socket_clients"] == 1
    assert payload["socket_connected_for"] == 25
    assert payload["uptime"] == 41
    assert payload["ethernet_connected"] is True
    assert payload["wifi_enabled"] is False
    assert payload["mqtt_connected"] is True
    assert payload["heap_used"] == 222
    assert payload["heap_size"] == 300


def test_parse_legacy_serial_html() -> None:
    """Legacy serial HTML parser extracts baud and socket port."""
    html = """
    <select class='form-control' id='baud' name='baud'>
      <option value='9600'>9600 bauds</option>
      <option value='115200' Selected>115200 bauds</option>
    </select>
    <input class='form-control' id='port' type='number' name='port' min='100' max='65000' value='6638'>
    """

    assert parse_legacy_serial_html(html) == {
        "serial_baud": 115200,
        "socket_port": 6638,
    }
