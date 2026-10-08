"""Regression tests for private, bounded RP7 event diagnostics."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "tenda_camera"
    / "event_trace.py"
)
spec = importlib.util.spec_from_file_location("rp7_event_trace_test", MODULE_PATH)
assert spec is not None and spec.loader is not None
trace_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace_module)
TendaEventTrace = trace_module.TendaEventTrace


class Config:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, *parts: str) -> str:
        return str(self.root.joinpath(*parts))


class HassStub:
    def __init__(self, root: Path) -> None:
        self.config = Config(root)

    def async_create_task(self, coroutine, name: str):
        return asyncio.create_task(coroutine, name=name)


class TraceJournalTests(unittest.IsolatedAsyncioTestCase):
    async def test_records_survive_reload_and_are_exportable(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            hass = HassStub(Path(folder))
            log = TendaEventTrace(hass, "example-entry")
            log.start(hass)
            log.record("transport_change", ws_root_9002="connected_wss")
            log.record("onvif_state", event_type="VideoMotion", active=True)
            export = await log.async_snapshot()
            await log.stop()

            events = [row["event"] for row in export["records"]]
            self.assertIn("transport_change", events)
            self.assertIn("onvif_state", events)
            self.assertEqual(export["dropped"], 0)
            self.assertIsNone(export["write_error"])

            restarted = TendaEventTrace(hass, "example-entry")
            restarted.start(hass)
            after_restart = await restarted.async_snapshot()
            await restarted.stop()
            self.assertIn(
                "onvif_state",
                [row["event"] for row in after_restart["records"]],
            )

    async def test_truncated_metadata_not_raw_capture(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            hass = HassStub(Path(folder))
            log = TendaEventTrace(hass, "safe-example")
            log.start(hass)
            log.record("transport_change", example="x" * 10000)
            snapshot = await log.async_snapshot()
            await log.stop()
            record = next(
                row for row in snapshot["records"]
                if row["event"] == "transport_change"
            )
            self.assertEqual(len(record["fields"]["example"]), 96)
            self.assertLess(
                snapshot["records"].__sizeof__(), 1000000
            )


if __name__ == "__main__":
    unittest.main()
