from abc import abstractmethod
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from ...auth import AuthByPlugin as AuthByPluginSync
from .. import SnowflakeConnection

if TYPE_CHECKING: ...
logger = ...

class AuthByPlugin(AuthByPluginSync):
    def __init__(self, timeout: int | None = ..., backoff_generator: Iterator | None = ..., **kwargs) -> None: ...
    @abstractmethod
    async def prepare(
        self,
        *,
        conn: SnowflakeConnection,
        authenticator: str,
        service_name: str | None,
        account: str,
        user: str,
        password: str | None,
        **kwargs: Any,
    ) -> str | None: ...
    @abstractmethod
    async def update_body(self, body: dict[Any, Any]) -> None: ...
    @abstractmethod
    async def reset_secrets(self) -> None: ...
    @abstractmethod
    async def reauthenticate(self, *, conn: SnowflakeConnection, **kwargs: Any) -> dict[str, Any]: ...
    async def handle_timeout(
        self, *, authenticator: str, service_name: str | None, account: str, user: str, password: str, **kwargs: Any
    ) -> None: ...
