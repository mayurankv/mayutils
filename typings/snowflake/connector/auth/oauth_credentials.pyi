from typing import TYPE_CHECKING

from .. import SnowflakeConnection
from ._oauth_base import AuthByOAuthBase

if TYPE_CHECKING: ...
logger = ...

class AuthByOauthCredentials(AuthByOAuthBase):
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
