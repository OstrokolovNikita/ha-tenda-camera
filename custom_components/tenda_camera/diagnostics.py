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

    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "device_info": async_redact_data(
            coordinator.device_info,
            TO_REDACT,
        ),
        "coordinator_data": coordinator.data,
    }
