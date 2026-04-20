import socket
from types import ModuleType
from typing import TYPE_CHECKING, Any

from ...auth.webbrowser import AuthByWebBrowser as AuthByWebBrowserSync
from .._connection import SnowflakeConnection
from ._by_plugin import AuthByPlugin as AuthByPluginAsync

if TYPE_CHECKING: ...
logger = ...

class AuthByWebBrowser(AuthByPluginAsync, AuthByWebBrowserSync):
    def __init__(
        self,
        application: str,
        webbrowser_pkg: ModuleType | None = ...,
        socket_pkg: type[socket.socket] | None = ...,
        protocol: str | None = ...,
        host: str | None = ...,
        port: str | None = ...,
        **kwargs,
    ) -> None: ...
    async def reset_secrets(self) -> None: ...
    async def prepare(
        self, *, conn: SnowflakeConnection, authenticator: str, service_name: str | None, account: str, user: str, **kwargs: Any
    ) -> None: ...
    async def reauthenticate(self, *, conn: SnowflakeConnection, **kwargs: Any) -> dict[str, bool]: ...
    async def update_body(self, body: dict[Any, Any]) -> None: ...
