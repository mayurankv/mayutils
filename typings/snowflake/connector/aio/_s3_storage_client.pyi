from typing import TYPE_CHECKING, Any

from ..constants import FileHeader
from ..file_transfer_agent import SnowflakeFileMeta, StorageCredential
from ..s3_storage_client import SnowflakeS3RestClient as SnowflakeS3RestClientSync
from ._storage_client import SnowflakeStorageClient as SnowflakeStorageClientAsync

if TYPE_CHECKING: ...
logger = ...

class SnowflakeS3RestClient(SnowflakeStorageClientAsync, SnowflakeS3RestClientSync):
    def __init__(
        self,
        meta: SnowflakeFileMeta,
        credentials: StorageCredential,
        stage_info: dict[str, Any],
        chunk_size: int,
        use_accelerate_endpoint: bool | None = ...,
        use_s3_regional_url: bool = ...,
        unsafe_file_write: bool = ...,
    ) -> None: ...
    async def get_file_header(self, filename: str) -> FileHeader | None: ...
    async def download_chunk(self, chunk_id: int) -> None: ...
    async def transfer_accelerate_config(self, use_accelerate_endpoint: bool | None = ...) -> bool: ...
