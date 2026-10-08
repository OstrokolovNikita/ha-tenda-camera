"""Bounded, sanitized, persistent RP7 event-transport trace.

The trace stores only developer-chosen diagnostic fields. Never pass original
RPC/WS payloads, exception messages, passwords or session identifiers here.
Files live in Home Assistant's private .storage directory and are accessible
through the standard downloadable integration diagnostics.
"""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 512 * 1024
MAX_EXPORT_RECORDS = 800
QUEUE_SIZE = 2048


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _sanitize_value(value: Any) -> Any:
    """Retain only bounded, explicitly structured diagnostic metadata."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:96]
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value[:24]]
    if isinstance(value, dict):
        return {
            str(key)[:40]: _sanitize_value(item)
            for key, item in list(value.items())[:24]
        }
    return type(value).__name__


class TendaEventTrace:
    """Serialize observations through a single async worker to bounded JSONL."""

    def __init__(self, hass: Any, entry_id: str) -> None:
        self._path = Path(
            hass.config.path(
                ".storage", f"tenda_camera_trace_{entry_id}.jsonl"
            )
        )
        self._queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(
            maxsize=QUEUE_SIZE
        )
        self._task: asyncio.Task[None] | None = None
        self._recent: deque[dict[str, Any]] = deque(maxlen=100)
        self.dropped = 0
        self.recorded_since_restart = 0
        self.last_record_utc: str | None = None
        self.write_error: str | None = None
        self.record("trace_initialized", mode="read_only", version="0.8.3b4")

    def record(self, event: str, **fields: Any) -> None:
        """Append one trusted metadata-only observation, never source payloads."""
        row = {
            "at_utc": _utc_now(),
            "event": str(event)[:48],
            "fields": {
                key: _sanitize_value(value)
                for key, value in fields.items()
            },
        }
        self._recent.append(row)
        self.recorded_since_restart += 1
        self.last_record_utc = row["at_utc"]
        try:
            self._queue.put_nowait(row)
        except asyncio.QueueFull:
            self.dropped += 1

    @property
    def status(self) -> dict[str, Any]:
        return {
            "recorded_since_restart": self.recorded_since_restart,
            "last_record_utc": self.last_record_utc,
            "dropped": self.dropped,
            "write_error": self.write_error,
            "stored_private": True,
            "download_via": "HA integration diagnostics",
        }

    def start(self, hass: Any) -> None:
        if self._task is None or self._task.done():
            self._task = hass.async_create_task(
                self._writer(), "tenda_camera sanitized event journal"
            )

    async def stop(self) -> None:
        if self._task is not None:
            await self._queue.put(None)
            await self._task
            self._task = None

    def _append_batch(self, rows: list[dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lines = "".join(
            json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n"
            for row in rows
        )
        # A two-file rotating journal is capped at approximately 1 MiB.
        if (
            self._path.exists()
            and self._path.stat().st_size + len(lines.encode("utf-8"))
            > MAX_FILE_BYTES
        ):
            backup = self._path.with_suffix(".jsonl.1")
            self._path.replace(backup)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(lines)

    async def _writer(self) -> None:
        while True:
            item = await self._queue.get()
            stop = item is None
            batch: list[dict[str, Any]] = []
            count = 1

            if item is not None:
                batch.append(item)
                while len(batch) < 50:
                    try:
                        next_item = self._queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    count += 1
                    if next_item is None:
                        stop = True
                        break
                    batch.append(next_item)

            if batch:
                try:
                    await asyncio.to_thread(self._append_batch, batch)
                    self.write_error = None
                except OSError as err:
                    self.write_error = type(err).__name__

            for _ in range(count):
                self._queue.task_done()
            if stop:
                return

    def _read_snapshot(self) -> list[dict[str, Any]]:
        rows: deque[dict[str, Any]] = deque(maxlen=MAX_EXPORT_RECORDS)
        for path in (self._path.with_suffix(".jsonl.1"), self._path):
            if not path.exists():
                continue
            try:
                with path.open("r", encoding="utf-8") as file:
                    for line in file:
                        try:
                            value = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(value, dict):
                            rows.append(value)
            except OSError:
                continue
        return list(rows)

    async def async_snapshot(self) -> dict[str, Any]:
        # Drain queued observations before reading the journal for a download.
        try:
            await asyncio.wait_for(self._queue.join(), timeout=5)
        except asyncio.TimeoutError:
            pass
        return {
            "format": "sanitized_jsonl",
            "retained_records": MAX_EXPORT_RECORDS,
            "dropped": self.dropped,
            "write_error": self.write_error,
            "records": await asyncio.to_thread(self._read_snapshot),
            "pending_recent_if_storage_unavailable": (
                list(self._recent) if self.write_error else []
            ),
        }
