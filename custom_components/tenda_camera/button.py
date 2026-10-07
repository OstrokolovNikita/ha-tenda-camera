from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TendaConfigEntry
from .entity import TendaCameraEntity


@dataclass(frozen=True, kw_only=True)
class TendaButtonDescription(ButtonEntityDescription):
    """Describe a Tenda camera button."""

    action: str


BUTTONS: tuple[TendaButtonDescription, ...] = (
    TendaButtonDescription(
        key="refresh",
        translation_key="refresh",
        icon="mdi:refresh",
        entity_category=EntityCategory.DIAGNOSTIC,
        action="refresh",
    ),
    TendaButtonDescription(
        key="reauthenticate",
        translation_key="reauthenticate",
        icon="mdi:login",
        entity_category=EntityCategory.DIAGNOSTIC,
        action="reauthenticate",
    ),
)


async def async_setup_entry(
    hass,
    entry: TendaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tenda camera buttons."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        TendaCameraButton(entry, coordinator, description)
        for description in BUTTONS
    )


class TendaCameraButton(TendaCameraEntity, ButtonEntity):
    """Tenda camera utility button."""

    entity_description: TendaButtonDescription

    def __init__(
        self,
        entry: TendaConfigEntry,
        coordinator,
        description: TendaButtonDescription,
    ) -> None:
        super().__init__(entry, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{self._device_unique_id}_{description.key}"
        )

    async def async_press(self) -> None:
        """Run the requested utility action."""
        if self.entity_description.action == "reauthenticate":
            await self.coordinator.client.async_login()

        await self.coordinator.async_request_refresh()
