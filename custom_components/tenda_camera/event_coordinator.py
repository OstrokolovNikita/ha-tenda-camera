from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import json
import logging
import re
from typing import Any

from homeassistant.const import CONF_HOST, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import (
    TendaRpcAuthError,
    TendaRpcClient,
    TendaRpcConnectionError,
    TendaRpcResponseError,
)
from .const import DOMAIN
from .transport_probe import TendaTransportProbe

_LOGGER = logging.getLogger(__name__)

EVENT_SCAN_INTERVAL = timedelta(seconds=1)
PULSE_HOLD_SECONDS = 3.0

POLL_CODE_MAP: dict[str, str] = {
    "VideoMotion": "VideoMotion",
    "VideoMotionInfo": "VideoMotion",
    "MDResult": "VideoMotion",
    "MoveDetection": "VideoMotion",
    "SmartMotionHuman": "SmartMotionHuman",
    "HumanDetection": "SmartMotionHuman",
    "HumanTrait": "SmartMotionHuman",
    "VideoBlind": "VideoBlind",
    "TamperingDetection": "VideoBlind",
}

EVENT_CODES: tuple[str, ...] = (
    "VideoMotion",
    "SmartMotionHuman",
    "VideoBlind",
)

MOTION_CODES = {
    "VideoMotion",
    "VideoMotionInfo",
    "MDResult",
    "MoveDetection",
    "MotionDetection",
    "MotionDetect",
}
PERSON_CODES = {
    "SmartMotionHuman",
    "HumanDetection",
    "HumanDetect",
    "HumanTrait",
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

    if len(tail) > 65536:
        tail = tail[-8192:]
    return objects, tail


def _parse_cgi_event(payload: str) -> dict[str, Any] | None:
    """Parse one Dahua-style CGI event payload."""
    code_match = re.search(r"(?:^|\n)Code=([^;\r\n]+)", payload)
    if code_match is None:
        return None

    action_match = re.search(r";action=([^;\r\n]+)", payload)
    index_match = re.search(r";index=([^;\r\n]+)", payload)

    data: Any = None
    data_marker = ";data="
    data_pos = payload.find(data_marker)
    if data_pos >= 0:
        raw_data = payload[data_pos + len(data_marker) :].strip()
        try:
            data = json.loads(raw_data)
        except ValueError:
            data = raw_data

    event: dict[str, Any] = {
        "Code": code_match.group(1).strip(),
        "Action": (
            action_match.group(1).strip()
            if action_match is not None
            else "Pulse"
        ),
    }
    if index_match is not None:
        event["Index"] = index_match.group(1).strip()
    if data is not None:
        event["Data"] = data
    return event


def _extract_cgi_events(buffer: str) -> tuple[list[dict[str, Any]], str]:
    """Extract complete Code=... blocks from a multipart CGI event stream."""
    events: list[dict[str, Any]] = []
    cursor = 0

    while True:
        start_match = re.search(r"(?m)^Code=", buffer[cursor:])
        if start_match is None:
            # Keep a small suffix in case "Code=" is split across chunks.
            return events, buffer[-32:] if len(buffer) > 32 else buffer

        start = cursor + start_match.start()

        next_code_match = re.search(r"(?m)^Code=", buffer[start + 5 :])
        next_code = (
            start + 5 + next_code_match.start()
            if next_code_match is not None
            else None
        )

        boundary_match = re.search(
            r"\r?\n--[^\r\n]+(?:\r?\n|$)",
            buffer[start:],
        )
        boundary = (
            start + boundary_match.start()
            if boundary_match is not None
            else None
        )

        ends = [
            position
            for position in (next_code, boundary)
            if position is not None and position > start
        ]
        if not ends:
            # The last event block is still arriving.
            tail = buffer[start:]
            if len(tail) > 65536:
                tail = tail[-16384:]
            return events, tail

        end = min(ends)
        event = _parse_cgi_event(buffer[start:end].strip())
        if event is not None:
            events.append(event)

        cursor = end
        if cursor >= len(buffer):
            return events, ""


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
    """Track RP7 events using native camera push plus fallbacks."""

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
        self.stream_status = "polling"
        self.cgi_status = "stopped"
        self.subscribe_status = "stopped"
        self._cgi_task: asyncio.Task[None] | None = None
        self._subscribe_task: asyncio.Task[None] | None = None

        # Only a real event can make a push source authoritative.
        self._push_canonicals: set[str] = set()

        self._onvif_unsub: Callable[[], None] | None = None
        self.onvif_sources: dict[str, list[str]] = {
            "VideoMotion": [],
            "SmartMotionHuman": [],
            "VideoBlind": [],
        }

        self._pulse_clear_tasks: dict[str, asyncio.Task[None]] = {}
        self._live_states: dict[str, bool] = {
            "VideoMotion": False,
            "SmartMotionHuman": False,
            "VideoBlind": False,
        }
        self.transport_probe = TendaTransportProbe(
            client, self._notify_transport_probe_update
        )

    @callback
    def _notify_transport_probe_update(self) -> None:
        """Update the existing diagnostic entity without altering event states."""
        self.async_set_updated_data(dict(self._live_states))

    def _refresh_stream_status(self) -> None:
        if self.cgi_status == "streaming":
            self.stream_status = "cgi_streaming"
        elif self.subscribe_status == "streaming":
            self.stream_status = "subscribe_streaming"
        elif self.cgi_status == "open_no_events":
            self.stream_status = "cgi_open_no_events"
        elif self.subscribe_status == "open_no_events":
            self.stream_status = "subscribe_open_no_events"
        else:
            self.stream_status = "polling"

    async def async_attach(self) -> None:
        """Activate RPC2 event manager for the current login."""
        data = await self.client.async_rpc(
            "eventManager.attach",
            {"codes": ["All"]},
        )
        params = data.get("params") or {}
        self.attach_sid = params.get("SID")
        self._attached = True
        self._attached_generation = self.client.auth_generation
        self.last_raw["eventManager.attach"] = data

    async def async_start_listener(self) -> None:
        """Start every non-destructive local event transport."""
        self.transport_probe.start(self.hass)
        self._async_start_onvif_mirror()

        if self._cgi_task is None or self._cgi_task.done():
            self._cgi_task = self.hass.async_create_task(
                self._async_cgi_event_listener(),
                f"{DOMAIN} eventManager.cgi",
            )

        if self._subscribe_task is None or self._subscribe_task.done():
            self._subscribe_task = self.hass.async_create_task(
                self._async_subscribe_event_listener(),
                f"{DOMAIN} SubscribeNotify",
            )

    def _classify_onvif_entity(self, label: str) -> str | None:
        value = label.lower()
        if any(word in value for word in ("human", "person", "pedestrian")):
            return "SmartMotionHuman"
        if any(word in value for word in ("tamper", "blind", "cover")):
            return "VideoBlind"
        if "motion" in value:
            return "VideoMotion"
        return None

    def _sync_onvif_state(self, canonical: str) -> None:
        entity_ids = self.onvif_sources.get(canonical) or []
        states = [self.hass.states.get(entity_id) for entity_id in entity_ids]
        known = [
            state.state
            for state in states
            if state is not None and state.state in {STATE_ON, STATE_OFF}
        ]
        if not known:
            return

        self._set_event_state(
            canonical,
            STATE_ON in known,
            pulse=False,
        )

    def _async_start_onvif_mirror(self) -> None:
        if self._onvif_unsub is not None:
            return

        registry = er.async_get(self.hass)
        found: list[str] = []

        for config_entry in self.hass.config_entries.async_entries("onvif"):
            if str(config_entry.data.get(CONF_HOST, "")).strip() != self.client.host:
                continue

            for entity_entry in er.async_entries_for_config_entry(
                registry,
                config_entry.entry_id,
            ):
                if not entity_entry.entity_id.startswith("binary_sensor."):
                    continue

                label = " ".join(
                    str(part)
                    for part in (
                        entity_entry.entity_id,
                        entity_entry.name,
                        entity_entry.original_name,
                        entity_entry.translation_key,
                        entity_entry.unique_id,
                    )
                    if part
                )
                canonical = self._classify_onvif_entity(label)
                if canonical is None:
                    continue

                if entity_entry.entity_id not in self.onvif_sources[canonical]:
                    self.onvif_sources[canonical].append(entity_entry.entity_id)
                found.append(entity_entry.entity_id)

        if not found:
            self.last_raw["onvif_mirror"] = {
                "status": "no matching ONVIF event entities",
            }
            return

        for canonical in self.onvif_sources:
            self._sync_onvif_state(canonical)

        @callback
        def _on_onvif_state_change(event) -> None:
            new_state = event.data.get("new_state")
            if new_state is None:
                return

            for canonical, entity_ids in self.onvif_sources.items():
                if new_state.entity_id in entity_ids:
                    self._sync_onvif_state(canonical)
                    break

        self._onvif_unsub = async_track_state_change_event(
            self.hass,
            found,
            _on_onvif_state_change,
        )
        self.last_raw["onvif_mirror"] = {
            "status": "listening",
            "sources": {
                key: list(value)
                for key, value in self.onvif_sources.items()
                if value
            },
        }

    async def async_stop_listener(self) -> None:
        await self.transport_probe.stop()
        for task_name in ("_cgi_task", "_subscribe_task"):
            task = getattr(self, task_name)
            if task is None:
                continue
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            setattr(self, task_name, None)

        if self._onvif_unsub is not None:
            self._onvif_unsub()
            self._onvif_unsub = None

        for task in self._pulse_clear_tasks.values():
            task.cancel()
        self._pulse_clear_tasks.clear()

        self.cgi_status = "stopped"
        self.subscribe_status = "stopped"
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

    def _handle_event(
        self,
        event: dict[str, Any],
        *,
        transport: str,
    ) -> None:
        code = str(event.get("Code") or event.get("code") or "")
        action = str(
            event.get("Action")
            or event.get("action")
            or "Pulse"
        )
        data = event.get("Data", event.get("data"))

        if not code:
            return

        self.discovered_event_codes.add(code)
        self.last_raw[f"{transport}:{code}"] = event
        self.last_raw["last_event_transport"] = transport

        action_lower = action.lower()
        active = action_lower != "stop"
        pulse = action_lower == "pulse"

        canonicals: set[str] = set()
        if code in MOTION_CODES:
            canonicals.add("VideoMotion")
        if code in PERSON_CODES or _contains_human(data):
            canonicals.add("SmartMotionHuman")
        if code in TAMPER_CODES:
            canonicals.add("VideoBlind")

        for canonical in canonicals:
            self._push_canonicals.add(canonical)
            self._set_event_state(canonical, active, pulse=pulse)

    def _handle_notification(self, message: dict[str, Any]) -> None:
        if message.get("method") != "client.notifyEventStream":
            return

        params = message.get("params") or {}
        event_list = params.get("eventList") or []
        if not isinstance(event_list, list):
            return

        self.subscribe_status = "streaming"
        self._refresh_stream_status()
        self.last_raw["last_notify"] = message

        for event in event_list:
            if isinstance(event, dict):
                self._handle_event(event, transport="subscribe")

    async def _async_cgi_event_listener(self) -> None:
        """Consume the native camera multipart eventManager.cgi stream."""
        retry_delay = 2.0

        while True:
            response = None
            try:
                response = await self.client.async_open_cgi_event_stream()
                self.cgi_status = "open_no_events"
                self._refresh_stream_status()
                self.last_raw["eventManager.cgi"] = {
                    "status": response.status,
                    "content_type": response.headers.get("Content-Type"),
                }
                retry_delay = 2.0
                buffer = ""

                async for chunk in response.content.iter_any():
                    if not chunk:
                        continue

                    buffer += chunk.decode("utf-8", errors="ignore")
                    events, buffer = _extract_cgi_events(buffer)

                    for event in events:
                        self.cgi_status = "streaming"
                        self._refresh_stream_status()
                        self._handle_event(event, transport="cgi")

                if self.cgi_status != "streaming":
                    self.cgi_status = "closed_no_events"
                else:
                    self.cgi_status = "disconnected"
                self._refresh_stream_status()

            except asyncio.CancelledError:
                raise
            except (
                TendaRpcAuthError,
                TendaRpcConnectionError,
                OSError,
            ) as err:
                self.cgi_status = "error"
                self._refresh_stream_status()
                self.last_raw["eventManager.cgi"] = {
                    "error": str(err),
                }
                _LOGGER.debug(
                    "RP7 eventManager.cgi unavailable: %s",
                    err,
                )
            finally:
                if response is not None:
                    response.close()

            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30.0)

    async def _async_subscribe_event_listener(self) -> None:
        """Keep the OEM SubscribeNotify experiment as a secondary transport."""
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
                self.subscribe_status = "open_no_events"
                self._refresh_stream_status()
                retry_delay = 2.0
                buffer = ""

                async for chunk in response.content.iter_any():
                    if not chunk:
                        continue

                    buffer += chunk.decode("utf-8", errors="ignore")
                    messages, buffer = _extract_json_objects(buffer)
                    for message in messages:
                        self._handle_notification(message)

                if self.subscribe_status != "streaming":
                    self.subscribe_status = "closed_no_events"
                else:
                    self.subscribe_status = "disconnected"
                self._refresh_stream_status()

            except asyncio.CancelledError:
                raise
            except (
                TendaRpcAuthError,
                TendaRpcConnectionError,
                TendaRpcResponseError,
                OSError,
            ) as err:
                self.subscribe_status = "error"
                self._refresh_stream_status()
                self.last_raw["SubscribeNotify"] = {
                    "error": str(err),
                }
            finally:
                if response is not None:
                    response.close()

            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30.0)

    async def _async_event_active(self, code: str) -> bool | None:
        """Read one RPC2 event-index snapshot."""
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

        self.unsupported_codes.discard(code)
        self.supported_codes.add(code)
        self.last_raw[code] = data

        params = data.get("params") or {}
        indexes = params.get("indexes")
        if indexes is None:
            indexes = []
        if not isinstance(indexes, list):
            return None

        active = bool(indexes)
        if active:
            self.discovered_event_codes.add(code)
        return active

    async def _async_update_data(self) -> dict[str, bool | None]:
        """Merge proven push events, ONVIF and RPC2 polling."""
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

            polled_by_code: dict[str, bool | None] = {}
            for code in POLL_CODE_MAP:
                polled_by_code[code] = await self._async_event_active(code)

            self.last_raw["event_index_values"] = polled_by_code

            collapsed: dict[str, bool | None] = {
                canonical: None for canonical in EVENT_CODES
            }
            for code, canonical in POLL_CODE_MAP.items():
                value = polled_by_code.get(code)
                if value is True:
                    collapsed[canonical] = True
                elif value is False and collapsed[canonical] is None:
                    collapsed[canonical] = False

            for canonical, value in collapsed.items():
                if value is None:
                    continue

                if canonical in self._push_canonicals:
                    continue
                if self.onvif_sources.get(canonical):
                    continue

                self._live_states[canonical] = value

            return dict(self._live_states)

        except (
            TendaRpcAuthError,
            TendaRpcConnectionError,
            TendaRpcResponseError,
        ) as err:
            self._attached = False
            self.last_raw["poll_error"] = {"error": str(err)}
            return dict(self._live_states)
