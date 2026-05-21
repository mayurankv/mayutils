"""Live, incrementally-refreshed DataFrame views backed by SQL queries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, cast

from mayutils.core.extras import may_require_extras
from mayutils.data.queries import QUERIES_FOLDERS
from mayutils.data.read import render_query
from mayutils.environment.logging import Logger
from mayutils.objects.dataframes.backends import Backend, BackendOperations, DataFrames, default_backend
from mayutils.objects.datetime import DateTime, Interval

with may_require_extras():
    import pandas as pd

if TYPE_CHECKING:
    from pathlib import Path

    from mayutils.data.read import QueryReader
    from mayutils.objects.datetime import Duration
    from mayutils.objects.types import SQL, SupportsStr


logger = Logger.spawn()


class StreamingQuery[DataFrameType: DataFrames = pd.DataFrame]:
    """Incrementally pull rows by tracking ``max(cursor_column)``.

    The query template must contain a ``{cursor}`` placeholder. On each
    update the cursor is formatted into the template and only rows past
    the previous cursor are fetched.
    """

    def __init__(
        self,
        query: SQL | Path,
        /,
        *,
        cursor_column: str,
        initial_cursor: object,
        reader: QueryReader[DataFrameType],
        backend: Backend[DataFrameType] | None = None,
        max_rows: int | None = None,
        max_age: Duration | None = None,
        update_frequency: Duration | None = None,
        time_format: str = "%Y-%m-%d %H:%M:%S",
        queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
        **fixed_format_kwargs: SupportsStr,
    ) -> None:
        self.query = query
        self.reader = reader
        self.backend = backend if backend is not None else cast("Backend[DataFrameType]", default_backend())
        self.cursor_column = cursor_column
        self.max_rows = max_rows
        self.max_age = max_age
        self.update_frequency = update_frequency
        self.time_format = time_format
        self.queries_folders = queries_folders
        self.fixed_format_kwargs = fixed_format_kwargs
        self.initial_cursor = initial_cursor

        self.validate_retention()

        self.cursor_value: Any = initial_cursor
        self.cursor_is_datetime: bool = hasattr(initial_cursor, "strftime")
        self._data: DataFrameType = self.fetch()
        self.last_updated: DateTime = DateTime.now()

    @property
    def data(
        self,
    ) -> DataFrameType:
        return self._data

    def update(
        self,
        *,
        force: bool = False,
    ) -> Self:
        if not self.should_update(force=force):
            return self

        snapshot = self.data
        try:
            delta = self.fetch()
        except Exception as err:
            self._data = snapshot

            logger.exception("StreamingQuery update failed", exc_info=err)

            return self

        if len(delta) > 0:
            self._data = BackendOperations.concat(self.data, delta, backend=self.backend)
            self.apply_retention()

        self.last_updated = DateTime.now()

        return self

    def reset(
        self,
    ) -> Self:
        self._data = self.fetch()
        self.last_updated = DateTime.now()

        return self

    def fetch(
        self,
    ) -> DataFrameType:
        data = self.read_query(cursor=self.cursor)

        if len(data) != 0:
            self.cursor_value = BackendOperations.max(data, self.cursor_column, backend=self.backend)

        return data

    @property
    def cursor(
        self,
    ) -> str:
        if self.cursor_is_datetime and hasattr(self.cursor_value, "strftime"):
            return self.cursor_value.strftime(self.time_format)

        return str(self.cursor_value)

    def read_query(
        self,
        *,
        default_suffix: str = "sql",
        **extra_kwargs: SupportsStr,
    ) -> DataFrameType:
        rendered = render_query(
            self.query,
            queries_folders=self.queries_folders,
            default_suffix=default_suffix,
            **self.fixed_format_kwargs,
            **extra_kwargs,
        )

        return self.reader(
            rendered,
            backend=self.backend,
        )

    def should_update(
        self,
        *,
        force: bool,
    ) -> bool:
        if force or self.update_frequency is None:
            return True

        return (DateTime.now() - self.last_updated) > self.update_frequency

    def apply_retention(
        self,
    ) -> None:
        if self.max_age is not None and len(self.data) > 0:
            newest = BackendOperations.max(self.data, self.cursor_column, backend=self.backend)
            if hasattr(newest, "strftime"):
                try:
                    cutoff = DateTime.parse(cast("DateTime", newest).strftime(self.time_format)) - self.max_age

                except (TypeError, ValueError):
                    pass
                else:
                    self._data = BackendOperations.filter_ge(
                        self.data,
                        self.cursor_column,
                        cutoff.strftime(format=self.time_format),
                        backend=self.backend,
                    )

        if self.max_rows is not None and len(self.data) > self.max_rows:
            self._data = BackendOperations.tail(
                self.data,
                self.max_rows,
                backend=self.backend,
            )

    def validate_retention(
        self,
    ) -> None:
        if self.max_rows is not None and self.max_rows <= 0:
            msg = f"max_rows must be positive, got {self.max_rows}"
            raise ValueError(msg)

        if self.max_age is not None and self.max_age.total_seconds() <= 0:
            msg = f"max_age must be positive, got {self.max_age}"
            raise ValueError(msg)


class WindowedQuery[DataFrameType: DataFrames = pd.DataFrame]:
    """Manage a sliding or expanding time window over a SQL query.

    The query template must contain ``{start_timestamp}`` and
    ``{end_timestamp}`` placeholders. On each update, only the delta
    since the previous window end is fetched.

    When *deduplicate* is ``True``, rows are deduped on *index_column*
    after each concat (keeps last), which handles re-fetched open
    buckets in time-bucketed aggregate queries.
    """

    def __init__(
        self,
        query: SQL | Path,
        /,
        *,
        index_column: str,
        start_timestamp: DateTime,
        reader: QueryReader[DataFrameType],
        backend: Backend[DataFrameType] | None = None,
        rolling: bool = True,
        deduplicate: bool = False,
        max_rows: int | None = None,
        max_age: Duration | None = None,
        update_frequency: Duration | None = None,
        time_format: str = "%Y-%m-%d",
        queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
        **fixed_format_kwargs: SupportsStr,
    ) -> None:
        self.query = query
        self.reader = reader
        self.backend = backend if backend is not None else cast("Backend[DataFrameType]", default_backend())
        self.index_column = index_column
        self._rolling = rolling
        self._deduplicate = deduplicate
        self.max_rows = max_rows
        self.max_age = max_age
        self.update_frequency = update_frequency
        self.time_format = time_format
        self.queries_folders = queries_folders
        self.fixed_format_kwargs = fixed_format_kwargs
        self.start_timestamp = start_timestamp

        self.validate_retention()

        self._interval: Interval[DateTime] = Interval(
            start=start_timestamp,
            end=DateTime.now(),
            absolute=True,
        )
        self._data: DataFrameType = self.fetch(initial=True)
        self.last_updated: DateTime = DateTime.now()

    @property
    def data(
        self,
    ) -> DataFrameType:
        return self._data

    @property
    def interval(
        self,
    ) -> Interval[DateTime]:
        return self._interval

    @property
    def rolling(
        self,
    ) -> bool:
        return self._rolling

    @property
    def deduplicate(
        self,
    ) -> bool:
        return self._deduplicate

    def update(
        self,
        *,
        force: bool = False,
    ) -> Self:
        if not self.should_update(force=force):
            return self

        snapshot = self.data
        snapshot_interval = self.interval
        try:
            delta = self.fetch()
        except Exception:
            self._data = snapshot
            self._interval = snapshot_interval
            logger.exception("WindowedQuery update failed")
            return self

        if len(delta) > 0:
            self._data = BackendOperations.concat(self.data, delta, backend=self.backend)

            if self.deduplicate:
                self._data = BackendOperations.deduplicate(
                    self.data,
                    self.index_column,
                    backend=self.backend,
                )

            self.apply_retention()

        self.last_updated = DateTime.now()

        return self

    def reset(
        self,
        *,
        start_timestamp: DateTime | None = None,
    ) -> Self:
        if start_timestamp is not None:
            self.start_timestamp = start_timestamp

        self._interval = Interval(
            start=self.start_timestamp,
            end=DateTime.now(),
            absolute=True,
        )

        self._data = self.fetch(initial=True)
        self.last_updated = DateTime.now()

        return self

    def fetch(
        self,
        *,
        initial: bool = False,
    ) -> DataFrameType:
        if initial:
            return self.read_query(
                start_timestamp=self._interval.start.strftime(format=self.time_format),
                end_timestamp=self._interval.end.strftime(format=self.time_format),
            )

        now = DateTime.now()
        previous_end = self._interval.end

        new_start = (now - self._interval.as_duration()) if self.rolling else self._interval.start

        if self.rolling and len(self.data) > 0:
            self._data = BackendOperations.filter_ge(
                self.data,
                self.index_column,
                new_start.strftime(format=self.time_format),
                backend=self.backend,
            )

        delta = self.read_query(
            start_timestamp=previous_end.strftime(format=self.time_format),
            end_timestamp=now.strftime(format=self.time_format),
        )

        self._interval = Interval(start=new_start, end=now, absolute=True)

        return delta

    def read_query(
        self,
        /,
        *,
        default_suffix: str = "sql",
        **extra_kwargs: SupportsStr,
    ) -> DataFrameType:
        rendered = render_query(
            self.query,
            queries_folders=self.queries_folders,
            default_suffix=default_suffix,
            **self.fixed_format_kwargs,
            **extra_kwargs,
        )

        return self.reader(
            rendered,
            backend=self.backend,
        )

    def should_update(
        self,
        *,
        force: bool,
    ) -> bool:
        if force or self.update_frequency is None:
            return True

        return (DateTime.now() - self.last_updated) > self.update_frequency

    def apply_retention(
        self,
    ) -> None:
        if self.max_age is not None and len(self.data) > 0:
            newest = BackendOperations.max(self.data, self.index_column, backend=self.backend)
            if hasattr(newest, "strftime"):
                try:
                    cutoff = DateTime.parse(cast("DateTime", newest).strftime(self.time_format)) - self.max_age

                except (TypeError, ValueError):
                    pass
                else:
                    self._data = BackendOperations.filter_ge(
                        self.data,
                        self.index_column,
                        cutoff.strftime(format=self.time_format),
                        backend=self.backend,
                    )

        if self.max_rows is not None and len(self.data) > self.max_rows:
            self._data = BackendOperations.tail(
                self.data,
                self.max_rows,
                backend=self.backend,
            )

    def validate_retention(self) -> None:
        if self.max_rows is not None and self.max_rows <= 0:
            msg = f"max_rows must be positive, got {self.max_rows}"
            raise ValueError(msg)

        if self.max_age is not None and self.max_age.total_seconds() <= 0:
            msg = f"max_age must be positive, got {self.max_age}"
            raise ValueError(msg)


__all__ = [
    "StreamingQuery",
    "WindowedQuery",
]
