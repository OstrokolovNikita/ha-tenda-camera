from __future__ import annotations

import asyncio
import json
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
PULSE_HOLD_SECONDS = 3.0

EVENT_CODES: tuple[str, ...] = (
    "VideoMotion",
    "SmartMotionHuman",
    "VideoBlind",
)

MOTION_CODES = {
    "VideoMotion",
    "MotionDetection",
    "MotionDetect",
}
PERSON_CODES = {
    "SmartMotionHuman",
    "HumanDetection",
    "HumanDetect",
    "Human",
}
TAMPER_CODES = {
    "VideoBlind",
    "TamperingDetection",
    "TamperDetection",
    "TamperDetect",
}


def _extract_json_objects(buffer: str) -> tuple[list[dict[str, Any]], str]:
    """Extract complete JSON objects embedded in SubscribeNotify HTML/script."""
    objects: list[dict[str, Any]] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    last_consumed = 0

    for index, char in enumerate(buffer):
        if start is None:
            if char == "{":
                start = index
                depth = 1
                in_string = False
                escaped = False
            continue

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                raw = buffer[start : index + 1]
                try:
                    value = json.loads(raw)
                except ValueError:
                    pass
                else:
                    if isinstance(value, dict):
                        objects.append(value)
                last_consumed = index + 1
                start = None

    if start is not None:
        tail = buffer[start:]
    else:
        tail = buffer[last_consumed:]

    # Prevent an HTML response without JSON from growing forever.
    if len(tail) > 65536:
        tail = tail[-8192:]
    return objects, tail


