from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TendaConfigEntry
from .entity import TendaCameraEntity

RECORD_MODE = SensorEntityDescription(
    key="record_mode",
    translation_key="record_mode",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass,
    entry: TendaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tenda sensors."""
    async_add_entities(
        [
            TendaRecordModeSensor(
                entry,
                entry.runtime_data.coordinator,
                RECORD_MODE,
            )
        ]
    )


class TendaRecordModeSensor(TendaCameraEntity, SensorEntity):
    """Expose the camera RecordMode value for reverse-engineering."""

    def __init__(self, entry, coordinator, description) -> None:
        super().__init__(entry, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_unique_id}_{description.key}"

    @property
    def native_value(self) -> str | None:
        """Return raw record mode in a stable diagnostic form."""
        value = self.coordinator.data.get("record_mode")
        if not isinstance(value, list) or not value:
            return None
        first = value[0]
        if not isinstance(first, dict):
            return None
        mode = first.get("Mode")
        return None if mode is None else str(mode)
