from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TendaConfigEntry
from .const import CONF_PORT, DEFAULT_PORT, DOMAIN
from .coordinator import TendaCoordinator


class TendaCameraEntity(CoordinatorEntity[TendaCoordinator]):
    """Base entity for a Tenda camera."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: TendaConfigEntry,
        coordinator: TendaCoordinator,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry

        probe = coordinator.device_info
        general = probe.get("general") or {}
        device_name = probe.get("device_name") or {}

        serial = str(
            general.get("machineSN")
            or general.get("uuid")
            or entry.unique_id
            or entry.entry_id
        )
        self._device_unique_id = serial

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=str(
                device_name.get("machineName")
                or general.get("machineModel")
                or entry.title
            ),
            manufacturer="Tenda",
            model=general.get("machineModel"),
            hw_version=general.get("hardVersion"),
            sw_version=general.get("softVersion"),
            serial_number=general.get("machineSN"),
            configuration_url=(
                f"https://{entry.data[CONF_HOST]}:"
                f"{entry.data.get(CONF_PORT, DEFAULT_PORT)}"
            ),
        )
