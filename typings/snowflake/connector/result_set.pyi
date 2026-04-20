from collections import deque
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any

from pyarrow import Table
from snowflake.connector.cursor import SnowflakeCursor

from .result_batch import ArrowResultBatch, JSONResultBatch, ResultBatch

if TYPE_CHECKING: ...
logger = ...

def result_set_iterator(
    first_batch_iter: Iterator[tuple],
    unconsumed_batches: deque[Future[Iterator[tuple]]],
    unfetched_batches: deque[ResultBatch],
    final: Callable[[], None],
    prefetch_thread_num: int,
    use_mp: bool,
    **kw: Any,
) -> Iterator[dict | Exception] | Iterator[tuple | Exception] | Iterator[Table]: ...

class ResultSet(Iterable[list]):
    def __init__(
        self, cursor: SnowflakeCursor, result_chunks: list[JSONResultBatch] | list[ArrowResultBatch], prefetch_thread_num: int, use_mp: bool
    ) -> None: ...
    def __iter__(self) -> Iterator[tuple]: ...
    def total_row_index(self) -> int: ...
