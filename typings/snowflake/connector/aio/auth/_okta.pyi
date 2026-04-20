from typing import TYPE_CHECKING, Any

from ...auth.okta import AuthByOkta as AuthByOktaSync
from .. import SnowflakeConnection
from ._by_plugin import AuthByPlugin as AuthByPluginAsync

if TYPE_CHECKING: ...
logger = ...

class AuthByOkta(AuthByPluginAsync, AuthByOktaSync):
    def __init__(self, application: str, **kwargs) -> None: ...
    async def reset_secrets(self) -> None: ...
    async def prepare(
        self,
        *,
        conn: SnowflakeConnection,
        authenticator: str,
        service_name: str | None,
        account: str,
        user: str,
        password: str,
        **kwargs: Any,
    ) -> None: ...
    async def reauthenticate(self, **kwargs: Any) -> dict[str, bool]: ...
    async def update_body(self, body: dict[Any, Any]) -> None: ...
