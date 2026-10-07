from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from homeassistant.components.camera import (
    Camera,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TendaConfigEntry
from .entity import TendaCameraEntity


@dataclass(frozen=True, kw_only=True)
class TendaCameraDescription(CameraEntityDescription):
    """Describe one RP7 RTSP stream."""

    subtype: int


CAMERAS: tuple[TendaCameraDescription, ...] = (
    TendaCameraDescription(
        key="main_stream",
        translation_key="main_stream",
        icon="mdi:video",
        subtype=0,
    ),
    TendaCameraDescription(
        key="sub_stream",
        translation_key="sub_stream",
        icon="mdi:video-outline",
        subtype=1,
    ),
)


async def async_setup_entry(
    hass,
    entry: TendaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tenda RTSP camera entities."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        TendaRtspCamera(entry, coordinator, description)
        for description in CAMERAS
    )


class TendaRtspCamera(TendaCameraEntity, Camera):
    """Local RTSP stream exposed as a Home Assistant camera."""

    entity_description: TendaCameraDescription
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        entry: TendaConfigEntry,
        coordinator,
        description: TendaCameraDescription,
    ) -> None:
        Camera.__init__(self)
        super().__init__(entry, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{self._device_unique_id}_{description.key}"
        )

    @property
    def use_stream_for_stills(self) -> bool:
        """Use the RTSP stream to generate preview stills."""
        return True

    async def stream_source(self) -> str | None:
        """Return the authenticated local RTSP source."""
        host = self._entry.data[CONF_HOST]
        username = quote(
            str(self._entry.data.get(CONF_USERNAME, "")),
            safe="",
        )
        password = quote(
            str(self._entry.data.get(CONF_PASSWORD, "")),
            safe="",
        )

        auth = ""
        if username:
            auth = username
            if password:
                auth += f":{password}"
            auth += "@"

        return (
            f"rtsp://{auth}{host}:554/"
            f"ch=1&subtype={self.entity_description.subtype}"
        )
