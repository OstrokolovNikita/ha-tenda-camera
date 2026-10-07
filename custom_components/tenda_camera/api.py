from __future__ import annotations

import asyncio
import base64
import json
import ssl
from typing import Any

import aiohttp
from yarl import URL

from .const import RPC_PATH


class TendaRpcError(Exception):
    """Base exception for the Tenda local RPC API."""


class TendaRpcConnectionError(TendaRpcError):
    """Raised when the camera cannot be reached."""


class TendaRpcAuthError(TendaRpcError):
    """Raised when authentication is required or rejected."""


class TendaRpcResponseError(TendaRpcError):
    """Raised when the camera rejects an RPC request."""

    def __init__(
        self,
        method: str,
        code: int | None = None,
        message: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        self.method = method
        self.code = code
        self.message = message
        self.raw = raw
        details = f"RPC method {method!r} failed"
        if code is not None:
            details += f" (code {code})"
        if message:
            details += f": {message}"
        if raw is not None:
            details += (
                "; raw="
                + json.dumps(raw, ensure_ascii=False, separators=(",", ":"))[:500]
            )
        super().__init__(details)


def _legacy_unverified_ssl_context() -> ssl.SSLContext:
    """Build a permissive TLS context for older embedded camera web servers."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

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
    """Async client for the local Tenda /RPC2 endpoint."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int = 443,
        verify_ssl: bool = False,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._session = session
        self._host = host.strip()
        self._port = port
        self._verify_ssl = verify_ssl
        self._username = username
        self._password = password
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._ssl = None if verify_ssl else _legacy_unverified_ssl_context()
        self._login_lock = asyncio.Lock()
        self._auth_generation = 0

    @property
    def auth_generation(self) -> int:
        """Return a counter that changes after every successful login."""
        return self._auth_generation

    @property
    def session_cookie_value(self) -> str | None:
        """Return the authenticated web-session cookie value if present."""
        cookies = self._session.cookie_jar.filter_cookies(URL(self.base_url))
        for name in ("SESSION", "session", "Session", "JSESSIONID"):
            morsel = cookies.get(name)
            if morsel is not None:
                return morsel.value

        # Some OEM firmwares use a non-standard cookie name. If there is
        # exactly one cookie after login, it is still useful as the session id.
        values = list(cookies.values())
        if len(values) == 1:
            return values[0].value
        return None

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

    @staticmethod
    def _is_auth_required(data: dict[str, Any]) -> bool:
        return (
            data.get("result") is False
            and data.get("errCode") == 401
            and data.get("page") == "login"
        )

    async def _async_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        login_page: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "method": method,
            "params": params or {},
        }

        referer = "/login.html" if login_page else "/"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": self.origin,
            "Referer": f"{self.origin}{referer}",
            "Connection": "keep-alive",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/154.0.0.0 Safari/537.36"
            ),
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
            raise TendaRpcResponseError(
                method,
                message="invalid JSON response",
                raw={"response": data},
            )

        return data

    async def async_login(self) -> None:
        """Authenticate exactly as the RP7 V2.0 web UI does."""
        if self._username is None or self._password is None:
            raise TendaRpcAuthError("username/password are required")

        encoded_password = base64.b64encode(
            self._password.encode("utf-8")
        ).decode("ascii")

        data = await self._async_request(
            "global.login",
            {
                "username": self._username,
                "password": encoded_password,
            },
            login_page=True,
        )

        if data.get("result") is not True:
            raise TendaRpcAuthError("camera rejected username/password")

        self._auth_generation += 1

    async def async_rpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call one RPC method, re-authenticating once on session expiry."""
        data = await self._async_request(method, params)

        if self._is_auth_required(data):
            async with self._login_lock:
                await self.async_login()
                data = await self._async_request(method, params)

        if self._is_auth_required(data):
            raise TendaRpcAuthError(
                "camera still requires login after authentication"
            )

        if data.get("result") is False:
            error = data.get("error") or {}
            raise TendaRpcResponseError(
                method,
                code=error.get("code"),
                message=error.get("message"),
                raw=data,
            )

        return data

    async def async_open_event_stream(self) -> aiohttp.ClientResponse:
        """Open the Dahua-style SubscribeNotify event stream if RP7 exposes it."""
        session_id = self.session_cookie_value
        params = {"sessionId": session_id} if session_id else None
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/json,*/*",
            "Referer": f"{self.origin}/",
            "Connection": "keep-alive",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/154.0.0.0 Safari/537.36"
            ),
        }

        try:
            response = await self._session.get(
                f"{self.base_url}/SubscribeNotify.cgi",
                params=params,
                headers=headers,
                ssl=self._ssl,
                timeout=aiohttp.ClientTimeout(
                    total=None,
                    connect=10,
                    sock_connect=10,
                    sock_read=None,
                ),
            )
        except (aiohttp.ClientError, asyncio.TimeoutError, ssl.SSLError) as err:
            raise TendaRpcConnectionError(self._connection_detail(err)) from err

        if response.status != 200:
            body = await response.text()
            response.release()
            raise TendaRpcConnectionError(
                f"SubscribeNotify HTTP {response.status} {response.reason}; "
                f"body={body[:300]!r}"
            )
        return response

    async def async_get_config(self, name: str) -> Any:
        """Read one config table."""
        try:
            data = await self.async_rpc(
                "configManager.getConfig",
                {"name": name},
            )
        except TendaRpcResponseError as err:
            raise TendaRpcResponseError(
                f"configManager.getConfig[{name}]",
                code=err.code,
                message=err.message,
                raw=err.raw,
            ) from err

        params = data.get("params") or {}
        if "table" not in params:
            raise TendaRpcResponseError(
                f"configManager.getConfig[{name}]",
                message="response has no params.table",
                raw=data,
            )
        return params["table"]

    async def async_set_config(self, name: str, table: Any) -> None:
        """Write a complete config table back to the camera."""
        await self.async_rpc(
            "configManager.setConfig",
            {
                "name": name,
                "table": table,
            },
        )

    async def async_set_config_value(
        self,
        name: str,
        key: str,
        value: Any,
    ) -> None:
        """Read-modify-write one value while preserving the rest of the table."""
        table = await self.async_get_config(name)

        if isinstance(table, dict):
            updated = dict(table)
            updated[key] = value
        elif (
            isinstance(table, list)
            and table
            and isinstance(table[0], dict)
        ):
            updated = [dict(item) if isinstance(item, dict) else item for item in table]
            updated[0][key] = value
        else:
            raise TendaRpcResponseError(
                f"configManager.setConfig[{name}]",
                message=f"unsupported table shape for key {key!r}",
                raw={"table": table},
            )

        await self.async_set_config(name, updated)

    async def async_get_product_definition(self) -> dict[str, Any]:
        """Read basic RPC capabilities."""
        data = await self.async_rpc(
            "magicBox.getProductDefinition",
            {"name": "All"},
        )
        params = data.get("params") or {}
        return params if isinstance(params, dict) else {}

    async def async_probe(self) -> dict[str, Any]:
        """Authenticate and read the minimum data needed to identify a camera."""
        await self.async_login()
        general = await self.async_get_config("General")
        device_name = await self.async_get_config("DeviceName")
        product = await self.async_get_product_definition()
        return {
            "general": general,
            "device_name": device_name,
            "product": product,
        }