def _contains_human(value: Any) -> bool:
    """Look for explicit human/person classification in nested event data."""
    if isinstance(value, str):
        return value.lower() in {"human", "person", "pedestrian"}
    if isinstance(value, dict):
        return any(
            _contains_human(item)
            for key, item in value.items()
            if key.lower()
            in {
                "object",
                "objecttype",
                "type",
                "class",
                "classname",
                "category",
                "label",
            }
        ) or any(_contains_human(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_human(item) for item in value)
    return False


class TendaEventCoordinator(DataUpdateCoordinator[dict[str, bool | None]]):
    """Track short-lived RP7 events from RPC2/SubscribeNotify."""

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
        self.discovered_event_codes: set[str] = set()
        self._attached = False
        self._attached_generation = -1
        self._attach_supported = True
        self.attach_sid: Any | None = None
        self.last_raw: dict[str, Any] = {}
        self.stream_status = "stopped"
        self._event_task: asyncio.Task[None] | None = None
        self._pulse_clear_tasks: dict[str, asyncio.Task[None]] = {}
        self._live_states: dict[str, bool] = {
            "VideoMotion": False,
            "SmartMotionHuman": False,
            "VideoBlind": False,
        }

    async def async_attach(self) -> None:
        """Activate the RPC2 event manager before subscribing to notifications."""
        data = await self.client.async_rpc(
            "eventManager.attach",
            {"codes": ["All"]},
        )
        params = data.get("params") or {}
        self.attach_sid = params.get("SID")
        self._attached = True
        self._attached_generation = self.client.auth_generation
        self.last_raw["eventManager.attach"] = data
        _LOGGER.debug("RP7 event manager attached; SID=%r", self.attach_sid)

    async def async_start_listener(self) -> None:
        """Start the long-lived local event stream task."""
        if self._event_task is not None and not self._event_task.done():
            return
        self._event_task = self.hass.async_create_task(
            self._async_event_listener(),
            f"{DOMAIN} SubscribeNotify",
        )

    async def async_stop_listener(self) -> None:
        """Stop the long-lived local event stream task."""
        if self._event_task is not None:
            self._event_task.cancel()
            try:
                await self._event_task
            except asyncio.CancelledError:
                pass
            self._event_task = None

        for task in self._pulse_clear_tasks.values():
            task.cancel()
        self._pulse_clear_tasks.clear()
        self.stream_status = "stopped"

    async def _async_clear_pulse(self, canonical: str) -> None:
        try:
            await asyncio.sleep(PULSE_HOLD_SECONDS)
        except asyncio.CancelledError:
            return

        self._live_states[canonical] = False
        self.async_set_updated_data(dict(self._live_states))

    def _set_event_state(
        self,
        canonical: str,
        active: bool,
        *,
        pulse: bool,
    ) -> None:
        self._live_states[canonical] = active

        previous = self._pulse_clear_tasks.pop(canonical, None)
        if previous is not None:
            previous.cancel()

        if pulse and active:
            self._pulse_clear_tasks[canonical] = self.hass.async_create_task(
                self._async_clear_pulse(canonical),
                f"{DOMAIN} clear {canonical}",
            )

        self.async_set_updated_data(dict(self._live_states))

    def _handle_event(self, event: dict[str, Any]) -> None:
        code = str(event.get("Code") or "")
        action = str(event.get("Action") or "Pulse")
        data = event.get("Data")

        if not code:
            return

        self.discovered_event_codes.add(code)
        self.last_raw[f"notify:{code}"] = event

        action_lower = action.lower()
        active = action_lower != "stop"
        pulse = action_lower == "pulse"

        if code in MOTION_CODES:
            self._set_event_state("VideoMotion", active, pulse=pulse)

        if code in PERSON_CODES or _contains_human(data):
            self._set_event_state("SmartMotionHuman", active, pulse=pulse)

        if code in TAMPER_CODES:
            self._set_event_state("VideoBlind", active, pulse=pulse)

    def _handle_notification(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        if method != "client.notifyEventStream":
            return

        params = message.get("params") or {}
        event_list = params.get("eventList") or []
        if not isinstance(event_list, list):
            return

        self.last_raw["last_notify"] = message
        for event in event_list:
            if isinstance(event, dict):
                self._handle_event(event)

    async def _async_event_listener(self) -> None:
        """Consume Dahua-style local event notifications without cloud access."""
        retry_delay = 2.0

        while True:
            response = None
            try:
                if (
                    not self._attached
                    or self._attached_generation != self.client.auth_generation
                ):
                    await self.async_attach()

                response = await self.client.async_open_event_stream()
                self.stream_status = "connected"
                retry_delay = 2.0
                buffer = ""

                async for chunk in response.content.iter_any():
                    if not chunk:
                        continue
                    buffer += chunk.decode("utf-8", errors="ignore")
                    messages, buffer = _extract_json_objects(buffer)
                    for message in messages:
                        self._handle_notification(message)

                self.stream_status = "disconnected"
            except asyncio.CancelledError:
                raise
            except (
                TendaRpcAuthError,
                TendaRpcConnectionError,
                TendaRpcResponseError,
                OSError,
            ) as err:
                self.stream_status = "error"
                self.last_raw["SubscribeNotify"] = {"error": str(err)}
                _LOGGER.debug("RP7 SubscribeNotify unavailable: %s", err)
            finally:
                if response is not None:
                    response.close()

            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30.0)

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
            return None

        self.last_raw[code] = data
        params = data.get("params") or {}
        indexes = params.get("indexes")
        if indexes is None:
            indexes = []
        if not isinstance(indexes, list):
            return None

        self.supported_codes.add(code)
        return bool(indexes)

    async def _async_update_data(self) -> dict[str, bool | None]:
        """Keep a polling fallback while event subscription is being verified."""
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
                    self._attach_supported = False
                    self._attached = False
                    self.last_raw["eventManager.attach"] = {
                        "error": str(err),
                        "raw": err.raw,
                    }

            polled = {
                code: await self._async_event_active(code)
                for code in EVENT_CODES
            }

            # SubscribeNotify is authoritative once connected; otherwise keep
            # the old RPC polling values as a harmless diagnostic fallback.
            if self.stream_status == "connected":
                return dict(self._live_states)

            return polled
        except (
            TendaRpcAuthError,
            TendaRpcConnectionError,
            TendaRpcResponseError,
        ) as err:
            self._attached = False
            self.last_raw["poll_error"] = {"error": str(err)}
            return dict(self._live_states)
