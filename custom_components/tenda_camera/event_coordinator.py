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
        self._attached = False
        self.attach_sid: Any | None = None
        self.last_raw: dict[str, Any] = {}

    async def async_attach(self) -> None:
        """Activate the RPC2 event manager before reading event indexes."""
        data = await self.client.async_rpc(
            "eventManager.attach",
            {"codes": ["All"]},
        )
        params = data.get("params") or {}
        self.attach_sid = params.get("SID")
        self._attached = True
        _LOGGER.debug("RP7 event manager attached; SID=%r", self.attach_sid)

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
            self.last_raw[code] = {
                "error": str(err),
                "raw": err.raw,
            }
            _LOGGER.debug("RP7 event code %s is unsupported: %s", code, err)
            return None

        self.last_raw[code] = data
        params = data.get("params") or {}
        indexes = params.get("indexes")

        # On this RPC family an inactive event is commonly returned as an
        # empty params object rather than {"indexes": []}.
        if indexes is None:
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
            if not self._attached:
                await self.async_attach()

            return {
                code: await self._async_event_active(code)
                for code in EVENT_CODES
            }
        except TendaRpcAuthError:
            # Re-authentication creates a new camera session; attach the
            # event manager again on the next cycle.
            self._attached = False
            raise
        except TendaRpcConnectionError as err:
            raise UpdateFailed(f"Unable to poll camera events: {err}") from err
        except TendaRpcResponseError as err:
            # Some firmwares may refuse eventManager.attach. Surface the
            # failure rather than pretending that every event is simply off.
            self._attached = False
            raise UpdateFailed(f"Unable to attach camera event manager: {err}") from err
