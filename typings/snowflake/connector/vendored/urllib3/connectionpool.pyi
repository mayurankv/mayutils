import queue
import ssl
import typing
from types import TracebackType
from typing import Self

from ._base_connection import _TYPE_BODY, BaseHTTPConnection, BaseHTTPSConnection
from ._request_methods import RequestMethods
from .connection import ProxyConfig
from .response import BaseHTTPResponse
from .util.request import _TYPE_BODY_POSITION
from .util.retry import Retry
from .util.timeout import _TYPE_DEFAULT, Timeout
from .util.url import Url

if typing.TYPE_CHECKING: ...
log = ...
type _TYPE_TIMEOUT = Timeout | float | _TYPE_DEFAULT | None

class ConnectionPool:
    scheme: str | None = ...
    QueueCls = queue.LifoQueue
    def __init__(self, host: str, port: int | None = ...) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> typing.Literal[False]: ...
    def close(self) -> None: ...

_blocking_errnos = ...

class HTTPConnectionPool(ConnectionPool, RequestMethods):
    scheme = ...
    ConnectionCls: type[BaseHTTPConnection | BaseHTTPSConnection] = ...
    def __init__(
        self,
        host: str,
        port: int | None = ...,
        timeout: _TYPE_TIMEOUT | None = ...,
        maxsize: int = ...,
        block: bool = ...,
        headers: typing.Mapping[str, str] | None = ...,
        retries: Retry | bool | int | None = ...,
        _proxy: Url | None = ...,
        _proxy_headers: typing.Mapping[str, str] | None = ...,
        _proxy_config: ProxyConfig | None = ...,
        **conn_kw: typing.Any,
    ) -> None: ...
    def close(self) -> None: ...
    def is_same_host(self, url: str) -> bool: ...
    def urlopen(
        self,
        method: str,
        url: str,
        body: _TYPE_BODY | None = ...,
        headers: typing.Mapping[str, str] | None = ...,
        retries: Retry | bool | int | None = ...,
        redirect: bool = ...,
        assert_same_host: bool = ...,
        timeout: _TYPE_TIMEOUT = ...,
        pool_timeout: int | None = ...,
        release_conn: bool | None = ...,
        chunked: bool = ...,
        body_pos: _TYPE_BODY_POSITION | None = ...,
        preload_content: bool = ...,
        decode_content: bool = ...,
        **response_kw: typing.Any,
    ) -> BaseHTTPResponse: ...

class HTTPSConnectionPool(HTTPConnectionPool):
    scheme = ...
    ConnectionCls: type[BaseHTTPSConnection] = ...
    def __init__(
        self,
        host: str,
        port: int | None = ...,
        timeout: _TYPE_TIMEOUT | None = ...,
        maxsize: int = ...,
        block: bool = ...,
        headers: typing.Mapping[str, str] | None = ...,
        retries: Retry | bool | int | None = ...,
        _proxy: Url | None = ...,
        _proxy_headers: typing.Mapping[str, str] | None = ...,
        key_file: str | None = ...,
        cert_file: str | None = ...,
        cert_reqs: int | str | None = ...,
        key_password: str | None = ...,
        ca_certs: str | None = ...,
        ssl_version: int | str | None = ...,
        ssl_minimum_version: ssl.TLSVersion | None = ...,
        ssl_maximum_version: ssl.TLSVersion | None = ...,
        assert_hostname: str | typing.Literal[False] | None = ...,
        assert_fingerprint: str | None = ...,
        ca_cert_dir: str | None = ...,
        **conn_kw: typing.Any,
    ) -> None: ...

def connection_from_url(url: str, **kw: typing.Any) -> HTTPConnectionPool: ...
