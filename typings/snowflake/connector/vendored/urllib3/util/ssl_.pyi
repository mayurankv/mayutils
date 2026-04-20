import socket
import ssl
import sys
import typing
from ssl import HAS_NEVER_CHECK_COMMON_NAME, OPENSSL_VERSION, OPENSSL_VERSION_NUMBER, SSLContext, VerifyMode
from typing import TypedDict

from .ssltransport import SSLTransport as SSLTransportType

SSLContext = ...
SSLTransport = ...
HAS_NEVER_CHECK_COMMON_NAME = ...
IS_PYOPENSSL = ...
ALPN_PROTOCOLS = ...
type _TYPE_VERSION_INFO = tuple[int, int, int, str, int]
HASHFUNC_MAP = ...
if typing.TYPE_CHECKING:
    class _TYPE_PEER_CERT_RET_DICT(TypedDict, total=False):
        subjectAltName: tuple[tuple[str, str], ...]
        subject: tuple[tuple[tuple[str, str], ...], ...]
        serialNumber: str

_SSL_VERSION_TO_TLS_VERSION: dict[int, int] = ...
PROTOCOL_SSLv23 = ...
VERIFY_X509_PARTIAL_CHAIN = ...
if HAS_NEVER_CHECK_COMMON_NAME and not _is_has_never_check_common_name_reliable(
    OPENSSL_VERSION,
    OPENSSL_VERSION_NUMBER,
    sys.implementation.name,
    sys.version_info,
    sys.pypy_version_info if sys.implementation.name == "pypy" else None,
):
    HAS_NEVER_CHECK_COMMON_NAME = ...
type _TYPE_PEER_CERT_RET = _TYPE_PEER_CERT_RET_DICT | bytes | None

def assert_fingerprint(cert: bytes | None, fingerprint: str) -> None: ...
def resolve_cert_reqs(candidate: None | int | str) -> VerifyMode: ...
def resolve_ssl_version(candidate: None | int | str) -> int: ...
def create_urllib3_context(
    ssl_version: int | None = ...,
    cert_reqs: int | None = ...,
    options: int | None = ...,
    ciphers: str | None = ...,
    ssl_minimum_version: int | None = ...,
    ssl_maximum_version: int | None = ...,
    verify_flags: int | None = ...,
) -> ssl.SSLContext: ...
@typing.overload
def ssl_wrap_socket(
    sock: socket.socket,
    keyfile: str | None = ...,
    certfile: str | None = ...,
    cert_reqs: int | None = ...,
    ca_certs: str | None = ...,
    server_hostname: str | None = ...,
    ssl_version: int | None = ...,
    ciphers: str | None = ...,
    ssl_context: ssl.SSLContext | None = ...,
    ca_cert_dir: str | None = ...,
    key_password: str | None = ...,
    ca_cert_data: None | str | bytes = ...,
    tls_in_tls: typing.Literal[False] = ...,
) -> ssl.SSLSocket: ...
@typing.overload
def ssl_wrap_socket(
    sock: socket.socket,
    keyfile: str | None = ...,
    certfile: str | None = ...,
    cert_reqs: int | None = ...,
    ca_certs: str | None = ...,
    server_hostname: str | None = ...,
    ssl_version: int | None = ...,
    ciphers: str | None = ...,
    ssl_context: ssl.SSLContext | None = ...,
    ca_cert_dir: str | None = ...,
    key_password: str | None = ...,
    ca_cert_data: None | str | bytes = ...,
    tls_in_tls: bool = ...,
) -> ssl.SSLSocket | SSLTransportType: ...
def ssl_wrap_socket(
    sock: socket.socket,
    keyfile: str | None = ...,
    certfile: str | None = ...,
    cert_reqs: int | None = ...,
    ca_certs: str | None = ...,
    server_hostname: str | None = ...,
    ssl_version: int | None = ...,
    ciphers: str | None = ...,
    ssl_context: ssl.SSLContext | None = ...,
    ca_cert_dir: str | None = ...,
    key_password: str | None = ...,
    ca_cert_data: None | str | bytes = ...,
    tls_in_tls: bool = ...,
) -> ssl.SSLSocket | SSLTransportType: ...
def is_ipaddress(hostname: str | bytes) -> bool: ...
