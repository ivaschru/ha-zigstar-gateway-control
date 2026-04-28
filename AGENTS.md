# AGENTS.md

## Project Purpose

- This repository contains a Home Assistant custom integration for managing ZigStar Gateway and XZG gateway devices.
- The integration is intended for HACS installation and local LAN operation.
- Supported functionality starts deliberately narrow: monitoring gateway health plus safe restart control for XZG firmware.

## Repository Layout

- `custom_components/zigstar_gateway_control/` — Home Assistant custom integration files managed by HACS.
- `custom_components/zigstar_gateway_control/api.py` — local HTTP client for ZigStar/XZG web UI endpoints.
- `custom_components/zigstar_gateway_control/parsing.py` — pure parsing helpers for XZG JSON and legacy ZigStar GW RUS HTML.
- `custom_components/zigstar_gateway_control/sensor.py` — monitoring entities.
- `custom_components/zigstar_gateway_control/binary_sensor.py` — connectivity entities.
- `custom_components/zigstar_gateway_control/button.py` — management button entities.
- `tests/` — lightweight parser tests that can run outside Home Assistant.

## Security Rules

- Never commit real Home Assistant tokens, gateway web passwords, MQTT passwords, cookies, SSH keys, or endpoint-specific secrets.
- The config flow must not ask for MQTT credentials and must not read configuration pages that expose password values unless a future feature explicitly needs it.
- Management actions must be opt-in Home Assistant buttons and should stay limited to low-blast-radius operations.
- Legacy ZigStar GW RUS reboot endpoints are known to execute immediately; do not expose them unless the user explicitly asks for legacy reboot control.

## Maintenance Notes

- Keep `README.md`, `hacs.json`, and `manifest.json` in sync when changing installation requirements or supported features.
- Keep code comments explicit around reverse-engineered endpoint quirks.
- Update this file whenever the project structure or safety posture changes.
