import logging
import sys
import typing

from ._base_connection import _TYPE_BODY
from ._collections import HTTPHeaderDict
from ._version import __version__
from .connectionpool import HTTPConnectionPool, HTTPSConnectionPool, connection_from_url
from .filepost import _TYPE_FIELDS, encode_multipart_formdata
from .poolmanager import PoolManager, ProxyManager, proxy_from_url
from .response import BaseHTTPResponse, HTTPResponse
from .util.request import make_headers
from .util.retry import Retry
from .util.timeout import Timeout

__author__ = ...
__license__ = ...
__version__ = ...
__all__ = (
    "BaseHTTPResponse",
    "HTTPConnectionPool",
    "HTTPHeaderDict",
    "HTTPResponse",
    "HTTPSConnectionPool",
    "PoolManager",
    "ProxyManager",
    "Retry",
    "Timeout",
    "add_stderr_logger",
    "connection_from_url",
    "disable_warnings",
    "encode_multipart_formdata",
    "make_headers",
    "proxy_from_url",
    "request",
)

def add_stderr_logger(level: int = ...) -> logging.StreamHandler[typing.TextIO]: ...
def disable_warnings(category: type[Warning] = ...) -> None: ...

_DEFAULT_POOL = ...

def request(
    method: str,
    url: str,
    *,
    body: _TYPE_BODY | None = ...,
    fields: _TYPE_FIELDS | None = ...,
    headers: typing.Mapping[str, str] | None = ...,
    preload_content: bool | None = ...,
    decode_content: bool | None = ...,
    redirect: bool | None = ...,
    retries: Retry | bool | int | None = ...,
    timeout: Timeout | float | None = ...,
    json: typing.Any | None = ...,
) -> BaseHTTPResponse: ...

if sys.platform == "emscripten": ...
