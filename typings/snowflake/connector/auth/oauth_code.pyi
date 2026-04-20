from typing import TYPE_CHECKING

from .. import SnowflakeConnection
from ..token_cache import TokenCache
from ._oauth_base import AuthByOAuthBase

if TYPE_CHECKING: ...
logger = ...
BUF_SIZE = ...

class AuthByOauthCode(AuthByOAuthBase):
    _LOCAL_APPLICATION_CLIENT_CREDENTIALS = ...
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
