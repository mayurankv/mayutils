from typing import TYPE_CHECKING, Any

from ..azure_storage_client import SnowflakeAzureRestClient as SnowflakeAzureRestClientSync
from ..constants import FileHeader
from ..file_transfer_agent import SnowflakeFileMeta, StorageCredential
from ._storage_client import SnowflakeStorageClient as SnowflakeStorageClientAsync

if TYPE_CHECKING: ...
logger = ...

class SnowflakeAzureRestClient(SnowflakeStorageClientAsync, SnowflakeAzureRestClientSync):
    def __init__(
        self,
        meta: SnowflakeFileMeta,
        credentials: StorageCredential | None,
        chunk_size: int,
        stage_info: dict[str, Any],
        unsafe_file_write: bool = ...,
    ) -> None: ...
    async def get_file_header(self, filename: str) -> FileHeader | None: ...
    async def download_chunk(self, chunk_id: int) -> None: ...
