import ssl
import typing
from typing import Protocol

from .response import BaseHTTPResponse
from .util.connection import _TYPE_SOCKET_OPTIONS
from .util.timeout import _TYPE_TIMEOUT
from .util.url import Url

type _TYPE_BODY = bytes | typing.IO[typing.Any] | typing.Iterable[bytes] | str

class ProxyConfig(typing.NamedTuple):
    ssl_context: ssl.SSLContext | None
    use_forwarding_for_https: bool
    assert_hostname: None | str | typing.Literal[False]
    assert_fingerprint: str | None

class _ResponseOptions(typing.NamedTuple):
    request_method: str
    request_url: str
    preload_content: bool
    decode_content: bool
    enforce_content_length: bool

if typing.TYPE_CHECKING:
    class BaseHTTPConnection(Protocol):
        default_port: typing.ClassVar[int]
        default_socket_options: typing.ClassVar[_TYPE_SOCKET_OPTIONS]
        host: str
        port: int
        timeout: None | float
        blocksize: int
        source_address: tuple[str, int] | None
        socket_options: _TYPE_SOCKET_OPTIONS | None
        proxy: Url | None
        proxy_config: ProxyConfig | None
        is_verified: bool
        proxy_is_verified: bool | None
        def __init__(
            self,
            host: str,
            port: int | None = ...,
            *,
            timeout: _TYPE_TIMEOUT = ...,
            source_address: tuple[str, int] | None = ...,
            blocksize: int = ...,
            socket_options: _TYPE_SOCKET_OPTIONS | None = ...,
            proxy: Url | None = ...,
            proxy_config: ProxyConfig | None = ...,
        ) -> None: ...
        def set_tunnel(
            self, host: str, port: int | None = ..., headers: typing.Mapping[str, str] | None = ..., scheme: str = ...
        ) -> None: ...
        def connect(self) -> None: ...
        def request(
            self,
            method: str,
            url: str,
            body: _TYPE_BODY | None = ...,
            headers: typing.Mapping[str, str] | None = ...,
            *,
            chunked: bool = ...,
            preload_content: bool = ...,
            decode_content: bool = ...,
            enforce_content_length: bool = ...,
        ) -> None: ...
        def getresponse(self) -> BaseHTTPResponse: ...
        def close(self) -> None: ...
        @property
        def is_closed(self) -> bool: ...
        @property
        def is_connected(self) -> bool: ...
        @property
        def has_connected_to_proxy(self) -> bool: ...

    class BaseHTTPSConnection(BaseHTTPConnection, Protocol):
        default_port: typing.ClassVar[int]
        default_socket_options: typing.ClassVar[_TYPE_SOCKET_OPTIONS]
        cert_reqs: int | str | None
        assert_hostname: None | str | typing.Literal[False]
        assert_fingerprint: str | None
        ssl_context: ssl.SSLContext | None
        ca_certs: str | None
        ca_cert_dir: str | None
        ca_cert_data: None | str | bytes
        ssl_minimum_version: int | None
        ssl_maximum_version: int | None
        ssl_version: int | str | None
        cert_file: str | None
        key_file: str | None
        key_password: str | None
        def __init__(
            self,
            host: str,
            port: int | None = ...,
            *,
            timeout: _TYPE_TIMEOUT = ...,
            source_address: tuple[str, int] | None = ...,
            blocksize: int = ...,
            socket_options: _TYPE_SOCKET_OPTIONS | None = ...,
            proxy: Url | None = ...,
            proxy_config: ProxyConfig | None = ...,
            cert_reqs: int | str | None = ...,
            assert_hostname: None | str | typing.Literal[False] = ...,
            assert_fingerprint: str | None = ...,
            server_hostname: str | None = ...,
            ssl_context: ssl.SSLContext | None = ...,
            ca_certs: str | None = ...,
            ca_cert_dir: str | None = ...,
            ca_cert_data: None | str | bytes = ...,
            ssl_minimum_version: int | None = ...,
            ssl_maximum_version: int | None = ...,
            ssl_version: int | str | None = ...,
            cert_file: str | None = ...,
            key_file: str | None = ...,
            key_password: str | None = ...,
        ) -> None: ...
