import contextlib
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

import aiohttp
from snowflake.connector.aio import SnowflakeConnection

from ..network import SnowflakeRestful as SnowflakeRestfulSync
from ._session_manager import SessionManager

if TYPE_CHECKING: ...
logger = ...
PYTHON_CONNECTOR_USER_AGENT = ...

def raise_okta_unauthorized_error(connection: SnowflakeConnection | None, response: aiohttp.ClientResponse) -> None: ...
def raise_failed_request_error(connection: SnowflakeConnection | None, url: str, method: str, response: aiohttp.ClientResponse) -> None: ...

class SnowflakeRestful(SnowflakeRestfulSync):
    def __init__(
        self,
        host: str = ...,
        port: int = ...,
        protocol: str = ...,
        inject_client_pause: int = ...,
        connection: SnowflakeConnection | None = ...,
        session_manager: SessionManager | None = ...,
    ) -> None: ...
    async def close(self) -> None: ...
    async def request(
        self,
        url,
        body=...,
        method: str = ...,
        client: str = ...,
        timeout: int | None = ...,
        _no_results: bool = ...,
        _include_retry_params: bool = ...,
        _no_retry: bool = ...,
    ): ...
    async def update_tokens(self, session_token, master_token, master_validity_in_seconds=..., id_token=..., mfa_token=...) -> None: ...
    async def delete_session(self, retry: bool = ...) -> None: ...
    async def fetch(
        self, method: str, full_url: str, headers: dict[str, Any], data: dict[str, Any] | None = ..., timeout: int | None = ..., **kwargs
    ) -> dict[Any, Any]: ...
    @contextlib.asynccontextmanager
    async def use_session(self, url: str | None = ...) -> AsyncGenerator[aiohttp.ClientSession]: ...
