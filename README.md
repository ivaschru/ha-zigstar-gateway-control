# ZigStar Gateway Control for Home Assistant

Home Assistant custom integration for monitoring and managing ZigStar Gateway / XZG devices over the local web UI.

The integration is intended for HACS installation and does not use any cloud service.

## Features

- Add multiple gateways through the Home Assistant UI.
- Connect to XZG devices with or without web UI authentication enabled.
- Monitor Zigbee socket connectivity and connected client count.
- Monitor ESP32 uptime, temperature, heap usage, file system usage, firmware and hardware metadata.
- Monitor Ethernet and MQTT connection status.
- Monitor Zigbee firmware, hardware, role and IEEE address when the firmware exposes them.
- Restart XZG and legacy ZigStar GW RUS firmware gateways from Home Assistant.

## Supported Firmware

Tested with these firmware families:

- XZG firmware with HTTP API at `/api?action=...`.
- Legacy `ZigStar GW RUS 0.1.3` HTML web UI.

The XZG HTTP API is documented by the firmware project at:

- <https://xzg.xyzroe.cc/http_api/>

## Entities

The exact entity list depends on the detected firmware and the fields it exposes.

Common entities include:

- Zigbee socket connected
- Zigbee socket clients
- Zigbee socket connected for
- Zigbee socket port
- Serial baud rate
- Device temperature
- Uptime
- Uptime seconds
- Ethernet connected
- Ethernet speed
- Ethernet IP
- MQTT connected
- MQTT broker
- ESP firmware
- ESP model
- ESP flash size
- Heap used
- Heap usage
- File system usage
- NVS usage
- Zigbee role
- Zigbee firmware
- Zigbee hardware
- Zigbee IEEE
- Zigbee flash size

XZG and legacy ZigStar GW RUS devices also create a restart button.

The dashboard-oriented uptime entity is reported in days. The raw seconds uptime
entity and low-level diagnostic metadata are disabled by default and can be
enabled from the Home Assistant entity registry when needed.

## Installation with HACS

1. Open HACS in Home Assistant.
2. Open custom repositories.
3. Add this repository URL as category `Integration`.
4. Install `ZigStar Gateway Control`.
5. Restart Home Assistant.
6. Go to **Settings -> Devices & services -> Add integration**.
7. Search for `ZigStar Gateway Control`.
8. Add one gateway by entering its IP address or hostname.
9. If XZG web server authentication is enabled, also enter the web UI username and password. Leave both fields empty for gateways without web authentication.
10. Repeat the add integration flow for every additional gateway.

For an already configured gateway, use the integration's **Configure** action
to add, change, or clear the optional XZG web UI username and password.

## Manual Installation

Copy `custom_components/zigstar_gateway_control` into your Home Assistant `custom_components` directory, then restart Home Assistant.

## Notes

- The integration polls local HTTP endpoints every 30 seconds.
- XZG status is read from `GET /api?action=1&param=root` and `GET /api?action=1&param=update_root`.
- XZG serial settings are read from the `respValuesArr` header of `GET /api?action=0&page=3`.
- XZG web UI authentication is handled through `POST /login` with a stored `XZG_UID` cookie. The integration does not read the XZG security settings page because that page can expose configured web credentials in response headers.
- Legacy ZigStar GW RUS status is parsed from `/` and serial settings from `/serial`.
- The restart button is exposed for XZG and legacy firmware. XZG calls `GET /api?action=8&cmd=3`; legacy ZigStar GW RUS calls `GET /reboot`, which executes immediately and temporarily disconnects the gateway.
- This integration manages the gateway device itself. It does not replace ZHA or Zigbee2MQTT and does not manage Zigbee end devices.

## Troubleshooting

If setup fails:

- Check that Home Assistant can reach the gateway IP address over plain HTTP on port `80`.
- If XZG web authentication is enabled, confirm the username and password work in the gateway web UI from the same network.
- Check that the Zigbee socket port, usually `6638`, is open from the Home Assistant host.
- Open the gateway web UI from the same network and confirm the device is responsive.

Enable debug logging if you need more detail:

```yaml
logger:
  logs:
    custom_components.zigstar_gateway_control: debug
```
