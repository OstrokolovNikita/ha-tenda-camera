from __future__ import annotations

import json
from typing import Any

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

EVENT_STATUS = SensorEntityDescription(
    key="event_status",
    translation_key="event_status",
    icon="mdi:motion-sensor",
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
            ),
            TendaEventStatusSensor(
                entry,
                entry.runtime_data.coordinator,
                EVENT_STATUS,
            ),
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


class TendaEventStatusSensor(TendaCameraEntity, SensorEntity):
    """Expose enough event transport detail to diagnose model-specific codes."""

    def __init__(self, entry, coordinator, description) -> None:
        super().__init__(entry, coordinator)
        self.entity_description = description
        self._event_coordinator = entry.runtime_data.event_coordinator
        self._attr_unique_id = f"{self._device_unique_id}_{description.key}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to event polling updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._event_coordinator.async_add_listener(
                self.async_write_ha_state
            )
        )

    @property
    def native_value(self) -> str:
        """Return a concise event transport status."""
        if not self._event_coordinator.last_update_success:
            return "error"
        return self._event_coordinator.stream_status or "polling"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return short raw RPC2 event details for troubleshooting."""
        raw: dict[str, str] = {}
        for key, value in self._event_coordinator.last_raw.items():
            raw[key] = json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
            )[:700]

        motion = self.coordinator.data.get("motion")
        motion_readback = (
            {
                "Enable": motion.get("Enable"),
                "HumanDetectFliter": motion.get("HumanDetectFliter"),
                "HumanTrack": motion.get("HumanTrack"),
                "Level": motion.get("Level"),
            }
            if isinstance(motion, dict)
            else None
        )

        return {
            "motion_config_readback": motion_readback,
            "attach_sid": self._event_coordinator.attach_sid,
            "stream_status": self._event_coordinator.stream_status,
            "transport_probe": dict(self._event_coordinator.transport_probe.details),
            "cgi_status": self._event_coordinator.cgi_status,
            "subscribe_status": self._event_coordinator.subscribe_status,
            "discovered_codes": sorted(
                self._event_coordinator.discovered_event_codes
            ),
            "onvif_sources": {
                key: list(value)
                for key, value in self._event_coordinator.onvif_sources.items()
                if value
            },
            "supported_codes": sorted(
                self._event_coordinator.supported_codes
            ),
            "unsupported_codes": sorted(
                self._event_coordinator.unsupported_codes
            ),
            "values": dict(self._event_coordinator.data or {}),
            "raw": raw,
        }
