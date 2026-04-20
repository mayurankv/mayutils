import abc
from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Any

from pandas import DataFrame
from pyarrow import Table
from snowflake.connector.aio._connection import SnowflakeConnection
from snowflake.connector.aio._cursor import SnowflakeCursor
from snowflake.connector.cursor import ResultMetadataV2
from snowflake.connector.result_batch import ArrowResultBatch as ArrowResultBatchSync
from snowflake.connector.result_batch import JSONResultBatch as JSONResultBatchSync
from snowflake.connector.result_batch import ResultBatch as ResultBatchSync

if TYPE_CHECKING: ...
logger = ...
DOWNLOAD_TIMEOUT = ...
MAX_DOWNLOAD_RETRY = ...

def create_batches_from_response(
    cursor: SnowflakeCursor, _format: str, data: dict[str, Any], schema: Sequence[ResultMetadataV2]
) -> list[ResultBatch]: ...

class ResultBatch(ResultBatchSync):
    def __iter__(self): ...
    @abc.abstractmethod
    async def create_iter(
        self, **kwargs
    ) -> Iterator[dict | Exception] | Iterator[tuple | Exception] | Iterator[Table] | Iterator[DataFrame]: ...

class JSONResultBatch(ResultBatch, JSONResultBatchSync):
    async def create_iter(
        self, connection: SnowflakeConnection | None = ..., **kwargs
    ) -> Iterator[dict | Exception] | Iterator[tuple | Exception]: ...

class ArrowResultBatch(ResultBatch, ArrowResultBatchSync):
    async def to_arrow(self, connection: SnowflakeConnection | None = ...) -> Table: ...
    async def to_pandas(self, connection: SnowflakeConnection | None = ..., **kwargs) -> DataFrame: ...
    async def create_iter(
        self, connection: SnowflakeConnection | None = ..., **kwargs
    ) -> Iterator[dict | Exception] | Iterator[tuple | Exception] | Iterator[Table] | Iterator[DataFrame]: ...
