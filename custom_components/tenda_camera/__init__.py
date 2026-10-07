from __future__ import annotations

from dataclasses import dataclass

from aiohttp import CookieJar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import TendaRpcClient, TendaRpcError
from .coordinator import TendaCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


@dataclass
class TendaRuntimeData:
    """Runtime data stored on the config entry."""

    client: TendaRpcClient
    coordinator: TendaCoordinator


type TendaConfigEntry = ConfigEntry[TendaRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TendaConfigEntry,
) -> bool:
    """Set up Tenda Camera from a config entry."""
    verify_ssl = bool(entry.data.get("verify_ssl", False))
    session = async_create_clientsession(
        hass,
        verify_ssl=verify_ssl,
        cookie_jar=CookieJar(unsafe=True, quote_cookie=False),
    )
    client = TendaRpcClient(
        session=session,
        **dict(entry.data),
    )

    try:
        device_info = await client.async_probe()
    except TendaRpcError as err:
        raise ConfigEntryNotReady(
            f"Unable to initialize Tenda camera: {err}"
        ) from err

    coordinator = TendaCoordinator(hass, client, device_info)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = TendaRuntimeData(
        client=client,
        coordinator=coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: TendaConfigEntry,
) -> bool:
    """Unload a Tenda Camera config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
