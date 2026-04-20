from typing import TYPE_CHECKING, Any

from aiohttp.client_proto import ResponseHandler
from asn1crypto.ocsp import CertId
from asn1crypto.x509 import Certificate
from snowflake.connector.aio._session_manager import SessionManager
from snowflake.connector.ocsp_snowflake import OCSPServer as OCSPServerSync
from snowflake.connector.ocsp_snowflake import OCSPTelemetryData
from snowflake.connector.ocsp_snowflake import SnowflakeOCSP as SnowflakeOCSPSync

if TYPE_CHECKING: ...
logger = ...

class OCSPServer(OCSPServerSync):
    async def download_cache_from_server(self, ocsp, *, session_manager: SessionManager):  # -> None:
        ...

class SnowflakeOCSP(SnowflakeOCSPSync):
    def __init__(
        self,
        ocsp_response_cache_uri=...,
        use_ocsp_cache_server=...,
        use_post_method: bool = ...,
        use_fail_open: bool = ...,
        root_certs_dict_lock_timeout: int = ...,
        **kwargs,
    ) -> None: ...
    async def validate(
        self, hostname: str | None, connection: ResponseHandler, *, session_manager: SessionManager, no_exception: bool = ...
    ) -> list[tuple[Exception | None, Certificate, Certificate, CertId, str | bytes]] | None: ...
    async def validate_by_direct_connection(
        self,
        issuer: Certificate,
        subject: Certificate,
        telemetry_data: OCSPTelemetryData,
        *,
        session_manager: SessionManager,
        hostname: str = ...,
        do_retry: bool = ...,
        **kwargs: Any,
    ) -> tuple[Exception | None, Certificate, Certificate, CertId, bytes]: ...
