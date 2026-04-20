import typing

from ._base_connection import _TYPE_BODY
from .filepost import _TYPE_FIELDS
from .response import BaseHTTPResponse

__all__ = ["RequestMethods"]
type _TYPE_ENCODE_URL_FIELDS = typing.Sequence[tuple[str, str | bytes]] | typing.Mapping[str, str | bytes]

class RequestMethods:
    _encode_url_methods = ...
    def __init__(self, headers: typing.Mapping[str, str] | None = ...) -> None: ...
    def urlopen(
        self,
        method: str,
        url: str,
        body: _TYPE_BODY | None = ...,
        headers: typing.Mapping[str, str] | None = ...,
        encode_multipart: bool = ...,
        multipart_boundary: str | None = ...,
        **kw: typing.Any,
    ) -> BaseHTTPResponse: ...
    def request(
        self,
        method: str,
        url: str,
        body: _TYPE_BODY | None = ...,
        fields: _TYPE_FIELDS | None = ...,
        headers: typing.Mapping[str, str] | None = ...,
        json: typing.Any | None = ...,
        **urlopen_kw: typing.Any,
    ) -> BaseHTTPResponse: ...
    def request_encode_url(
        self,
        method: str,
        url: str,
        fields: _TYPE_ENCODE_URL_FIELDS | None = ...,
        headers: typing.Mapping[str, str] | None = ...,
        **urlopen_kw: str,
    ) -> BaseHTTPResponse: ...
    def request_encode_body(
        self,
        method: str,
        url: str,
        fields: _TYPE_FIELDS | None = ...,
        headers: typing.Mapping[str, str] | None = ...,
        encode_multipart: bool = ...,
        multipart_boundary: str | None = ...,
        **urlopen_kw: str,
    ) -> BaseHTTPResponse: ...
