from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TendaConfigEntry
from .entity import TendaCameraEntity


@dataclass(frozen=True, kw_only=True)
class TendaEventDescription(BinarySensorEntityDescription):
    """Describe one live camera event."""

    event_code: str


EVENT_SENSORS: tuple[TendaEventDescription, ...] = (
    TendaEventDescription(
        key="motion_detected",
        translation_key="motion_detected",
        device_class=BinarySensorDeviceClass.MOTION,
        icon="mdi:motion-sensor",
        event_code="VideoMotion",
    ),
    TendaEventDescription(
        key="person_detected",
        translation_key="person_detected",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        icon="mdi:account-alert",
        event_code="SmartMotionHuman",
    ),
    TendaEventDescription(
        key="tamper_detected",
        translation_key="tamper_detected",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:camera-off",
        event_code="VideoBlind",
    ),
)


async def async_setup_entry(
    hass,
    entry: TendaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up live Tenda event sensors."""
    coordinator = entry.runtime_data.event_coordinator

    async_add_entities(
        TendaEventBinarySensor(entry, coordinator, description)
        for description in EVENT_SENSORS
        if description.event_code in coordinator.supported_codes
    )


class TendaEventBinarySensor(TendaCameraEntity, BinarySensorEntity):
    """Live event state reported by the camera."""

    entity_description: TendaEventDescription

    def __init__(
        self,
        entry: TendaConfigEntry,
        coordinator,
        description: TendaEventDescription,
    ) -> None:
        super().__init__(entry, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{self._device_unique_id}_{description.key}"
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether the event is currently active."""
        return self.coordinator.data.get(self.entity_description.event_code)
