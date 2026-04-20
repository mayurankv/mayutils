import abc
import contextlib
import sys
from collections.abc import AsyncGenerator, Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Unpack

import aiohttp
from aiohttp import ClientRequest, ClientTimeout
from aiohttp.client import _RequestContextManager, _RequestOptions
from aiohttp.client_proto import ResponseHandler
from aiohttp.connector import Connection
from aiohttp.tracing import Trace
from aiohttp.typedefs import StrOrURL

from ..constants import OCSPMode
from ..session_manager import BaseHttpConfig, _BaseConfigDirectAccessMixin
from ..session_manager import SessionManager as SessionManagerSync
from ..session_manager import SessionPool as SessionPoolSync

if TYPE_CHECKING: ...
logger = ...

class SnowflakeSSLConnector(aiohttp.TCPConnector):
    def __init__(self, *args, snowflake_ocsp_mode: OCSPMode = ..., session_manager: SessionManager | None = ..., **kwargs) -> None: ...
    async def connect(self, req: ClientRequest, traces: list[Trace], timeout: ClientTimeout) -> Connection: ...
    async def validate_ocsp(self, hostname: str, protocol: ResponseHandler, *, session_manager: SessionManager): ...

class ConnectorFactory(abc.ABC):
    @abc.abstractmethod
    def __call__(self, *args, **kwargs) -> aiohttp.BaseConnector: ...

class SnowflakeSSLConnectorFactory(ConnectorFactory):
    def __call__(self, *args, session_manager: SessionManager, **kwargs) -> SnowflakeSSLConnector: ...

@dataclass(frozen=True)
class AioHttpConfig(BaseHttpConfig):
    connector_factory: Callable[..., aiohttp.BaseConnector] = ...
    trust_env: bool = ...
    snowflake_ocsp_mode: OCSPMode = ...
    def get_connector(self, **override_connector_factory_kwargs) -> aiohttp.BaseConnector: ...

class SessionPool(SessionPoolSync[aiohttp.ClientSession]):
    def __init__(self, manager: SessionManager) -> None: ...
    async def close(self) -> None: ...
    def __getstate__(self): ...
    def __setstate__(self, state): ...

class _RequestVerbsUsingSessionMixin(abc.ABC):
    @abc.abstractmethod
    async def use_session(self, url: str | bytes, use_pooling: bool) -> AsyncGenerator[aiohttp.ClientSession]: ...
    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = ...,
        timeout: int | tuple[int, int] | None = ...,
        use_pooling: bool | None = ...,
        **kwargs,
    ) -> aiohttp.ClientResponse: ...
    async def options(
        self, url: str, *, headers: Mapping[str, str] | None = ..., timeout: int | None = ..., use_pooling: bool | None = ..., **kwargs
    ) -> aiohttp.ClientResponse: ...
    async def head(
        self, url: str, *, headers: Mapping[str, str] | None = ..., timeout: int | None = ..., use_pooling: bool | None = ..., **kwargs
    ) -> aiohttp.ClientResponse: ...
    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = ...,
        timeout: int | None = ...,
        use_pooling: bool | None = ...,
        data=...,
        json=...,
        **kwargs,
    ) -> aiohttp.ClientResponse: ...
    async def put(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = ...,
        timeout: int | None = ...,
        use_pooling: bool | None = ...,
        data=...,
        **kwargs,
    ) -> aiohttp.ClientResponse: ...
    async def patch(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = ...,
        timeout: int | None = ...,
        use_pooling: bool | None = ...,
        data=...,
        **kwargs,
    ) -> aiohttp.ClientResponse: ...
    async def delete(
        self, url: str, *, headers: Mapping[str, str] | None = ..., timeout: int | None = ..., use_pooling: bool | None = ..., **kwargs
    ) -> aiohttp.ClientResponse: ...

class _AsyncHttpConfigDirectAccessMixin(_BaseConfigDirectAccessMixin, abc.ABC):
    @property
    @abc.abstractmethod
    def config(self) -> AioHttpConfig: ...
    @config.setter
    @abc.abstractmethod
    def config(self, value) -> AioHttpConfig: ...
    @property
    def connector_factory(self) -> Callable[..., aiohttp.BaseConnector]: ...
    @connector_factory.setter
    def connector_factory(self, value: Callable[..., aiohttp.BaseConnector]) -> None: ...

class SessionManager(_RequestVerbsUsingSessionMixin, SessionManagerSync, _AsyncHttpConfigDirectAccessMixin):
    def __init__(self, config: AioHttpConfig | None = ..., **http_config_kwargs) -> None: ...
    @classmethod
    def from_config(cls, cfg: AioHttpConfig, **overrides: Any) -> SessionManager: ...
    def make_session(self, *, url: str | None = ...) -> aiohttp.ClientSession: ...
    @contextlib.asynccontextmanager
    async def use_session(self, url: str | bytes, use_pooling: bool | None = ...) -> AsyncGenerator[aiohttp.ClientSession]: ...
    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = ...,
        timeout: int | None = ...,
        use_pooling: bool | None = ...,
        **kwargs: Any,
    ) -> aiohttp.ClientResponse: ...
    async def close(self): ...
    def clone(self, **http_config_overrides) -> SessionManager: ...

async def request(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = ...,
    timeout: int | None = ...,
    session_manager: SessionManager | None = ...,
    use_pooling: bool | None = ...,
    **kwargs: Any,
) -> aiohttp.ClientResponse: ...

class ProxySessionManager(SessionManager):
    class SessionWithProxy(aiohttp.ClientSession):
        if sys.version_info >= (3, 11) and TYPE_CHECKING:
            def request(self, method: str, url: StrOrURL, **kwargs: Unpack[_RequestOptions]) -> _RequestContextManager: ...

        else: ...

    def make_session(self, *, url: str | None = ...) -> aiohttp.ClientSession: ...

class SessionManagerFactory:
    @staticmethod
    def get_manager(config: AioHttpConfig | None = ..., **http_config_kwargs) -> SessionManager: ...
