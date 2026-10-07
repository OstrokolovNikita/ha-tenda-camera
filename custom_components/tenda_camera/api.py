from __future__ import annotations

import asyncio
import json
import ssl
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


def _legacy_unverified_ssl_context() -> ssl.SSLContext:
    """Build a permissive TLS context for older embedded camera web servers."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    # Some embedded servers require older TLS/cipher compatibility. This is
    # only used when the user has explicitly disabled certificate validation.
    if hasattr(ssl, "TLSVersion"):
        try:
            context.minimum_version = ssl.TLSVersion.TLSv1
        except (ValueError, ssl.SSLError):
            pass

    try:
        context.set_ciphers("DEFAULT:@SECLEVEL=0")
    except ssl.SSLError:
        pass

    legacy_option = getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0)
    if legacy_option:
        context.options |= legacy_option

    return context


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
        self._ssl = None if verify_ssl else _legacy_unverified_ssl_context()

    @property
    def base_url(self) -> str:
        """Return base camera URL."""
        return f"https://{self._host}:{self._port}"

    @property
    def origin(self) -> str:
        """Return browser-style Origin used by the camera web UI."""
        if self._port == 443:
            return f"https://{self._host}"
        return self.base_url

    @staticmethod
    def _connection_detail(err: BaseException) -> str:
        """Turn a transport exception into a useful user-visible diagnostic."""
        if isinstance(err, asyncio.TimeoutError):
            return "timeout while waiting for the camera"

        if isinstance(err, aiohttp.ClientConnectorCertificateError):
            return f"TLS certificate error: {err.certificate_error}"

        if isinstance(err, aiohttp.ClientConnectorSSLError):
            return f"TLS handshake error: {err.os_error or err}"

        if isinstance(err, aiohttp.ClientConnectorError):
            os_error = err.os_error
            if os_error is not None:
                return (
                    f"TCP connection failed to {err.host}:{err.port}: "
                    f"{os_error.__class__.__name__}: {os_error}"
                )
            return f"TCP connection failed to {err.host}:{err.port}: {err}"

        if isinstance(err, aiohttp.ServerDisconnectedError):
            return f"camera closed the connection: {err}"

        if isinstance(err, aiohttp.ClientError):
            return f"HTTP client error: {err.__class__.__name__}: {err}"

        return f"{err.__class__.__name__}: {err}"

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

        # Match the request shape captured from the RP7 V2.0 web interface.
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": self.origin,
            "Referer": f"{self.origin}/",
            "Connection": "close",
            "User-Agent": "Mozilla/5.0 HomeAssistant TendaCamera/0.1",
        }

        try:
            async with self._session.post(
                f"{self.base_url}{RPC_PATH}",
                data=json.dumps(payload, separators=(",", ":")),
                headers=headers,
                ssl=self._ssl,
                timeout=self._timeout,
            ) as response:
                body = await response.text()

                if response.status != 200:
                    raise TendaRpcConnectionError(
                        f"HTTP {response.status} {response.reason}; "
                        f"body={body[:300]!r}"
                    )

                try:
                    data = json.loads(body)
                except ValueError as err:
                    raise TendaRpcConnectionError(
                        "camera answered but response is not JSON; "
                        f"content-type={response.headers.get('Content-Type')!r}; "
                        f"body={body[:300]!r}"
                    ) from err

        except TendaRpcConnectionError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, ssl.SSLError) as err:
            raise TendaRpcConnectionError(self._connection_detail(err)) from err

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
