from collections import deque
from collections.abc import Awaitable, Callable, Iterator
from typing import TYPE_CHECKING, Any

from snowflake.connector.aio._cursor import SnowflakeCursor
from snowflake.connector.aio._result_batch import ArrowResultBatch, JSONResultBatch, ResultBatch
from snowflake.connector.result_set import ResultSet as ResultSetSync

if TYPE_CHECKING: ...
logger = ...

class ResultSetIterator:
    def __init__(
        self,
        first_batch_iter: Iterator[tuple],
        unfetched_batches: deque[ResultBatch],
        final: Callable[[], Awaitable[None]],
        prefetch_thread_num: int,
        **kw: Any,
    ) -> None: ...
    async def fetch_all_data(self):  # -> list[tuple[Any, ...]]:
        ...
    async def generator(self):  # -> Generator[tuple[Any, ...] | Any, Any, None]:
        ...
    async def get_next(self):  # -> tuple[Any, ...] | None:
        ...

class ResultSet(ResultSetSync):
    def __init__(
        self, cursor: SnowflakeCursor, result_chunks: list[JSONResultBatch] | list[ArrowResultBatch], prefetch_thread_num: int
    ) -> None: ...
