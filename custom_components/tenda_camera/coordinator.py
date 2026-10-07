from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TendaRpcClient, TendaRpcConnectionError, TendaRpcResponseError
from .const import (
    CONFIG_BLIND,
    CONFIG_MOTION,
    CONFIG_RECORD_MODE,
    CONFIG_SECURITY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


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
        try:
            return await self.client.async_get_config(name)
        except TendaRpcResponseError:
            return None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            motion = await self.client.async_get_config(CONFIG_MOTION)
            blind = await self._async_optional_config(CONFIG_BLIND)
            record_mode = await self._async_optional_config(CONFIG_RECORD_MODE)
            security = await self._async_optional_config(CONFIG_SECURITY)
        except TendaRpcConnectionError as err:
            raise UpdateFailed(f"Unable to communicate with camera: {err}") from err
        except TendaRpcResponseError as err:
            raise UpdateFailed(f"Camera RPC error: {err}") from err

        return {
            "motion": motion,
            "blind": blind,
            "record_mode": record_mode,
            "security": security,
        }
