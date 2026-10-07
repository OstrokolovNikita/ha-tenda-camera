from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from homeassistant.components.camera import (
    Camera,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TendaConfigEntry
from .entity import TendaCameraEntity


@dataclass(frozen=True, kw_only=True)
class TendaCameraDescription(CameraEntityDescription):
    """Describe one RP7 RTSP stream."""

    subtype: int
    native_stream: bool = True


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
        native_stream=False,
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
        self._event_coordinator = entry.runtime_data.event_coordinator
        self._attr_unique_id = (
            f"{self._device_unique_id}_{description.key}"
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe camera state to both settings and live-event coordinators."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._event_coordinator.async_add_listener(
                self._handle_event_update
            )
        )

    @callback
    def _handle_event_update(self) -> None:
        """Refresh camera card attributes when a live event changes."""
        self.async_write_ha_state()

    def _configured_codec(self) -> str | None:
        """Return the current codec for this stream."""
        encode = self.coordinator.data.get("encode")
        if not isinstance(encode, dict):
            return None

        format_key = (
            "MainFormat"
            if self.entity_description.subtype == 0
            else "ExtraFormat"
        )
        formats = encode.get(format_key)
        if not isinstance(formats, list) or not formats:
            return None

        first = formats[0]
        if not isinstance(first, dict):
            return None
        video = first.get("Video")
        if not isinstance(video, dict):
            return None

        codec = video.get("Compression")
        return codec if isinstance(codec, str) else None

    @property
    def use_stream_for_stills(self) -> bool:
        """Use the RTSP stream to generate preview stills."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose controls/events so the bundled camera card needs one entity."""
        motion = self.coordinator.data.get("motion")
        blind = self.coordinator.data.get("blind")
        events = self._event_coordinator.data or {}

        return {
            "brand": "Tenda",
            "stream_role": (
                "main"
                if self.entity_description.subtype == 0
                else "sub"
            ),
            "stream_codec": self._configured_codec(),
            "motion_detection": (
                bool(motion.get("Enable"))
                if isinstance(motion, dict)
                and motion.get("Enable") is not None
                else None
            ),
            "human_detection": (
                bool(motion.get("HumanDetectFliter"))
                if isinstance(motion, dict)
                and motion.get("HumanDetectFliter") is not None
                else None
            ),
            "human_tracking": (
                bool(motion.get("HumanTrack"))
                if isinstance(motion, dict)
                and motion.get("HumanTrack") is not None
                else None
            ),
            "tamper_detection": (
                bool(blind.get("Enable"))
                if isinstance(blind, dict)
                and blind.get("Enable") is not None
                else None
            ),
            "motion_detected": events.get("VideoMotion"),
            "person_detected": events.get("SmartMotionHuman"),
            "tamper_detected": events.get("VideoBlind"),
        }

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Decode a still from RTSP for the MJPEG-compatible HA fallback."""
        stream = self.stream or await self.async_create_stream()
        if stream is None:
            return None
        return await stream.async_get_image(
            width=width,
            height=height,
            wait_for_next_keyframe=True,
        )

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
