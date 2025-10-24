from mayutils.environment.databases import EngineWrapper as EngineWrapper
from mayutils.objects.datetime import (
    DateTime as DateTime,
    Duration as Duration,
    Interval as Interval,
)
from pandas import DataFrame
from typing import Callable, Self

class LiveData:
    """
    Class to manage live data updates and aggregation.

    Assumptions:
        - Data is pulled via a named SQL query in an appropriate queries folder
        - This SQL query has a timestamp column to index time against
        - This SQL query can be formatted with `start_timestamp` and `end_timestamp` to select incremental data
        - Data is stored in a pandas DataFrame
    """
    def __init__(
        self,
        query_string: str,
        engine: EngineWrapper,
        index_column: str,
        start_timestamp: DateTime,
        rolling: bool = True,
        aggregations: dict[str, Callable[[DataFrame], DataFrame]] = {},
        update_frequency: Duration | None = None,
        time_format: str = "%Y-%m-%d",
        **format_kwargs,
    ) -> None: ...
    def update(
        self, engine: EngineWrapper | None = None, force: bool = False
    ) -> Self: ...
    def reset(self, start_timestamp: DateTime | None = None) -> Self: ...
