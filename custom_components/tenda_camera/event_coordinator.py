from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    TendaRpcAuthError,
    TendaRpcClient,
    TendaRpcConnectionError,
    TendaRpcResponseError,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

EVENT_SCAN_INTERVAL = timedelta(seconds=2)

EVENT_CODES: tuple[str, ...] = (
    "VideoMotion",
    "SmartMotionHuman",
    "VideoBlind",
)


class TendaEventCoordinator(DataUpdateCoordinator[dict[str, bool | None]]):
    """Poll short-lived event state from the camera's RPC2 API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: TendaRpcClient,
        device_info: dict[str, Any],
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_events",
            update_interval=EVENT_SCAN_INTERVAL,
        )
        self.client = client
        self.device_info = device_info
        self.supported_codes: set[str] = set()
        self.unsupported_codes: set[str] = set()

    async def _async_event_active(self, code: str) -> bool | None:
        if code in self.unsupported_codes:
            return None

        try:
            data = await self.client.async_rpc(
                "eventManager.getEventIndexes",
                {"code": code},
            )
        except TendaRpcResponseError as err:
            self.unsupported_codes.add(code)
            _LOGGER.debug("RP7 event code %s is unsupported: %s", code, err)
            return None

        params = data.get("params") or {}
        indexes = params.get("indexes")

        if indexes is None:
            # Successful call without indexes is treated as supported/inactive.
            indexes = []

        if not isinstance(indexes, list):
            _LOGGER.debug(
                "Unexpected event indexes shape for %s: %r",
                code,
                indexes,
            )
            return None

        self.supported_codes.add(code)
        return bool(indexes)

    async def _async_update_data(self) -> dict[str, bool | None]:
        try:
            return {
                code: await self._async_event_active(code)
                for code in EVENT_CODES
            }
        except (
            TendaRpcAuthError,
            TendaRpcConnectionError,
        ) as err:
            raise UpdateFailed(f"Unable to poll camera events: {err}") from err
