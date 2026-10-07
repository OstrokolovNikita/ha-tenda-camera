from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import CONF_HOST
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TendaConfigEntry
from .entity import TendaCameraEntity


@dataclass(frozen=True, kw_only=True)
class TendaButtonDescription(ButtonEntityDescription):
    """Describe a Tenda camera button."""

    action: str
    ptz_axis: str | None = None
    ptz_direction: str | None = None


BUTTONS: tuple[TendaButtonDescription, ...] = (
    TendaButtonDescription(
        key="ptz_up",
        translation_key="ptz_up",
        icon="mdi:chevron-up",
        action="ptz",
        ptz_axis="tilt",
        ptz_direction="UP",
    ),
    TendaButtonDescription(
        key="ptz_down",
        translation_key="ptz_down",
        icon="mdi:chevron-down",
        action="ptz",
        ptz_axis="tilt",
        ptz_direction="DOWN",
    ),
    TendaButtonDescription(
        key="ptz_left",
        translation_key="ptz_left",
        icon="mdi:chevron-left",
        action="ptz",
        ptz_axis="pan",
        ptz_direction="LEFT",
    ),
    TendaButtonDescription(
        key="ptz_right",
        translation_key="ptz_right",
        icon="mdi:chevron-right",
        action="ptz",
        ptz_axis="pan",
        ptz_direction="RIGHT",
    ),
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


def _find_matching_onvif_camera(hass, host: str) -> str | None:
    """Find the existing ONVIF camera entity configured for the same host."""
    registry = er.async_get(hass)

    for config_entry in hass.config_entries.async_entries("onvif"):
        if str(config_entry.data.get(CONF_HOST, "")).strip() != host:
            continue

        for entity_entry in er.async_entries_for_config_entry(
            registry,
            config_entry.entry_id,
        ):
            if entity_entry.entity_id.startswith("camera."):
                return entity_entry.entity_id

    return None


async def async_setup_entry(
    hass,
    entry: TendaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tenda camera buttons."""
    coordinator = entry.runtime_data.coordinator
    onvif_camera = _find_matching_onvif_camera(
        hass,
        str(entry.data[CONF_HOST]).strip(),
    )

    async_add_entities(
        TendaCameraButton(
            entry,
            coordinator,
            description,
            onvif_camera=onvif_camera,
        )
        for description in BUTTONS
    )


class TendaCameraButton(TendaCameraEntity, ButtonEntity):
    """Tenda camera utility/PTZ button."""

    entity_description: TendaButtonDescription

    def __init__(
        self,
        entry: TendaConfigEntry,
        coordinator,
        description: TendaButtonDescription,
        *,
        onvif_camera: str | None,
    ) -> None:
        super().__init__(entry, coordinator)
        self.entity_description = description
        self._onvif_camera = onvif_camera
        self._attr_unique_id = (
            f"{self._device_unique_id}_{description.key}"
        )

    @property
    def available(self) -> bool:
        """Return availability for utility and PTZ buttons."""
        if self.entity_description.action == "ptz":
            return (
                super().available
                and self._onvif_camera is not None
            )
        return super().available

    async def _async_ptz(self) -> None:
        """Move the matching ONVIF camera by one short step."""
        if (
            self._onvif_camera is None
            or self.entity_description.ptz_axis is None
            or self.entity_description.ptz_direction is None
        ):
            return

        data: dict[str, Any] = {
            "entity_id": self._onvif_camera,
            "move_mode": "ContinuousMove",
            "continuous_duration": 0.35,
            "speed": 0.6,
        }
        data[self.entity_description.ptz_axis] = (
            self.entity_description.ptz_direction
        )

        await self.hass.services.async_call(
            "onvif",
            "ptz",
            data,
            blocking=True,
        )

    async def async_press(self) -> None:
        """Run the requested utility/PTZ action."""
        action = self.entity_description.action

        if action == "ptz":
            await self._async_ptz()
            return

        if action == "reauthenticate":
            await self.coordinator.client.async_login()

        await self.coordinator.async_request_refresh()
