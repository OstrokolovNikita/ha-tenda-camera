from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TendaConfigEntry
from .entity import TendaCameraEntity

CODECS = ["H.264", "H.265"]


@dataclass(frozen=True, kw_only=True)
class TendaCodecSelectDescription(SelectEntityDescription):
    """Describe one RP7 stream codec selector."""

    stream: str
    format_key: str


SELECTS: tuple[TendaCodecSelectDescription, ...] = (
    TendaCodecSelectDescription(
        key="main_stream_codec",
        translation_key="main_stream_codec",
        icon="mdi:video-high-definition",
        entity_category=EntityCategory.CONFIG,
        stream="main",
        format_key="MainFormat",
    ),
    TendaCodecSelectDescription(
        key="sub_stream_codec",
        translation_key="sub_stream_codec",
        icon="mdi:video",
        entity_category=EntityCategory.CONFIG,
        stream="sub",
        format_key="ExtraFormat",
    ),
)


async def async_setup_entry(
    hass,
    entry: TendaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up stream codec selectors."""
    coordinator = entry.runtime_data.coordinator
    encode = coordinator.data.get("encode")

    if not isinstance(encode, dict):
        return

    async_add_entities(
        TendaCodecSelect(entry, coordinator, description)
        for description in SELECTS
        if isinstance(encode.get(description.format_key), list)
    )


class TendaCodecSelect(TendaCameraEntity, SelectEntity):
    """Codec selector matching the RP7 web UI Encode configuration."""

    entity_description: TendaCodecSelectDescription
    _attr_options = CODECS

    def __init__(
        self,
        entry: TendaConfigEntry,
        coordinator,
        description: TendaCodecSelectDescription,
    ) -> None:
        super().__init__(entry, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{self._device_unique_id}_{description.key}"
        )

    @property
    def current_option(self) -> str | None:
        """Return the configured stream codec."""
        encode = self.coordinator.data.get("encode")
        if not isinstance(encode, dict):
            return None

        formats = encode.get(self.entity_description.format_key)
        if not isinstance(formats, list) or not formats:
            return None

        first = formats[0]
        if not isinstance(first, dict):
            return None

        video = first.get("Video")
        if not isinstance(video, dict):
            return None

        codec = video.get("Compression")
        return codec if codec in CODECS else None

    async def async_select_option(self, option: str) -> None:
        """Change stream codec."""
        await self.coordinator.async_set_stream_codec(
            self.entity_description.stream,
            option,
        )
