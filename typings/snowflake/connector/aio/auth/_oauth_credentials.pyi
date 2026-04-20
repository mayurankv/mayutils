from typing import TYPE_CHECKING, Any

from ...auth.oauth_credentials import AuthByOauthCredentials as AuthByOauthCredentialsSync
from .. import SnowflakeConnection
from ._by_plugin import AuthByPlugin as AuthByPluginAsync

if TYPE_CHECKING: ...
logger = ...

class AuthByOauthCredentials(AuthByPluginAsync, AuthByOauthCredentialsSync):
    def __init__(
        self,
        application: str,
        client_id: str,
        client_secret: str,
        token_request_url: str,
        scope: str,
        connection: SnowflakeConnection | None = ...,
        credentials_in_body: bool = ...,
        **kwargs,
    ) -> None: ...
    async def reset_secrets(self) -> None: ...
    async def prepare(self, **kwargs: Any) -> None: ...
    async def reauthenticate(self, conn: SnowflakeConnection, **kwargs: Any) -> dict[str, bool]: ...
    async def update_body(self, body: dict[Any, Any]) -> None: ...
