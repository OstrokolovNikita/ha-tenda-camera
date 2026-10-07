from __future__ import annotations

import logging
from typing import Any

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    TendaRpcAuthError,
    TendaRpcClient,
    TendaRpcConnectionError,
    TendaRpcError,
)
from .const import (
    CONF_PORT,
    CONF_VERIFY_SSL,
    DEFAULT_PORT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class TendaCameraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tenda Camera."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}
        diagnostic = "не проверено"

        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip()
            port = int(user_input.get(CONF_PORT, DEFAULT_PORT))
            verify_ssl = bool(
                user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
            )
            username = str(user_input[CONF_USERNAME])
            password = str(user_input[CONF_PASSWORD])

            client = TendaRpcClient(
                session=async_get_clientsession(self.hass),
                host=host,
                port=port,
                verify_ssl=verify_ssl,
                username=username,
                password=password,
            )

            try:
                probe = await client.async_probe()
            except TendaRpcAuthError as err:
                diagnostic = str(err)
                errors["base"] = "invalid_auth"
            except TendaRpcConnectionError as err:
                diagnostic = str(err)
                _LOGGER.warning(
                    "Tenda camera connection test failed for %s:%s: %s",
                    host,
                    port,
                    diagnostic,
                )
                errors["base"] = "cannot_connect"
            except TendaRpcError as err:
                diagnostic = str(err)
                _LOGGER.warning(
                    "Tenda camera RPC2 validation failed for %s:%s: %s",
                    host,
                    port,
                    diagnostic,
                )
                errors["base"] = "rpc_error"
            else:
                general = probe.get("general") or {}
                device_name = probe.get("device_name") or {}

                serial = general.get("machineSN")
                uuid = general.get("uuid")
                unique_id = str(serial or uuid or host)

                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_VERIFY_SSL: verify_ssl,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    }
                )

                title = (
                    device_name.get("machineName")
                    or general.get("machineModel")
                    or f"Tenda {host}"
                )

                return self.async_create_entry(
                    title=str(title),
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_VERIFY_SSL: verify_ssl,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_HOST,
                    default=(
                        str(user_input[CONF_HOST]).strip()
                        if user_input and CONF_HOST in user_input
                        else ""
                    ),
                ): str,
                probatio.Required(
                    CONF_USERNAME,
                    default=(
                        str(user_input.get(CONF_USERNAME, "admin"))
                        if user_input
                        else "admin"
                    ),
                ): str,
                probatio.Required(
                    CONF_PASSWORD,
                    default=(
                        str(user_input.get(CONF_PASSWORD, ""))
                        if user_input
                        else ""
                    ),
                ): str,
                probatio.Optional(
                    CONF_PORT,
                    default=(
                        int(user_input.get(CONF_PORT, DEFAULT_PORT))
                        if user_input
                        else DEFAULT_PORT
                    ),
                ): int,
                probatio.Optional(
                    CONF_VERIFY_SSL,
                    default=(
                        bool(user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL))
                        if user_input
                        else DEFAULT_VERIFY_SSL
                    ),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"diagnostic": diagnostic},
        )
