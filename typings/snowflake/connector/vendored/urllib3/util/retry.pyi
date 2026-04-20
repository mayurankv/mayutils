import typing
from types import TracebackType
from typing import Self

from ..connectionpool import ConnectionPool
from ..response import BaseHTTPResponse

if typing.TYPE_CHECKING: ...
log = ...

class RequestHistory(typing.NamedTuple):
    method: str | None
    url: str | None
    error: Exception | None
    status: int | None
    redirect_location: str | None

class Retry:
    DEFAULT_ALLOWED_METHODS = ...
    RETRY_AFTER_STATUS_CODES = ...
    DEFAULT_REMOVE_HEADERS_ON_REDIRECT = ...
    DEFAULT_BACKOFF_MAX = ...
    DEFAULT_RETRY_AFTER_MAX: typing.Final[int] = ...
    DEFAULT: typing.ClassVar[Retry]
    def __init__(
        self,
        total: bool | int | None = ...,
        connect: int | None = ...,
        read: int | None = ...,
        redirect: bool | int | None = ...,
        status: int | None = ...,
        other: int | None = ...,
        allowed_methods: typing.Collection[str] | None = ...,
        status_forcelist: typing.Collection[int] | None = ...,
        backoff_factor: float = ...,
        backoff_max: float = ...,
        raise_on_redirect: bool = ...,
        raise_on_status: bool = ...,
        history: tuple[RequestHistory, ...] | None = ...,
        respect_retry_after_header: bool = ...,
        remove_headers_on_redirect: typing.Collection[str] = ...,
        backoff_jitter: float = ...,
        retry_after_max: int = ...,
    ) -> None: ...
    def new(self, **kw: typing.Any) -> Self: ...
    @classmethod
    def from_int(
        cls, retries: Retry | bool | int | None, redirect: bool | int | None = ..., default: Retry | bool | int | None = ...
    ) -> Retry: ...
    def get_backoff_time(self) -> float: ...
    def parse_retry_after(self, retry_after: str) -> float: ...
    def get_retry_after(self, response: BaseHTTPResponse) -> float | None: ...
    def sleep_for_retry(self, response: BaseHTTPResponse) -> bool: ...
    def sleep(self, response: BaseHTTPResponse | None = ...) -> None: ...
    def is_retry(self, method: str, status_code: int, has_retry_after: bool = ...) -> bool: ...
    def is_exhausted(self) -> bool: ...
    def increment(
        self,
        method: str | None = ...,
        url: str | None = ...,
        response: BaseHTTPResponse | None = ...,
        error: Exception | None = ...,
        _pool: ConnectionPool | None = ...,
        _stacktrace: TracebackType | None = ...,
    ) -> Self: ...
