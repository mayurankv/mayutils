import abc
from collections.abc import Callable, Iterator, Sequence
from enum import Enum, unique
from typing import TYPE_CHECKING, Any, NamedTuple, Self

from pandas import DataFrame
from pyarrow import DataType, Table

from .arrow_context import ArrowConverterContext
from .connection import SnowflakeConnection
from .converter import SnowflakeConverterType
from .cursor import ResultMetadataV2, SnowflakeCursor
from .session_manager import HttpConfig, SessionManager

logger = ...
MAX_DOWNLOAD_RETRY = ...
DOWNLOAD_TIMEOUT = ...
if TYPE_CHECKING: ...
FIELD_TYPE_TO_PA_TYPE: list[Callable[[ResultMetadataV2], DataType]] = ...
SSE_C_ALGORITHM = ...
SSE_C_KEY = ...
SSE_C_AES = ...

@unique
class DownloadMetrics(Enum):
    download = ...
    parse = ...
    load = ...

class RemoteChunkInfo(NamedTuple):
    url: str
    uncompressedSize: int
    compressedSize: int

def create_batches_from_response(
    cursor: SnowflakeCursor, _format: str, data: dict[str, Any], schema: Sequence[ResultMetadataV2]
) -> list[ResultBatch]: ...

class ResultBatch(abc.ABC):
    def __init__(
        self,
        rowcount: int,
        chunk_headers: dict[str, str] | None,
        remote_chunk_info: RemoteChunkInfo | None,
        schema: Sequence[ResultMetadataV2],
        use_dict_result: bool,
        session_manager: SessionManager | None = ...,
    ) -> None: ...
    @property
    def compressed_size(self) -> int | None: ...
    @property
    def uncompressed_size(self) -> int | None: ...
    @property
    def column_names(self) -> list[str]: ...
    @property
    def session_manager(self) -> SessionManager | None: ...
    @session_manager.setter
    def session_manager(self, session_manager: SessionManager | None) -> None: ...
    @property
    def http_config(self): ...
    @http_config.setter
    def http_config(self, config: HttpConfig) -> None: ...
    def __iter__(self) -> Iterator[dict | Exception] | Iterator[tuple | Exception]: ...
    @abc.abstractmethod
    def create_iter(self, **kwargs) -> Iterator[dict | Exception] | Iterator[tuple | Exception] | Iterator[Table] | Iterator[DataFrame]: ...
    @abc.abstractmethod
    def to_pandas(self) -> DataFrame: ...
    @abc.abstractmethod
    def to_arrow(self) -> Table: ...
    @abc.abstractmethod
    def populate_data(self, connection: SnowflakeConnection | None = ..., **kwargs) -> Self: ...

class JSONResultBatch(ResultBatch):
    def __init__(
        self,
        rowcount: int,
        chunk_headers: dict[str, str] | None,
        remote_chunk_info: RemoteChunkInfo | None,
        schema: Sequence[ResultMetadataV2],
        column_converters: Sequence[tuple[str, SnowflakeConverterType]],
        use_dict_result: bool,
        *,
        json_result_force_utf8_decoding: bool = ...,
        session_manager: SessionManager | None = ...,
    ) -> None: ...
    @classmethod
    def from_data(
        cls,
        data: Sequence[Sequence[Any]],
        data_len: int,
        schema: Sequence[ResultMetadataV2],
        column_converters: Sequence[tuple[str, SnowflakeConverterType]],
        use_dict_result: bool,
        session_manager: SessionManager | None = ...,
    ): ...
    def populate_data(self, connection: SnowflakeConnection | None = ..., **kwargs) -> Self: ...
    def create_iter(
        self, connection: SnowflakeConnection | None = ..., **kwargs
    ) -> Iterator[dict | Exception] | Iterator[tuple | Exception]: ...
    def to_pandas(self): ...
    def to_arrow(self): ...

class ArrowResultBatch(ResultBatch):
    def __init__(
        self,
        rowcount: int,
        chunk_headers: dict[str, str] | None,
        remote_chunk_info: RemoteChunkInfo | None,
        context: ArrowConverterContext,
        use_dict_result: bool,
        numpy: bool,
        schema: Sequence[ResultMetadataV2],
        number_to_decimal: bool,
        session_manager: SessionManager | None = ...,
    ) -> None: ...
    @classmethod
    def from_data(
        cls,
        data: str,
        data_len: int,
        context: ArrowConverterContext,
        use_dict_result: bool,
        numpy: bool,
        schema: Sequence[ResultMetadataV2],
        number_to_decimal: bool,
        session_manager: SessionManager | None = ...,
    ): ...
    def to_arrow(self, connection: SnowflakeConnection | None = ..., force_microsecond_precision: bool = ...) -> Table: ...
    def to_pandas(self, connection: SnowflakeConnection | None = ..., force_microsecond_precision: bool = ..., **kwargs) -> DataFrame: ...
    def create_iter(
        self, connection: SnowflakeConnection | None = ..., **kwargs
    ) -> Iterator[dict | Exception] | Iterator[tuple | Exception] | Iterator[Table] | Iterator[DataFrame]: ...
    def populate_data(self, connection: SnowflakeConnection | None = ..., **kwargs) -> Self: ...
