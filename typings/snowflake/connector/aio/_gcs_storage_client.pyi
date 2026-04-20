from typing import TYPE_CHECKING, Any

from ..constants import FileHeader
from ..file_transfer_agent import SnowflakeFileMeta, StorageCredential
from ..gcs_storage_client import SnowflakeGCSRestClient as SnowflakeGCSRestClientSync
from ._connection import SnowflakeConnection
from ._storage_client import SnowflakeStorageClient as SnowflakeStorageClientAsync

if TYPE_CHECKING: ...
logger = ...

class SnowflakeGCSRestClient(SnowflakeStorageClientAsync, SnowflakeGCSRestClientSync):
    def __init__(
        self,
        meta: SnowflakeFileMeta,
        credentials: StorageCredential,
        stage_info: dict[str, Any],
        cnx: SnowflakeConnection,
        command: str,
        unsafe_file_write: bool = ...,
    ) -> None: ...
    async def download_chunk(self, chunk_id: int) -> None: ...
    async def finish_download(self) -> None: ...
    async def get_file_header(self, filename: str) -> FileHeader | None: ...
