from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import CONFIG_BLIND, CONFIG_MOTION, DOMAIN

SERVICE_PTZ = "ptz"
SERVICE_SET_FEATURE = "set_feature"

FEATURE_MAP: dict[str, tuple[str, str]] = {
    "motion": (CONFIG_MOTION, "Enable"),
    "human_detection": (CONFIG_MOTION, "HumanDetectFliter"),
    "human_tracking": (CONFIG_MOTION, "HumanTrack"),
    "tamper_detection": (CONFIG_BLIND, "Enable"),
}

DIRECTION_MAP: dict[str, tuple[str, str]] = {
    "up": ("tilt", "UP"),
    "down": ("tilt", "DOWN"),
    "left": ("pan", "LEFT"),
    "right": ("pan", "RIGHT"),
}


def _entry_from_entity_id(
    hass: HomeAssistant,
    entity_id: str,
) -> Any:
    registry = er.async_get(hass)
    entity_entry = registry.async_get(entity_id)

    if entity_entry is None or entity_entry.config_entry_id is None:
        raise HomeAssistantError(f"Unknown Tenda entity: {entity_id}")

    entry = hass.config_entries.async_get_entry(entity_entry.config_entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise HomeAssistantError(f"Entity does not belong to {DOMAIN}: {entity_id}")

    return entry


def _find_matching_onvif_camera(
    hass: HomeAssistant,
    host: str,
) -> str | None:
    registry = er.async_get(hass)

    for config_entry in hass.config_entries.async_entries("onvif"):
        if str(config_entry.data.get(CONF_HOST, "")).strip() != host:
            continue

        for entity_entry in er.async_entries_for_config_entry(
            registry,
            config_entry.entry_id,
        ):
            if entity_entry.entity_id.startswith("camera."):
                return entity_entry.entity_id

    return None


async def async_ptz_service(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Move the camera using the matching ONVIF entity."""
    entity_id = str(call.data.get("entity_id", ""))
    action = str(call.data.get("action", "pulse")).lower()
    direction = str(call.data.get("direction", "")).lower()

    entry = _entry_from_entity_id(hass, entity_id)
    host = str(entry.data[CONF_HOST]).strip()
    onvif_camera = _find_matching_onvif_camera(hass, host)

    if onvif_camera is None:
        raise HomeAssistantError(
            "No ONVIF camera for the same host was found"
        )

    if action == "stop":
        await hass.services.async_call(
            "onvif",
            "ptz",
            {
                "entity_id": onvif_camera,
                "move_mode": "Stop",
            },
            blocking=True,
        )
        return

    if direction not in DIRECTION_MAP:
        raise HomeAssistantError(
            "direction must be one of: up, down, left, right"
        )

    axis, onvif_direction = DIRECTION_MAP[direction]
    speed = float(call.data.get("speed", 0.35))

    if action == "start":
        duration = float(call.data.get("duration", 10.0))
        blocking = False
    else:
        duration = float(call.data.get("duration", 0.18))
        blocking = True

    data: dict[str, Any] = {
        "entity_id": onvif_camera,
        "move_mode": "ContinuousMove",
        "continuous_duration": duration,
        "speed": max(0.05, min(speed, 1.0)),
        axis: onvif_direction,
    }

    await hass.services.async_call(
        "onvif",
        "ptz",
        data,
        blocking=blocking,
    )


async def async_set_feature_service(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Change one RP7 feature from the camera card."""
    entity_id = str(call.data.get("entity_id", ""))
    feature = str(call.data.get("feature", ""))
    enabled = bool(call.data.get("enabled", False))

    if feature not in FEATURE_MAP:
        raise HomeAssistantError(
            "feature must be one of: " + ", ".join(FEATURE_MAP)
        )

    entry = _entry_from_entity_id(hass, entity_id)
    config_name, key = FEATURE_MAP[feature]
    await entry.runtime_data.coordinator.async_set_boolean(
        config_name,
        key,
        enabled,
    )


def async_register_services(hass: HomeAssistant) -> None:
    """Register Tenda Camera services once."""
    if not hass.services.has_service(DOMAIN, SERVICE_PTZ):
        hass.services.async_register(
            DOMAIN,
            SERVICE_PTZ,
            lambda call: async_ptz_service(hass, call),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_FEATURE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_FEATURE,
            lambda call: async_set_feature_service(hass, call),
        )
