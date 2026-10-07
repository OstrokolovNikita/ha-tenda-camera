from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TendaConfigEntry
from .const import CONFIG_BLIND, CONFIG_MOTION
from .entity import TendaCameraEntity


@dataclass(frozen=True, kw_only=True)
class TendaSwitchDescription(SwitchEntityDescription):
    """Describe a writable Tenda camera setting."""

    section: str
    config_name: str
    config_key: str


SWITCHES: tuple[TendaSwitchDescription, ...] = (
    TendaSwitchDescription(
        key="motion_detection",
        translation_key="motion_detection",
        icon="mdi:motion-sensor",
        entity_category=EntityCategory.CONFIG,
        section="motion",
        config_name=CONFIG_MOTION,
        config_key="Enable",
    ),
    TendaSwitchDescription(
        key="human_detection_filter",
        translation_key="human_detection_filter",
        icon="mdi:account-search",
        entity_category=EntityCategory.CONFIG,
        section="motion",
        config_name=CONFIG_MOTION,
        config_key="HumanDetectFliter",
    ),
    TendaSwitchDescription(
        key="human_tracking",
        translation_key="human_tracking",
        icon="mdi:account-arrow-right",
        entity_category=EntityCategory.CONFIG,
        section="motion",
        config_name=CONFIG_MOTION,
        config_key="HumanTrack",
    ),
    TendaSwitchDescription(
        key="blind_detection",
        translation_key="blind_detection",
        icon="mdi:camera-off",
        entity_category=EntityCategory.CONFIG,
        section="blind",
        config_name=CONFIG_BLIND,
        config_key="Enable",
    ),
)


def _has_key(data: dict[str, Any], section: str, key: str) -> bool:
    table = data.get(section)
    return isinstance(table, dict) and key in table


async def async_setup_entry(
    hass,
    entry: TendaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up writable Tenda camera switches."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        TendaCameraSwitch(entry, coordinator, description)
        for description in SWITCHES
        if _has_key(
            coordinator.data,
            description.section,
            description.config_key,
        )
    )


class TendaCameraSwitch(TendaCameraEntity, SwitchEntity):
    """Writable Tenda camera configuration switch."""

    entity_description: TendaSwitchDescription

    def __init__(
        self,
        entry: TendaConfigEntry,
        coordinator,
        description: TendaSwitchDescription,
    ) -> None:
        super().__init__(entry, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{self._device_unique_id}_{description.key}"
        )

    @property
    def is_on(self) -> bool | None:
        """Return the current camera setting."""
        table = self.coordinator.data.get(self.entity_description.section)
        if not isinstance(table, dict):
            return None

        value = table.get(self.entity_description.config_key)
        if value is None:
            return None
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the camera setting."""
        await self.coordinator.async_set_boolean(
            self.entity_description.config_name,
            self.entity_description.config_key,
            True,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the camera setting."""
        await self.coordinator.async_set_boolean(
            self.entity_description.config_name,
            self.entity_description.config_key,
            False,
        )
