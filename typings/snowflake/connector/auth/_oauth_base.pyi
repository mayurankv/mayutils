from abc import ABC
from typing import TYPE_CHECKING, Any

from .. import SnowflakeConnection
from ..token_cache import TokenCache
from .by_plugin import AuthByPlugin, AuthType

if TYPE_CHECKING: ...
logger = ...

class _OAuthTokensMixin:
    def __init__(self, token_cache: TokenCache | None, refresh_token_enabled: bool, idp_host: str) -> None: ...

class AuthByOAuthBase(AuthByPlugin, _OAuthTokensMixin, ABC):
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_request_url: str,
        scope: str,
        token_cache: TokenCache | None,
        refresh_token_enabled: bool,
        **kwargs,
    ) -> None: ...
    def reset_secrets(self) -> None: ...
    @property
    def type_(self) -> AuthType: ...
    @property
    def assertion_content(self) -> str: ...
    def reauthenticate(self, *, conn: SnowflakeConnection, **kwargs: Any) -> dict[str, bool]: ...
    def prepare(
        self, *, conn: SnowflakeConnection, authenticator: str, service_name: str | None, account: str, user: str, **kwargs: Any
    ) -> None: ...
    def update_body(self, body: dict[Any, Any]) -> None: ...
