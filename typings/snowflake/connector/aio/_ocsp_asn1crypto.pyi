from aiohttp.client_proto import ResponseHandler

from ..ocsp_asn1crypto import SnowflakeOCSPAsn1Crypto as SnowflakeOCSPAsn1CryptoSync
from ._ocsp_snowflake import SnowflakeOCSP

logger = ...

class SnowflakeOCSPAsn1Crypto(SnowflakeOCSP, SnowflakeOCSPAsn1CryptoSync):
    def extract_certificate_chain(self, connection: ResponseHandler):  # -> list[tuple[Certificate, Certificate]]:
        ...
