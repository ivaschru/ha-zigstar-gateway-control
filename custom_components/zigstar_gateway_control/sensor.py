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
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("backend"),
    ),
    ZigStarGatewaySensorDescription(
        key="device_temperature",
        translation_key="device_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("device_temperature"),
    ),
    ZigStarGatewaySensorDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("uptime"),
    ),
    ZigStarGatewaySensorDescription(
        key="socket_clients",
        translation_key="socket_clients",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("socket_clients"),
    ),
    ZigStarGatewaySensorDescription(
        key="socket_connected_for",
        translation_key="socket_connected_for",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("socket_connected_for"),
    ),
    ZigStarGatewaySensorDescription(
        key="socket_port",
        translation_key="socket_port",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("socket_port"),
    ),
    ZigStarGatewaySensorDescription(
        key="serial_baud",
        translation_key="serial_baud",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("serial_baud"),
    ),
    ZigStarGatewaySensorDescription(
        key="operational_mode",
        translation_key="operational_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("operational_mode"),
    ),
    ZigStarGatewaySensorDescription(
        key="ethernet_speed",
        translation_key="ethernet_speed",
        native_unit_of_measurement="Mbit/s",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("ethernet_speed"),
    ),
    ZigStarGatewaySensorDescription(
        key="ethernet_ip",
        translation_key="ethernet_ip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("ethernet_ip"),
    ),
    ZigStarGatewaySensorDescription(
        key="mqtt_broker",
        translation_key="mqtt_broker",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("mqtt_broker"),
    ),
    ZigStarGatewaySensorDescription(
        key="esp_firmware",
        translation_key="esp_firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("firmware_version"),
    ),
    ZigStarGatewaySensorDescription(
        key="esp_model",
        translation_key="esp_model",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("esp_model"),
    ),
    ZigStarGatewaySensorDescription(
        key="esp_flash_size",
        translation_key="esp_flash_size",
        native_unit_of_measurement="MB",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("esp_flash_size"),
    ),
    ZigStarGatewaySensorDescription(
        key="heap_used",
        translation_key="heap_used",
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("heap_used"),
    ),
    ZigStarGatewaySensorDescription(
        key="heap_usage",
        translation_key="heap_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_memory_percent("heap_used", "heap_size"),
        available_fn=_has_value("heap_size"),
    ),
    ZigStarGatewaySensorDescription(
        key="fs_usage",
        translation_key="fs_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_memory_percent("fs_used", "fs_size"),
        available_fn=_has_value("fs_size"),
    ),
    ZigStarGatewaySensorDescription(
        key="nvs_usage",
        translation_key="nvs_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_memory_percent("nvs_used", "nvs_size"),
        available_fn=_has_value("nvs_size"),
    ),
    ZigStarGatewaySensorDescription(
        key="zigbee_role",
        translation_key="zigbee_role",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("zigbee_role"),
    ),
    ZigStarGatewaySensorDescription(
        key="zigbee_firmware",
        translation_key="zigbee_firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("zigbee_firmware"),
    ),
    ZigStarGatewaySensorDescription(
        key="zigbee_hardware",
        translation_key="zigbee_hardware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("zigbee_hardware"),
    ),
    ZigStarGatewaySensorDescription(
        key="zigbee_ieee",
        translation_key="zigbee_ieee",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("zigbee_ieee"),
    ),
    ZigStarGatewaySensorDescription(
        key="zigbee_flash_size",
        translation_key="zigbee_flash_size",
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("zigbee_flash_size"),
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
