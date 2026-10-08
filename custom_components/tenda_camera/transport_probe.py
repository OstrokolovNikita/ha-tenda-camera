"""Non-destructive, read-only transport discovery for RP7 V2.0.

No protocol commands or credentials are sent. A TCP connect only proves that
the port is reachable. A WebSocket handshake to "/" is a *candidate* URL:
rejection does not imply the camera lacks WebSocket event support.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime, timezone
import json
import re
from typing import Any

import aiohttp

from .api import TendaRpcClient


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_ws_summary(message: aiohttp.WSMessage) -> dict[str, Any]:
    """Expose message kind/size and known event fields, never raw payloads."""
    if message.type is aiohttp.WSMsgType.BINARY:
        return {"kind": "binary", "size": len(message.data)}

    payload = message.data
    if message.type is not aiohttp.WSMsgType.TEXT or not isinstance(payload, str):
        return {"kind": str(message.type), "size": 0}

    result: dict[str, Any] = {"kind": "text", "size": len(payload)}
    try:
        decoded = json.loads(payload)
    except (ValueError, TypeError):
        return result
    if not isinstance(decoded, dict):
        return result

    # Keys are useful to recognize event envelopes, but never expose values of
    # arbitrary fields (they might contain IDs, session cookies or tokens).
    result["keys"] = sorted(str(key)[:40] for key in decoded)[:15]
    for field in ("method", "Code", "code", "Action", "action"):
        value = decoded.get(field)
        if (
            isinstance(value, str)
            and re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", value) is not None
        ):
            result[field] = value
    return result


def _error_label(error: BaseException) -> str:
    """Avoid storing exception messages (may include URLs or credentials)."""
    if isinstance(error, aiohttp.WSServerHandshakeError):
        return f"HTTP_{error.status}"
    return error.__class__.__name__


class TendaTransportProbe:
    """Observational probes for 9002/8000 without affecting live entities."""

    def __init__(
        self,
        client: TendaRpcClient,
        on_change: Callable[[], None],
    ) -> None:
        self.client = client
        self._on_change = on_change
        self._task: asyncio.Task[None] | None = None
        self.details: dict[str, Any] = {
            "tcp_9002": "pending",
            "tcp_8000": "pending",
            "ws_root_9002": "pending",
            "ws_messages": 0,
            "ws_connection_count": 0,
            "ws_connected_utc": None,
            "ws_close_code": None,
            "ws_close_frame_type": None,
            "ws_lifetime_ms": None,
            "ws_last_message": None,
            "ws_last_message_utc": None,
            "last_probe_utc": None,
        }

    def start(self, hass: Any) -> None:
        if self._task is None or self._task.done():
            self._task = hass.async_create_task(
                self._run(), "tenda_camera transport discovery"
            )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    def _set(self, **changes: Any) -> None:
        if all(self.details.get(key) == value for key, value in changes.items()):
            return
        self.details.update(changes)
        self._on_change()

    async def _check_tcp(self, port: int) -> bool:
        writer: asyncio.StreamWriter | None = None
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(self.client.host, port),
                timeout=4,
            )
            self._set(**{f"tcp_{port}": "open"})
            return True
        except (OSError, asyncio.TimeoutError) as err:
            self._set(**{f"tcp_{port}": _error_label(err)})
            return False
        finally:
            if writer is not None:
                writer.close()
                with suppress(OSError, ConnectionError):
                    await writer.wait_closed()

    async def _observe_websocket(self) -> None:
        # A failed handshake to "/" is only a result for this one URL.
        failures: list[str] = []
        # Deliberately use a separate cookie-less session: do not reuse the
        # authenticated RPC2 session or accidentally send its cookies.
        async with aiohttp.ClientSession(
            cookie_jar=aiohttp.DummyCookieJar(),
            trust_env=False,
        ) as session:
            for scheme in ("ws", "wss"):
                url = f"{scheme}://{self.client.host}:9002/"
                websocket: aiohttp.ClientWebSocketResponse | None = None
                try:
                    websocket = await asyncio.wait_for(
                        session.ws_connect(
                            url,
                            ssl=self.client.ssl_context if scheme == "wss" else None,
                            heartbeat=20,
                        ),
                        timeout=5,
                    )
                    connected_at = asyncio.get_running_loop().time()
                    self._set(
                        ws_root_9002=f"connected_{scheme}",
                        ws_connection_count=self.details["ws_connection_count"] + 1,
                        ws_connected_utc=_timestamp(),
                        ws_close_code=None,
                        ws_close_frame_type=None,
                        ws_lifetime_ms=None,
                    )
                    async with websocket:
                        until = asyncio.get_running_loop().time() + 90
                        while asyncio.get_running_loop().time() < until:
                            try:
                                message = await asyncio.wait_for(
                                    websocket.receive(), timeout=10
                                )
                            except asyncio.TimeoutError:
                                continue

                            if message.type in (
                                aiohttp.WSMsgType.TEXT,
                                aiohttp.WSMsgType.BINARY,
                            ):
                                self._set(
                                    ws_messages=self.details["ws_messages"] + 1,
                                    ws_last_message=_safe_ws_summary(message),
                                    ws_last_message_utc=_timestamp(),
                                )
                            elif message.type in (
                                aiohttp.WSMsgType.CLOSED,
                                aiohttp.WSMsgType.CLOSE,
                                aiohttp.WSMsgType.CLOSING,
                                aiohttp.WSMsgType.ERROR,
                            ):
                                code = websocket.close_code
                                if message.type is aiohttp.WSMsgType.CLOSE:
                                    # Received CLOSE frame contains a numeric status.
                                    code = message.data if isinstance(message.data, int) else code
                                self._set(
                                    ws_root_9002=f"closed_{scheme}",
                                    ws_close_code=code,
                                    ws_close_frame_type=message.type.name,
                                    ws_lifetime_ms=round(
                                        (asyncio.get_running_loop().time() - connected_at) * 1000
                                    ),
                                )
                                return
                    self._set(
                        ws_root_9002=f"observed_90s_{scheme}",
                        ws_close_code=websocket.close_code,
                        ws_lifetime_ms=round(
                            (asyncio.get_running_loop().time() - connected_at) * 1000
                        ),
                    )
                    return
                except asyncio.CancelledError:
                    raise
                except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as err:
                    failures.append(f"{scheme}:{_error_label(err)}")
                finally:
                    if websocket is not None and not websocket.closed:
                        await websocket.close()

        self._set(ws_root_9002=" | ".join(failures))

    async def _run(self) -> None:
        while True:
            self._set(last_probe_utc=_timestamp())
            ws_open = await self._check_tcp(9002)
            await self._check_tcp(8000)
            if ws_open:
                await self._observe_websocket()
            else:
                self._set(ws_root_9002="skipped_tcp_9002_not_open")
            await asyncio.sleep(60)
