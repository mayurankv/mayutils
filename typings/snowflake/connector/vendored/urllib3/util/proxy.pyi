import typing

from ..connection import ProxyConfig
from .url import Url

if typing.TYPE_CHECKING: ...

def connection_requires_http_tunnel(
    proxy_url: Url | None = ..., proxy_config: ProxyConfig | None = ..., destination_scheme: str | None = ...
) -> bool: ...
