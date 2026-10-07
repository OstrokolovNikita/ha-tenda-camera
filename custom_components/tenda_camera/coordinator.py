from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    TendaRpcAuthError,
    TendaRpcClient,
    TendaRpcConnectionError,
    TendaRpcResponseError,
)
from .const import (
    CONFIG_BLIND,
    CONFIG_ENCODE,
    CONFIG_MOTION,
    CONFIG_RECORD_MODE,
    CONFIG_SECURITY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def normalize_config_table(value: Any) -> dict[str, Any] | None:
    """Normalize RP7 config tables that may be dicts or one-item lists."""
    if isinstance(value, dict):
        if isinstance(value.get("table"), dict):
            return value["table"]
        return value

    if (
        isinstance(value, list)
        and value
        and isinstance(value[0], dict)
    ):
        return value[0]

    return None


class TendaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate local Tenda camera state updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: TendaRpcClient,
        device_info: dict[str, Any],
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self.device_info = device_info

    async def _async_optional_config(self, name: str) -> Any | None:
        """Read an optional table without making the whole entry unavailable."""
        try:
            return await self.client.async_get_config(name)
        except (
            TendaRpcAuthError,
            TendaRpcConnectionError,
            TendaRpcResponseError,
        ) as err:
            _LOGGER.debug("Optional RP7 config %s is unavailable: %s", name, err)
            return None

    async def async_set_boolean(
        self,
        config_name: str,
        key: str,
        value: bool,
    ) -> None:
        """Set one boolean config key and refresh all entities."""
        try:
            await self.client.async_set_config_value(config_name, key, value)
        except (
            TendaRpcAuthError,
            TendaRpcConnectionError,
            TendaRpcResponseError,
        ) as err:
            raise UpdateFailed(
                f"Unable to update {config_name}.{key}: {err}"
            ) from err

        await self.async_request_refresh()

    async def async_set_stream_codec(
        self,
        stream: str,
        codec: str,
    ) -> None:
        """Set MainFormat/ExtraFormat codec exactly as the RP7 web UI does."""
        if stream not in {"main", "sub"}:
            raise UpdateFailed(f"Unknown stream {stream!r}")
        if codec not in {"H.264", "H.265"}:
            raise UpdateFailed(f"Unsupported codec {codec!r}")

        try:
            table = await self.client.async_get_config(CONFIG_ENCODE)
            if not isinstance(table, dict):
                raise TendaRpcResponseError(
                    "configManager.setConfig[Encode]",
                    message="Encode table is not a mapping",
                    raw={"table": table},
                )

            updated = deepcopy(table)
            format_key = "MainFormat" if stream == "main" else "ExtraFormat"
            formats = updated.get(format_key)
            if not isinstance(formats, list) or not formats:
                raise TendaRpcResponseError(
                    "configManager.setConfig[Encode]",
                    message=f"Encode.{format_key} is missing",
                    raw={"table": table},
                )

            for item in formats:
                if not isinstance(item, dict):
                    continue
                video = item.get("Video")
                if not isinstance(video, dict):
                    continue
                video["Compression"] = codec
                video["Profile"] = "Main" if codec == "H.264" else "Baseline"

            await self.client.async_set_config(CONFIG_ENCODE, updated)
        except (
            TendaRpcAuthError,
            TendaRpcConnectionError,
            TendaRpcResponseError,
        ) as err:
            raise UpdateFailed(
                f"Unable to update {stream} stream codec: {err}"
            ) from err

        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            motion_raw = await self.client.async_get_config(CONFIG_MOTION)
            blind_raw = await self._async_optional_config(CONFIG_BLIND)
            record_mode = await self._async_optional_config(CONFIG_RECORD_MODE)
            security_raw = await self._async_optional_config(CONFIG_SECURITY)
            encode_raw = await self._async_optional_config(CONFIG_ENCODE)
        except (
            TendaRpcAuthError,
            TendaRpcConnectionError,
            TendaRpcResponseError,
        ) as err:
            raise UpdateFailed(f"Camera RPC error: {err}") from err

        return {
            "motion": normalize_config_table(motion_raw),
            "blind": normalize_config_table(blind_raw),
            "record_mode": record_mode,
            "security": normalize_config_table(security_raw),
            "encode": encode_raw,
            "_raw": {
                "motion": motion_raw,
                "blind": blind_raw,
                "security": security_raw,
                "encode": encode_raw,
            },
        }
