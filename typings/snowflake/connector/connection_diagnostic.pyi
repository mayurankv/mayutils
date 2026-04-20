from .compat import IS_WINDOWS
from .session_manager import SessionManager

logger = ...
if IS_WINDOWS: ...

class ConnectionDiagnostic:
    def __init__(
        self,
        account: str,
        host: str,
        connection_diag_log_path: str | None = ...,
        connection_diag_allowlist_path: str | None = ...,
        proxy_host: str | None = ...,
        proxy_port: str | None = ...,
        proxy_user: str | None = ...,
        proxy_password: str | None = ...,
        session_manager: SessionManager | None = ...,
    ) -> None: ...
    def run_post_test(self) -> None: ...
    def run_test(self) -> None: ...
    def generate_report(self) -> None: ...
