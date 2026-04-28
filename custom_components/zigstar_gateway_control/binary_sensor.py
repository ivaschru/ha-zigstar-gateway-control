"""Binary sensor entities for ZigStar gateway monitoring."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import ZigStarGatewayCoordinator
from .entity import ZigStarGatewayEntity


@dataclass(frozen=True, kw_only=True)
class ZigStarGatewayBinarySensorDescription(BinarySensorEntityDescription):
    """Describe how one binary sensor reads coordinator data."""

    value_key: str
    available_fn: Callable[[ZigStarGatewayCoordinator], bool] | None = None


def _has_value(key: str) -> Callable[[ZigStarGatewayCoordinator], bool]:
    """Return an availability predicate for payload-backed binary sensors."""
    return lambda coordinator: bool(coordinator.data and coordinator.data.get(key) is not None)


BINARY_SENSOR_DESCRIPTIONS: tuple[ZigStarGatewayBinarySensorDescription, ...] = (
    ZigStarGatewayBinarySensorDescription(
        key="socket_connected",
        translation_key="socket_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="socket_connected",
    ),
    ZigStarGatewayBinarySensorDescription(
        key="ethernet_connected",
        translation_key="ethernet_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="ethernet_connected",
    ),
    ZigStarGatewayBinarySensorDescription(
        key="mqtt_connected",
        translation_key="mqtt_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="mqtt_connected",
        available_fn=_has_value("mqtt_connected"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ZigStar gateway binary sensors for one config entry."""
    runtime_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ZigStarGatewayCoordinator = runtime_data.coordinator
    async_add_entities(
        ZigStarGatewayBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
        if description.available_fn is None or description.available_fn(coordinator)
    )


class ZigStarGatewayBinarySensor(ZigStarGatewayEntity, BinarySensorEntity):
    """Binary connectivity sensor derived from normalized gateway status."""

    entity_description: ZigStarGatewayBinarySensorDescription

    def __init__(
        self,
        coordinator: ZigStarGatewayCoordinator,
        description: ZigStarGatewayBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        device_slug = slugify(coordinator.device_info.name)
        self._attr_unique_id = f"{coordinator.device_identifier}_{description.key}"
        self._attr_suggested_object_id = f"{device_slug}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true when the corresponding gateway status flag is active."""
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get(self.entity_description.value_key)
        return bool(value) if value is not None else None
