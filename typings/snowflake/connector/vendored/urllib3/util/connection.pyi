import socket
import typing

from .._base_connection import BaseHTTPConnection
from .timeout import _TYPE_TIMEOUT

type _TYPE_SOCKET_OPTIONS = list[tuple[int, int, int | bytes]]
if typing.TYPE_CHECKING: ...

def is_connection_dropped(conn: BaseHTTPConnection) -> bool: ...
def create_connection(
    address: tuple[str, int],
    timeout: _TYPE_TIMEOUT = ...,
    source_address: tuple[str, int] | None = ...,
    socket_options: _TYPE_SOCKET_OPTIONS | None = ...,
) -> socket.socket: ...
def allowed_gai_family() -> socket.AddressFamily: ...

HAS_IPV6 = ...
