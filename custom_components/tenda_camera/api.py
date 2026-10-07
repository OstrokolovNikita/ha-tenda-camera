from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import RPC_PATH


class TendaRpcError(Exception):
    """Base exception for the Tenda local RPC API."""


class TendaRpcConnectionError(TendaRpcError):
    """Raised when the camera cannot be reached."""


class TendaRpcResponseError(TendaRpcError):
    """Raised when the camera rejects an RPC request."""

    def __init__(
        self,
        method: str,
        code: int | None = None,
        message: str | None = None,
    ) -> None:
        self.method = method
        self.code = code
        self.message = message
        details = f"RPC method {method!r} failed"
        if code is not None:
            details += f" (code {code})"
        if message:
            details += f": {message}"
        super().__init__(details)


class TendaRpcClient:
    """Small async client for the local Tenda /RPC2 endpoint."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int = 443,
        verify_ssl: bool = False,
        timeout: float = 10.0,
    ) -> None:
        self._session = session
        self._host = host.strip()
        self._port = port
        self._verify_ssl = verify_ssl
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    @property
    def base_url(self) -> str:
        """Return base camera URL."""
        return f"https://{self._host}:{self._port}"

    async def async_rpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call one RPC method and return the decoded response."""
        payload: dict[str, Any] = {
            "method": method,
            "params": params or {},
        }

        try:
            async with self._session.post(
                f"{self.base_url}{RPC_PATH}",
                json=payload,
                ssl=None if self._verify_ssl else False,
                timeout=self._timeout,
            ) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise TendaRpcConnectionError(str(err)) from err

        if not isinstance(data, dict):
            raise TendaRpcResponseError(method, message="invalid JSON response")

        if data.get("result") is False:
            error = data.get("error") or {}
            raise TendaRpcResponseError(
                method,
                code=error.get("code"),
                message=error.get("message") or str(data.get("params", "")),
            )

        return data

    async def async_get_config(self, name: str) -> Any:
        """Read one config table."""
        data = await self.async_rpc(
            "configManager.getConfig",
            {"name": name},
        )
        params = data.get("params") or {}
        if "table" not in params:
            raise TendaRpcResponseError(
                "configManager.getConfig",
                message=f"missing table for {name}",
            )
        return params["table"]

    async def async_get_product_definition(self) -> dict[str, Any]:
        """Read basic RPC capabilities."""
        data = await self.async_rpc(
            "magicBox.getProductDefinition",
            {"name": "All"},
        )
        params = data.get("params") or {}
        return params if isinstance(params, dict) else {}

    async def async_probe(self) -> dict[str, Any]:
        """Read the minimum data needed to identify a camera."""
        general = await self.async_get_config("General")
        device_name = await self.async_get_config("DeviceName")
        product = await self.async_get_product_definition()
        return {
            "general": general,
            "device_name": device_name,
            "product": product,
        }
