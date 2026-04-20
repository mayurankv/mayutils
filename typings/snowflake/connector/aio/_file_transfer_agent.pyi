from typing import IO, TYPE_CHECKING, Any

from ..file_transfer_agent import SnowflakeFileMeta, SnowflakeProgressPercentage
from ..file_transfer_agent import SnowflakeFileTransferAgent as SnowflakeFileTransferAgentSync
from ._cursor import SnowflakeCursor

if TYPE_CHECKING: ...
logger = ...

class SnowflakeFileTransferAgent(SnowflakeFileTransferAgentSync):
    def __init__(
        self,
        cursor: SnowflakeCursor,
        command: str,
        ret: dict[str, Any],
        put_callback: type[SnowflakeProgressPercentage] | None = ...,
        put_azure_callback: type[SnowflakeProgressPercentage] | None = ...,
        put_callback_output_stream: IO[str] = ...,
        get_callback: type[SnowflakeProgressPercentage] | None = ...,
        get_azure_callback: type[SnowflakeProgressPercentage] | None = ...,
        get_callback_output_stream: IO[str] = ...,
        show_progress_bar: bool = ...,
        raise_put_get_error: bool = ...,
        force_put_overwrite: bool = ...,
        skip_upload_on_content_match: bool = ...,
        multipart_threshold: int | None = ...,
        source_from_stream: IO[bytes] | None = ...,
        use_s3_regional_url: bool = ...,
        unsafe_file_write: bool = ...,
        reraise_error_in_file_transfer_work_function: bool = ...,
    ) -> None: ...
    async def execute(self) -> None: ...
    async def transfer(self, metas: list[SnowflakeFileMeta]) -> None: ...
