from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ...auth import Auth as AuthSync
from ._by_plugin import AuthByPlugin

if TYPE_CHECKING: ...
logger = ...

class Auth(AuthSync):
    async def authenticate(
        self,
        auth_instance: AuthByPlugin,
        account: str,
        user: str,
        database: str | None = ...,
        schema: str | None = ...,
        warehouse: str | None = ...,
        role: str | None = ...,
        passcode: str | None = ...,
        passcode_in_password: bool = ...,
        mfa_callback: Callable[[], None] | None = ...,
        password_callback: Callable[[], str] | None = ...,
        session_parameters: dict[Any, Any] | None = ...,
        timeout: int | None = ...,
    ) -> dict[str, str | int | bool]: ...
