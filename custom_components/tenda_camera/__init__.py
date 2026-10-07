from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aiohttp import CookieJar

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import TendaRpcClient, TendaRpcError
from .const import DOMAIN
from .coordinator import TendaCoordinator
from .event_coordinator import TendaEventCoordinator
from .services import async_register_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.CAMERA,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


FRONTEND_URL = "/tenda-camera"
FRONTEND_MODULE = f"{FRONTEND_URL}/tenda-camera-card.js?v=0.5.0"


async def async_setup(
    hass: HomeAssistant,
    config: dict,
) -> bool:
    """Register the bundled Tenda Camera dashboard card and services."""
    frontend_dir = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                url_path=FRONTEND_URL,
                path=str(frontend_dir),
                cache_headers=False,
            )
        ]
    )
    add_extra_js_url(hass, FRONTEND_MODULE)
    async_register_services(hass)
    return True


LEGACY_BINARY_SENSOR_KEYS = (
    "motion_detection_enabled",
    "human_detection_filter_enabled",
    "human_tracking_enabled",
    "blind_detection_enabled",
    "onvif_enabled",
    "rtsp_enabled",
)


@dataclass
class TendaRuntimeData:
    """Runtime data stored on the config entry."""

    client: TendaRpcClient
    coordinator: TendaCoordinator
    event_coordinator: TendaEventCoordinator


type TendaConfigEntry = ConfigEntry[TendaRuntimeData]


def _remove_legacy_binary_sensors(
    hass: HomeAssistant,
    entry: TendaConfigEntry,
    device_info: dict,
) -> None:
    """Remove v0.2.x read-only entities replaced by switches/camera entities."""
    general = device_info.get("general") or {}
    serial = str(
        general.get("machineSN")
        or general.get("uuid")
        or entry.unique_id
        or entry.entry_id
    )

    registry = er.async_get(hass)
    for key in LEGACY_BINARY_SENSOR_KEYS:
        unique_id = f"{serial}_{key}"
        entity_id = registry.async_get_entity_id(
            "binary_sensor",
            DOMAIN,
            unique_id,
        )
        if entity_id:
            registry.async_remove(entity_id)


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

    event_coordinator = TendaEventCoordinator(hass, client, device_info)
    await event_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = TendaRuntimeData(
        client=client,
        coordinator=coordinator,
        event_coordinator=event_coordinator,
    )

    _remove_legacy_binary_sensors(hass, entry, device_info)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: TendaConfigEntry,
) -> bool:
    """Unload a Tenda Camera config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
