from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TendaConfigEntry
from .entity import TendaCameraEntity


@dataclass(frozen=True, kw_only=True)
class TendaBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a Tenda configuration state binary sensor."""

    value_fn: Callable[[dict[str, Any]], bool | None]


def _nested_bool(
    section: str,
    key: str,
) -> Callable[[dict[str, Any]], bool | None]:
    def _value(data: dict[str, Any]) -> bool | None:
        table = data.get(section)
        if not isinstance(table, dict) or key not in table:
            return None
        return bool(table[key])

    return _value


SENSORS: tuple[TendaBinarySensorDescription, ...] = (
    TendaBinarySensorDescription(
        key="motion_detection_enabled",
        translation_key="motion_detection_enabled",
        entity_category=EntityCategory.CONFIG,
        value_fn=_nested_bool("motion", "Enable"),
    ),
    TendaBinarySensorDescription(
        key="human_detection_filter_enabled",
        translation_key="human_detection_filter_enabled",
        entity_category=EntityCategory.CONFIG,
        value_fn=_nested_bool("motion", "HumanDetectFliter"),
    ),
    TendaBinarySensorDescription(
        key="human_tracking_enabled",
        translation_key="human_tracking_enabled",
        entity_category=EntityCategory.CONFIG,
        value_fn=_nested_bool("motion", "HumanTrack"),
    ),
    TendaBinarySensorDescription(
        key="blind_detection_enabled",
        translation_key="blind_detection_enabled",
        entity_category=EntityCategory.CONFIG,
        value_fn=_nested_bool("blind", "Enable"),
    ),
    TendaBinarySensorDescription(
        key="onvif_enabled",
        translation_key="onvif_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_nested_bool("security", "OnvifEnable"),
    ),
    TendaBinarySensorDescription(
        key="rtsp_enabled",
        translation_key="rtsp_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_nested_bool("security", "rtsp"),
    ),
)


async def async_setup_entry(
    hass,
    entry: TendaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tenda binary sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        TendaCameraBinarySensor(entry, coordinator, description)
        for description in SENSORS
    )


class TendaCameraBinarySensor(TendaCameraEntity, BinarySensorEntity):
    """Representation of a Tenda camera configuration state."""

    entity_description: TendaBinarySensorDescription

    def __init__(
        self,
        entry: TendaConfigEntry,
        coordinator,
        description: TendaBinarySensorDescription,
    ) -> None:
        super().__init__(entry, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_unique_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the current boolean state."""
        return self.entity_description.value_fn(self.coordinator.data)
