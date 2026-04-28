"""Sensor entities for ZigStar gateway monitoring."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import ZigStarGatewayCoordinator
from .entity import ZigStarGatewayEntity


@dataclass(frozen=True, kw_only=True)
class ZigStarGatewaySensorDescription(SensorEntityDescription):
    """Describe how one sensor reads its value from coordinator data."""

    value_fn: Callable[[ZigStarGatewayCoordinator], Any]
    available_fn: Callable[[ZigStarGatewayCoordinator], bool] | None = None


def _value(key: str) -> Callable[[ZigStarGatewayCoordinator], Any]:
    """Read a normalized payload value by key."""
    return lambda coordinator: coordinator.data.get(key) if coordinator.data else None


def _rounded_value(key: str, digits: int) -> Callable[[ZigStarGatewayCoordinator], Any]:
    """Read a numeric payload value and round it to the desired precision."""
    def read(coordinator: ZigStarGatewayCoordinator) -> Any:
        value = coordinator.data.get(key) if coordinator.data else None
        if not isinstance(value, (int, float)):
            return value
        rounded = round(value, digits)
        return int(rounded) if digits == 0 else rounded

    return read


def _uptime_days() -> Callable[[ZigStarGatewayCoordinator], float | None]:
    """Expose uptime in days for dashboards while keeping raw seconds hidden."""
    def read(coordinator: ZigStarGatewayCoordinator) -> float | None:
        if not coordinator.data:
            return None
        uptime = coordinator.data.get("uptime")
        if not isinstance(uptime, (int, float)):
            return None
        return round(uptime / 86400, 2)

    return read


def _memory_percent(used_key: str, size_key: str) -> Callable[[ZigStarGatewayCoordinator], Any]:
    """Calculate a percentage from two KiB counter fields."""
    def read(coordinator: ZigStarGatewayCoordinator) -> float | None:
        if not coordinator.data:
            return None
        used = coordinator.data.get(used_key)
        size = coordinator.data.get(size_key)
        if not isinstance(used, (int, float)) or not isinstance(size, (int, float)) or size <= 0:
            return None
        return round((used / size) * 100, 1)

    return read


def _has_value(key: str) -> Callable[[ZigStarGatewayCoordinator], bool]:
    """Return an availability predicate for payload-backed sensors."""
    return lambda coordinator: bool(coordinator.data and coordinator.data.get(key) is not None)


SENSOR_DESCRIPTIONS: tuple[ZigStarGatewaySensorDescription, ...] = (
    ZigStarGatewaySensorDescription(
        key="backend",
        translation_key="backend",
        icon="mdi:api",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value("backend"),
    ),
    ZigStarGatewaySensorDescription(
        key="device_temperature",
        translation_key="device_temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_rounded_value("device_temperature", 1),
    ),
    ZigStarGatewaySensorDescription(
        key="uptime_days",
        translation_key="uptime_days",
        icon="mdi:calendar-clock",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_uptime_days(),
    ),
    ZigStarGatewaySensorDescription(
        key="uptime",
        translation_key="uptime",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_rounded_value("uptime", 0),
    ),
    ZigStarGatewaySensorDescription(
        key="socket_clients",
        translation_key="socket_clients",
        icon="mdi:account-network",
        native_unit_of_measurement="clients",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_rounded_value("socket_clients", 0),
    ),
    ZigStarGatewaySensorDescription(
        key="socket_connected_for",
        translation_key="socket_connected_for",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_rounded_value("socket_connected_for", 0),
    ),
    ZigStarGatewaySensorDescription(
        key="socket_port",
        translation_key="socket_port",
        icon="mdi:ethernet-cable",
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_rounded_value("socket_port", 0),
    ),
    ZigStarGatewaySensorDescription(
        key="serial_baud",
        translation_key="serial_baud",
        icon="mdi:serial-port",
        native_unit_of_measurement="baud",
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_rounded_value("serial_baud", 0),
    ),
    ZigStarGatewaySensorDescription(
        key="operational_mode",
        translation_key="operational_mode",
        icon="mdi:cog-transfer",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value("operational_mode"),
    ),
    ZigStarGatewaySensorDescription(
        key="ethernet_speed",
        translation_key="ethernet_speed",
        icon="mdi:speedometer",
        native_unit_of_measurement="Mbit/s",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_rounded_value("ethernet_speed", 0),
    ),
    ZigStarGatewaySensorDescription(
        key="ethernet_ip",
        translation_key="ethernet_ip",
        icon="mdi:ip-network",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value("ethernet_ip"),
    ),
    ZigStarGatewaySensorDescription(
        key="mqtt_broker",
        translation_key="mqtt_broker",
        icon="mdi:message-cog",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value("mqtt_broker"),
    ),
    ZigStarGatewaySensorDescription(
        key="esp_firmware",
        translation_key="esp_firmware",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value("firmware_version"),
    ),
    ZigStarGatewaySensorDescription(
        key="esp_model",
        translation_key="esp_model",
        icon="mdi:developer-board",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value("esp_model"),
    ),
    ZigStarGatewaySensorDescription(
        key="esp_flash_size",
        translation_key="esp_flash_size",
        icon="mdi:harddisk",
        native_unit_of_measurement="MB",
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_rounded_value("esp_flash_size", 0),
    ),
    ZigStarGatewaySensorDescription(
        key="heap_used",
        translation_key="heap_used",
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_rounded_value("heap_used", 0),
    ),
    ZigStarGatewaySensorDescription(
        key="heap_usage",
        translation_key="heap_usage",
        icon="mdi:memory",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_memory_percent("heap_used", "heap_size"),
        available_fn=_has_value("heap_size"),
    ),
    ZigStarGatewaySensorDescription(
        key="fs_usage",
        translation_key="fs_usage",
        icon="mdi:folder-cog",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_memory_percent("fs_used", "fs_size"),
        available_fn=_has_value("fs_size"),
    ),
    ZigStarGatewaySensorDescription(
        key="nvs_usage",
        translation_key="nvs_usage",
        icon="mdi:database-cog",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_memory_percent("nvs_used", "nvs_size"),
        available_fn=_has_value("nvs_size"),
    ),
    ZigStarGatewaySensorDescription(
        key="zigbee_role",
        translation_key="zigbee_role",
        icon="mdi:zigbee",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("zigbee_role"),
    ),
    ZigStarGatewaySensorDescription(
        key="zigbee_firmware",
        translation_key="zigbee_firmware",
        icon="mdi:zigbee",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value("zigbee_firmware"),
    ),
    ZigStarGatewaySensorDescription(
        key="zigbee_hardware",
        translation_key="zigbee_hardware",
        icon="mdi:expansion-card",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value("zigbee_hardware"),
    ),
    ZigStarGatewaySensorDescription(
        key="zigbee_ieee",
        translation_key="zigbee_ieee",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value("zigbee_ieee"),
    ),
    ZigStarGatewaySensorDescription(
        key="zigbee_flash_size",
        translation_key="zigbee_flash_size",
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_rounded_value("zigbee_flash_size", 0),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ZigStar gateway sensors for one config entry."""
    runtime_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ZigStarGatewayCoordinator = runtime_data.coordinator
    async_add_entities(
        ZigStarGatewaySensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if description.available_fn is None or description.available_fn(coordinator)
    )


class ZigStarGatewaySensor(ZigStarGatewayEntity, SensorEntity):
    """Representation of one ZigStar gateway monitoring sensor."""

    entity_description: ZigStarGatewaySensorDescription

    def __init__(
        self,
        coordinator: ZigStarGatewayCoordinator,
        description: ZigStarGatewaySensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        device_slug = slugify(coordinator.device_info.name)
        self._attr_unique_id = f"{coordinator.device_identifier}_{description.key}"
        self._attr_suggested_object_id = f"{device_slug}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the latest parsed value for this sensor."""
        return self.entity_description.value_fn(self.coordinator)
