import typing
from typing import TYPE_CHECKING, Any

from ...auth.workload_identity import AuthByWorkloadIdentity as AuthByWorkloadIdentitySync
from .. import SnowflakeConnection
from .._wif_util import AttestationProvider
from ._by_plugin import AuthByPlugin as AuthByPluginAsync

if TYPE_CHECKING: ...

class AuthByWorkloadIdentity(AuthByPluginAsync, AuthByWorkloadIdentitySync):
    def __init__(
        self,
        *,
        provider: AttestationProvider,
        token: str | None = ...,
        entra_resource: str | None = ...,
        impersonation_path: list[str] | None = ...,
        **kwargs,
    ) -> None: ...
    async def reset_secrets(self) -> None: ...
    async def prepare(self, *, conn: SnowflakeConnection | None, **kwargs: typing.Any) -> None: ...
    async def reauthenticate(self, **kwargs: Any) -> dict[str, bool]: ...
    async def update_body(self, body: dict[Any, Any]) -> None: ...
