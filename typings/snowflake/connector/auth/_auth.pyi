from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ..session_manager import BaseHttpConfig
from ..session_manager import SessionManager as SyncSessionManager
from ..token_cache import TokenCache
from . import AuthByPlugin

if TYPE_CHECKING: ...
logger = ...
KEYRING_SERVICE_NAME = ...
KEYRING_USER = ...
KEYRING_DRIVER_NAME = ...
ID_TOKEN = ...
MFA_TOKEN = ...
AUTHENTICATION_REQUEST_KEY_WHITELIST = ...

class Auth:
    def __init__(self, rest) -> None: ...
    @staticmethod
    def base_auth_data(
        user,
        account,
        application,
        internal_application_name,
        internal_application_version,
        ocsp_mode,
        cert_revocation_check_mode,
        login_timeout: int | None = ...,
        network_timeout: int | None = ...,
        socket_timeout: int | None = ...,
        platform_detection_timeout_seconds: float | None = ...,
        session_manager: SyncSessionManager | None = ...,
        http_config: BaseHttpConfig | None = ...,
    ): ...
    def authenticate(
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
    def read_temporary_credentials(self, host: str, user: str, session_parameters: dict[str, Any]) -> None: ...
    def write_temporary_credentials(self, host: str, user: str, session_parameters: dict[str, Any], response: dict[str, Any]) -> None: ...
    def get_token_cache(self) -> TokenCache: ...

def get_token_from_private_key(user: str, account: str, privatekey_path: str, key_password: str | None) -> str: ...
def get_public_key_fingerprint(private_key_file: str, password: str) -> str: ...
