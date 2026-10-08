from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import TendaConfigEntry

TO_REDACT = {
    "host",
    CONF_PASSWORD,
    "machineSN",
    "uuid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: TendaConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a Tenda Camera config entry."""
    coordinator = entry.runtime_data.coordinator
    event_coordinator = entry.runtime_data.event_coordinator

    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "device_info": async_redact_data(
            coordinator.device_info,
            TO_REDACT,
        ),
        "coordinator_data": coordinator.data,
        "event_data": event_coordinator.data,
        "event_attach_sid": event_coordinator.attach_sid,
        "event_stream_status": event_coordinator.stream_status,
        "event_transport_probe": dict(event_coordinator.transport_probe.details),
        "event_cgi_status": event_coordinator.cgi_status,
        "event_subscribe_status": event_coordinator.subscribe_status,
        "event_discovered_codes": sorted(event_coordinator.discovered_event_codes),
        "event_onvif_sources": {
            key: list(value)
            for key, value in event_coordinator.onvif_sources.items()
            if value
        },
        "event_supported_codes": sorted(event_coordinator.supported_codes),
        "event_unsupported_codes": sorted(event_coordinator.unsupported_codes),
        "event_last_raw": async_redact_data(
            event_coordinator.last_raw,
            TO_REDACT,
        ),
    }
