import typing

from ..._base_connection import _TYPE_BODY, BaseHTTPConnection, BaseHTTPSConnection
from ...connection import ProxyConfig
from ...response import BaseHTTPResponse
from ...util.connection import _TYPE_SOCKET_OPTIONS
from ...util.timeout import _TYPE_TIMEOUT
from ...util.url import Url
from .response import EmscriptenResponse

if typing.TYPE_CHECKING: ...

class EmscriptenHTTPConnection:
    default_port: typing.ClassVar[int] = ...
    default_socket_options: typing.ClassVar[_TYPE_SOCKET_OPTIONS]
    timeout: None | float
    host: str
    port: int
    blocksize: int
    source_address: tuple[str, int] | None
    socket_options: _TYPE_SOCKET_OPTIONS | None
    proxy: Url | None
    proxy_config: ProxyConfig | None
    is_verified: bool = ...
    proxy_is_verified: bool | None = ...
    response_class: type[BaseHTTPResponse] = ...
    _response: EmscriptenResponse | None
    def __init__(
        self,
        host: str,
        port: int = ...,
        *,
        timeout: _TYPE_TIMEOUT = ...,
        source_address: tuple[str, int] | None = ...,
        blocksize: int = ...,
        socket_options: _TYPE_SOCKET_OPTIONS | None = ...,
        proxy: Url | None = ...,
        proxy_config: ProxyConfig | None = ...,
    ) -> None: ...
    def set_tunnel(self, host: str, port: int | None = ..., headers: typing.Mapping[str, str] | None = ..., scheme: str = ...) -> None: ...
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

class EmscriptenHTTPSConnection(EmscriptenHTTPConnection):
    default_port = ...
    cert_reqs: int | str | None = ...
    ca_certs: str | None = ...
    ca_cert_dir: str | None = ...
    ca_cert_data: None | str | bytes = ...
    cert_file: str | None
    key_file: str | None
    key_password: str | None
    ssl_context: typing.Any | None
    ssl_version: int | str | None = ...
    ssl_minimum_version: int | None = ...
    ssl_maximum_version: int | None = ...
    assert_hostname: None | str | typing.Literal[False]
    assert_fingerprint: str | None = ...
    def __init__(
        self,
        host: str,
        port: int = ...,
        *,
        timeout: _TYPE_TIMEOUT = ...,
        source_address: tuple[str, int] | None = ...,
        blocksize: int = ...,
        socket_options: (None | _TYPE_SOCKET_OPTIONS) = ...,
        proxy: Url | None = ...,
        proxy_config: ProxyConfig | None = ...,
        cert_reqs: int | str | None = ...,
        assert_hostname: None | str | typing.Literal[False] = ...,
        assert_fingerprint: str | None = ...,
        server_hostname: str | None = ...,
        ssl_context: typing.Any | None = ...,
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
    def set_cert(
        self,
        key_file: str | None = ...,
        cert_file: str | None = ...,
        cert_reqs: int | str | None = ...,
        key_password: str | None = ...,
        ca_certs: str | None = ...,
        assert_hostname: None | str | typing.Literal[False] = ...,
        assert_fingerprint: str | None = ...,
        ca_cert_dir: str | None = ...,
        ca_cert_data: None | str | bytes = ...,
    ) -> None: ...

if typing.TYPE_CHECKING:
    _supports_http_protocol: BaseHTTPConnection = ...
    _supports_https_protocol: BaseHTTPSConnection = ...
