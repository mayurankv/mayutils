import ssl
import typing
from types import TracebackType
from typing import Self

from ._request_methods import RequestMethods
from .connection import ProxyConfig
from .connectionpool import HTTPConnectionPool
from .response import BaseHTTPResponse
from .util.connection import _TYPE_SOCKET_OPTIONS
from .util.retry import Retry
from .util.timeout import Timeout
from .util.url import Url

if typing.TYPE_CHECKING: ...
__all__ = ["PoolManager", "ProxyManager", "proxy_from_url"]
log = ...
SSL_KEYWORDS = ...
_DEFAULT_BLOCKSIZE = ...

class PoolKey(typing.NamedTuple):
    key_scheme: str
    key_host: str
    key_port: int | None
    key_timeout: Timeout | float | int | None
    key_retries: Retry | bool | int | None
    key_block: bool | None
    key_source_address: tuple[str, int] | None
    key_key_file: str | None
    key_key_password: str | None
    key_cert_file: str | None
    key_cert_reqs: str | None
    key_ca_certs: str | None
    key_ca_cert_data: str | bytes | None
    key_ssl_version: int | str | None
    key_ssl_minimum_version: ssl.TLSVersion | None
    key_ssl_maximum_version: ssl.TLSVersion | None
    key_ca_cert_dir: str | None
    key_ssl_context: ssl.SSLContext | None
    key_maxsize: int | None
    key_headers: frozenset[tuple[str, str]] | None
    key__proxy: Url | None
    key__proxy_headers: frozenset[tuple[str, str]] | None
    key__proxy_config: ProxyConfig | None
    key_socket_options: _TYPE_SOCKET_OPTIONS | None
    key__socks_options: frozenset[tuple[str, str]] | None
    key_assert_hostname: bool | str | None
    key_assert_fingerprint: str | None
    key_server_hostname: str | None
    key_blocksize: int | None

key_fn_by_scheme = ...
pool_classes_by_scheme = ...

class PoolManager(RequestMethods):
    proxy: Url | None = ...
    proxy_config: ProxyConfig | None = ...
    def __init__(self, num_pools: int = ..., headers: typing.Mapping[str, str] | None = ..., **connection_pool_kw: typing.Any) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> typing.Literal[False]: ...
    def clear(self) -> None: ...
    def connection_from_host(
        self, host: str | None, port: int | None = ..., scheme: str | None = ..., pool_kwargs: dict[str, typing.Any] | None = ...
    ) -> HTTPConnectionPool: ...
    def connection_from_context(self, request_context: dict[str, typing.Any]) -> HTTPConnectionPool: ...
    def connection_from_pool_key(self, pool_key: PoolKey, request_context: dict[str, typing.Any]) -> HTTPConnectionPool: ...
    def connection_from_url(self, url: str, pool_kwargs: dict[str, typing.Any] | None = ...) -> HTTPConnectionPool: ...
    def urlopen(self, method: str, url: str, redirect: bool = ..., **kw: typing.Any) -> BaseHTTPResponse: ...

class ProxyManager(PoolManager):
    def __init__(
        self,
        proxy_url: str,
        num_pools: int = ...,
        headers: typing.Mapping[str, str] | None = ...,
        proxy_headers: typing.Mapping[str, str] | None = ...,
        proxy_ssl_context: ssl.SSLContext | None = ...,
        use_forwarding_for_https: bool = ...,
        proxy_assert_hostname: None | str | typing.Literal[False] = ...,
        proxy_assert_fingerprint: str | None = ...,
        **connection_pool_kw: typing.Any,
    ) -> None: ...
    def connection_from_host(
        self, host: str | None, port: int | None = ..., scheme: str | None = ..., pool_kwargs: dict[str, typing.Any] | None = ...
    ) -> HTTPConnectionPool: ...
    def urlopen(self, method: str, url: str, redirect: bool = ..., **kw: typing.Any) -> BaseHTTPResponse: ...

def proxy_from_url(url: str, **kw: typing.Any) -> ProxyManager: ...
