from typing import TYPE_CHECKING, Any

from ...auth.oauth_code import AuthByOauthCode as AuthByOauthCodeSync
from ...token_cache import TokenCache
from .. import SnowflakeConnection
from ._by_plugin import AuthByPlugin as AuthByPluginAsync

if TYPE_CHECKING: ...
logger = ...

class AuthByOauthCode(AuthByPluginAsync, AuthByOauthCodeSync):
    def __init__(
        self,
        application: str,
        client_id: str,
        client_secret: str,
        authentication_url: str,
        token_request_url: str,
        redirect_uri: str,
        scope: str,
        host: str,
        pkce_enabled: bool = ...,
        token_cache: TokenCache | None = ...,
        refresh_token_enabled: bool = ...,
        external_browser_timeout: int | None = ...,
        enable_single_use_refresh_tokens: bool = ...,
        connection: SnowflakeConnection | None = ...,
        uri: str | None = ...,
        **kwargs,
    ) -> None: ...
    async def reset_secrets(self) -> None: ...
    async def prepare(self, **kwargs: Any) -> None: ...
    async def reauthenticate(self, conn: SnowflakeConnection, **kwargs: Any) -> dict[str, bool]: ...
    async def update_body(self, body: dict[Any, Any]) -> None: ...
