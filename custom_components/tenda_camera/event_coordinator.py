from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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
        self._attached_generation = -1
        self._attach_supported = True
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
        self._attached_generation = self.client.auth_generation
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
            if (
                self._attach_supported
                and (
                    not self._attached
                    or self._attached_generation != self.client.auth_generation
                )
            ):
                try:
                    await self.async_attach()
                except TendaRpcResponseError as err:
                    # Do not take the whole camera integration down just because
                    # this firmware refuses eventManager.attach. Keep polling so
                    # diagnostics can still show what getEventIndexes returns.
                    self._attach_supported = False
                    self._attached = False
                    self.last_raw["eventManager.attach"] = {
                        "error": str(err),
                        "raw": err.raw,
                    }
                    _LOGGER.warning(
                        "RP7 eventManager.attach is unavailable: %s", err
                    )

            return {
                code: await self._async_event_active(code)
                for code in EVENT_CODES
            }
        except (
            TendaRpcAuthError,
            TendaRpcConnectionError,
            TendaRpcResponseError,
        ) as err:
            # Event transport is diagnostic/optional. A firmware-specific
            # event failure must never take the whole camera entry down.
            self._attached = False
            self.last_raw["poll_error"] = {"error": str(err)}
            _LOGGER.warning("Unable to poll RP7 camera events: %s", err)
            return {code: None for code in EVENT_CODES}
