"""Live, incrementally-refreshed DataFrame views backed by SQL queries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, cast

from mayutils.data.queries import QUERIES_FOLDERS
from mayutils.data.read import render_query
from mayutils.environment.logging import Logger
from mayutils.objects.dataframes.backends import Backend, BackendOperations, DataFrames, default_backend

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    import pandas as pd

    from mayutils.data.read import QueryReader
    from mayutils.objects.datetime import DateTime, Duration, Interval
    from mayutils.objects.types import SQL


logger = Logger.spawn()


class StreamingQuery[DataFrameType: DataFrames = pd.DataFrame]:
    """
    Incrementally pull rows by tracking ``max(cursor_column)``.

    The query template must contain a ``{{ cursor }}`` placeholder. On
    each update the cursor is rendered into the template and only rows
    past the previous cursor are fetched. Results are returned exactly
    as the *reader* produces them: unlike
    :func:`mayutils.data.read.read_query`, no automatic temporal column
    parsing is applied, keeping the schema stable across incremental
    fetches that are concatenated together.

    Parameters
    ----------
    query
        SQL string or path to a ``.sql`` template containing
        ``{{ cursor }}``.
    cursor_column
        Column whose maximum is tracked as the cursor.
    initial_cursor
        Starting cursor value used for the first fetch.
    reader
        Callable that executes a rendered SQL query and returns a DataFrame.
    backend
        Backend token; defaults to pandas when ``None``.
    max_rows
        Maximum rows to retain after each update.
    max_age
        Maximum age of rows to retain after each update.
    update_frequency
        Minimum interval between consecutive fetches.
    time_format
        :meth:`~datetime.datetime.strftime` format for datetime cursors.
    queries_folders
        Directories searched when *query* is a filename.
    template_kwargs
        Jinja2 template variables rendered into the query template on
        every call.  The key ``cursor`` is injected per-call by
        :meth:`fetch` and overrides any value stored here.

    See Also
    --------
    WindowedQuery : Time-windowed alternative using start/end timestamps.

    Examples
    --------
    >>> from mayutils.data.live import StreamingQuery  # doctest: +SKIP
    """

    def __init__(
        self,
        query: SQL | Path,
        /,
        *,
        cursor_column: str,
        initial_cursor: object,
        reader: QueryReader,
        backend: Backend[DataFrameType] | None = None,
        max_rows: int | None = None,
        max_age: Duration | None = None,
        update_frequency: Duration | None = None,
        time_format: str = "%Y-%m-%d %H:%M:%S",
        queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
        template_kwargs: Mapping[str, object] | None = None,
    ) -> None:
        """
        Initialise the streaming query and perform the first fetch.

        Validates retention settings, executes the first query against
        *initial_cursor*, and stores the result as the initial data.

        Parameters
        ----------
        query
            SQL string or path to a ``.sql`` template containing
            ``{{ cursor }}``.
        cursor_column
            Column whose maximum is tracked as the cursor.
        initial_cursor
            Starting cursor value used for the first fetch.
        reader
            Callable that executes a rendered SQL query and returns a
            DataFrame.
        backend
            Backend token; defaults to pandas when ``None``.
        max_rows
            Maximum rows to retain after each update.
        max_age
            Maximum age of rows to retain after each update.
        update_frequency
            Minimum interval between consecutive fetches.
        time_format
            :meth:`~datetime.datetime.strftime` format for datetime
            cursors.
        queries_folders
            Directories searched when *query* is a filename.
        template_kwargs
            Jinja2 template variables rendered into the query template
            on every call.  The key ``cursor`` is injected per-call by
            :meth:`fetch` and overrides any value stored here.

        See Also
        --------
        StreamingQuery.fetch : Execute the query and advance the cursor.

        Examples
        --------
        >>> from mayutils.data.live import StreamingQuery  # doctest: +SKIP
        >>> sq = StreamingQuery(  # doctest: +SKIP
        ...     "SELECT * FROM t WHERE id > {{ cursor }}",
        ...     cursor_column="id",
        ...     initial_cursor=0,
        ...     reader=my_reader,
        ... )
        """
        self.query = query
        self.reader = reader
        self.backend = backend if backend is not None else cast("Backend[DataFrameType]", default_backend())
        self.cursor_column = cursor_column
        self.max_rows = max_rows
        self.max_age = max_age
        self.update_frequency = update_frequency
        self.time_format = time_format
        self.queries_folders = queries_folders
        self.template_kwargs: dict[str, object] = dict(template_kwargs or {})
        self.initial_cursor = initial_cursor

        self.validate_retention()

        from mayutils.objects.datetime import DateTime

        self.cursor_value: Any = initial_cursor
        self.cursor_is_datetime: bool = hasattr(initial_cursor, "strftime")
        self._data: DataFrameType = self.fetch()
        self.last_updated: DateTime = DateTime.now()

    @property
    def data(
        self,
    ) -> DataFrameType:
        """
        Return the current accumulated DataFrame.

        Provides read-only access to the internal data buffer that grows
        with each :meth:`update` call.

        Returns
        -------
            The accumulated rows.

        See Also
        --------
        StreamingQuery.update : Append new rows.

        Examples
        --------
        >>> sq.data  # doctest: +SKIP
        """
        return self._data

    def update(
        self,
        *,
        force: bool = False,
    ) -> Self:
        """
        Fetch new rows since the last cursor and append them.

        Skips the fetch when *update_frequency* has not elapsed unless
        *force* is ``True``.  On failure the previous data is preserved.

        Parameters
        ----------
        force
            When ``True``, bypass the *update_frequency* throttle.

        Returns
        -------
        Self
            The query instance for fluent chaining.

        See Also
        --------
        StreamingQuery.fetch : Low-level fetch and cursor advance.

        Examples
        --------
        >>> sq.update(force=True)  # doctest: +SKIP
        """
        if not self.should_update(force=force):
            return self

        from mayutils.objects.datetime import DateTime

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
        """
        Drop all data and re-fetch from the current cursor.

        Replaces the internal buffer with a fresh query result starting
        from the current cursor position.

        Returns
        -------
        Self
            The query instance for fluent chaining.

        See Also
        --------
        StreamingQuery.fetch : Execute the query and advance the cursor.

        Examples
        --------
        >>> sq.reset()  # doctest: +SKIP
        """
        from mayutils.objects.datetime import DateTime

        self._data = self.fetch()
        self.last_updated = DateTime.now()

        return self

    def fetch(
        self,
    ) -> DataFrameType:
        """
        Execute the query at the current cursor and advance it.

        Renders the SQL template with the current cursor, runs the query,
        and updates the cursor to the maximum of *cursor_column*.

        Returns
        -------
            The rows returned by the query.

        See Also
        --------
        StreamingQuery.read_query : Render and execute the SQL template.

        Examples
        --------
        >>> delta = sq.fetch()  # doctest: +SKIP
        """
        data = self.read_query(template_kwargs={"cursor": self.cursor})

        if len(data) != 0:
            self.cursor_value = BackendOperations.max(data, self.cursor_column, backend=self.backend)

        return data

    @property
    def cursor(
        self,
    ) -> str:
        """
        Return the current cursor value formatted as a string.

        Datetime cursors are formatted via *time_format*; all other types
        are cast with ``str()``.

        Returns
        -------
            The formatted cursor string.

        See Also
        --------
        StreamingQuery.fetch : Uses the cursor to parameterise the query.

        Examples
        --------
        >>> sq.cursor  # doctest: +SKIP
        '2024-01-01 00:00:00'
        """
        if self.cursor_is_datetime and hasattr(self.cursor_value, "strftime"):
            return self.cursor_value.strftime(self.time_format)

        return str(self.cursor_value)

    def read_query(
        self,
        *,
        default_suffix: str = "sql",
        template_kwargs: Mapping[str, object] | None = None,
    ) -> DataFrameType:
        """
        Render and execute the SQL query template.

        Merges the per-call *template_kwargs* over the mapping stored at
        construction (per-call keys win), renders the template, and
        passes it to *reader*.

        Parameters
        ----------
        default_suffix
            File extension appended when *query* is a filename without
            one.
        template_kwargs
            Per-call Jinja2 template variables merged over the stored
            mapping.

        Returns
        -------
            The DataFrame returned by the reader.

        See Also
        --------
        StreamingQuery.fetch : High-level fetch that calls this method.

        Examples
        --------
        >>> df = sq.read_query(template_kwargs={"cursor": "0"})  # doctest: +SKIP
        """
        rendered = render_query(
            self.query,
            queries_folders=self.queries_folders,
            default_suffix=default_suffix,
            template_kwargs={**self.template_kwargs, **(template_kwargs or {})},
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
        """
        Return whether enough time has elapsed since the last update.

        Compares the elapsed time since *last_updated* against
        *update_frequency*.

        Parameters
        ----------
        force
            When ``True``, always return ``True`` regardless of elapsed
            time.

        Returns
        -------
            ``True`` if a new fetch should proceed.

        See Also
        --------
        StreamingQuery.update : Calls this before fetching.

        Examples
        --------
        >>> sq.should_update(force=False)  # doctest: +SKIP
        True
        """
        if force or self.update_frequency is None:
            return True

        from mayutils.objects.datetime import DateTime

        return (DateTime.now() - self.last_updated) > self.update_frequency

    def apply_retention(
        self,
    ) -> None:
        """
        Trim data to satisfy *max_age* and *max_rows* constraints.

        Removes rows older than *max_age* first, then truncates to
        *max_rows* from the tail.

        See Also
        --------
        StreamingQuery.validate_retention : Guard against invalid limits.

        Examples
        --------
        >>> sq.apply_retention()  # doctest: +SKIP
        """
        if self.max_age is not None and len(self.data) > 0:
            newest = BackendOperations.max(self.data, self.cursor_column, backend=self.backend)
            if hasattr(newest, "strftime"):
                from mayutils.objects.datetime import DateTime

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
        """
        Raise if *max_rows* or *max_age* are non-positive.

        Called during ``__init__`` to fail fast on invalid retention
        settings.

        Raises
        ------
        ValueError
            If *max_rows* <= 0 or *max_age* total seconds <= 0.

        See Also
        --------
        StreamingQuery.apply_retention : Enforces the validated limits.

        Examples
        --------
        >>> sq.validate_retention()  # doctest: +SKIP
        """
        if self.max_rows is not None and self.max_rows <= 0:
            msg = f"max_rows must be positive, got {self.max_rows}"
            raise ValueError(msg)

        if self.max_age is not None and self.max_age.total_seconds() <= 0:
            msg = f"max_age must be positive, got {self.max_age}"
            raise ValueError(msg)


class WindowedQuery[DataFrameType: DataFrames = pd.DataFrame]:
    """
    Manage a sliding or expanding time window over a SQL query.

    The query template must contain ``{{ start_timestamp }}`` and
    ``{{ end_timestamp }}`` placeholders. On each update, only the
    delta since the previous window end is fetched. Results are
    returned exactly as the *reader* produces them: unlike
    :func:`mayutils.data.read.read_query`, no automatic temporal column
    parsing is applied, keeping the schema stable across windowed
    fetches that are concatenated together.

    When *deduplicate* is ``True``, rows are deduped on *index_column*
    after each concat (keeps last), which handles re-fetched open
    buckets in time-bucketed aggregate queries.

    Parameters
    ----------
    query
        SQL string or path to a ``.sql`` template containing
        ``{{ start_timestamp }}`` and ``{{ end_timestamp }}``.
    index_column
        Column used for deduplication and rolling-window filtering.
    start_timestamp
        Left edge of the initial query window.
    reader
        Callable that executes a rendered SQL query and returns a DataFrame.
    backend
        Backend token; defaults to pandas when ``None``.
    rolling
        If ``True`` the window slides forward; otherwise it expands.
    deduplicate
        If ``True``, deduplicate on *index_column* after each concat.
    max_rows
        Maximum rows to retain after each update.
    max_age
        Maximum age of rows to retain after each update.
    update_frequency
        Minimum interval between consecutive fetches.
    time_format
        :meth:`~datetime.datetime.strftime` format for window boundaries.
    queries_folders
        Directories searched when *query* is a filename.
    template_kwargs
        Jinja2 template variables rendered into the query template on
        every call.  The keys ``start_timestamp`` and ``end_timestamp``
        are injected per-call by :meth:`fetch` and override any values
        stored here.

    See Also
    --------
    StreamingQuery : Cursor-based alternative using ``max(column)``.

    Examples
    --------
    >>> from mayutils.data.live import WindowedQuery  # doctest: +SKIP
    """

    def __init__(
        self,
        query: SQL | Path,
        /,
        *,
        index_column: str,
        start_timestamp: DateTime,
        reader: QueryReader,
        backend: Backend[DataFrameType] | None = None,
        rolling: bool = True,
        deduplicate: bool = False,
        max_rows: int | None = None,
        max_age: Duration | None = None,
        update_frequency: Duration | None = None,
        time_format: str = "%Y-%m-%d",
        queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
        template_kwargs: Mapping[str, object] | None = None,
    ) -> None:
        """
        Initialise the windowed query and perform the first fetch.

        Validates retention settings, builds the initial time interval
        from *start_timestamp* to now, and fetches the first batch.

        Parameters
        ----------
        query
            SQL string or path to a ``.sql`` template containing
            ``{{ start_timestamp }}`` and ``{{ end_timestamp }}``.
        index_column
            Column used for deduplication and rolling-window filtering.
        start_timestamp
            Left edge of the initial query window.
        reader
            Callable that executes a rendered SQL query and returns a
            DataFrame.
        backend
            Backend token; defaults to pandas when ``None``.
        rolling
            If ``True`` the window slides forward; otherwise it expands.
        deduplicate
            If ``True``, deduplicate on *index_column* after each concat.
        max_rows
            Maximum rows to retain after each update.
        max_age
            Maximum age of rows to retain after each update.
        update_frequency
            Minimum interval between consecutive fetches.
        time_format
            :meth:`~datetime.datetime.strftime` format for window
            boundaries.
        queries_folders
            Directories searched when *query* is a filename.
        template_kwargs
            Jinja2 template variables rendered into the query template
            on every call.  The keys ``start_timestamp`` and
            ``end_timestamp`` are injected per-call by :meth:`fetch`
            and override any values stored here.

        See Also
        --------
        WindowedQuery.fetch : Execute the query for a time window.

        Examples
        --------
        >>> from mayutils.data.live import WindowedQuery  # doctest: +SKIP
        >>> wq = WindowedQuery(  # doctest: +SKIP
        ...     "SELECT * FROM t WHERE ts BETWEEN '{{ start_timestamp }}' AND '{{ end_timestamp }}'",
        ...     index_column="ts",
        ...     start_timestamp=DateTime.now(),
        ...     reader=my_reader,
        ... )
        """
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
        self.template_kwargs: dict[str, object] = dict(template_kwargs or {})
        self.start_timestamp = start_timestamp

        self.validate_retention()

        from mayutils.objects.datetime import DateTime, Interval

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
        """
        Return the current accumulated DataFrame.

        Provides read-only access to the internal data buffer that grows
        with each :meth:`update` call.

        Returns
        -------
            The accumulated rows.

        See Also
        --------
        WindowedQuery.update : Append new rows.

        Examples
        --------
        >>> wq.data  # doctest: +SKIP
        """
        return self._data

    @property
    def interval(
        self,
    ) -> Interval[DateTime]:
        """
        Return the current query time interval.

        The interval shifts on each :meth:`fetch` call when the window
        is rolling.

        Returns
        -------
            The current start/end interval.

        See Also
        --------
        WindowedQuery.fetch : Updates the interval on each call.

        Examples
        --------
        >>> wq.interval  # doctest: +SKIP
        """
        return self._interval

    @property
    def rolling(
        self,
    ) -> bool:
        """
        Return whether the window slides forward on each update.

        When ``True``, older data outside the window width is dropped
        during :meth:`fetch`.

        Returns
        -------
            ``True`` if the window slides; ``False`` if it expands.

        See Also
        --------
        WindowedQuery.fetch : Applies the rolling behaviour.

        Examples
        --------
        >>> wq.rolling  # doctest: +SKIP
        True
        """
        return self._rolling

    @property
    def deduplicate(
        self,
    ) -> bool:
        """
        Return whether rows are deduplicated after each concat.

        When ``True``, duplicate rows on *index_column* are removed
        (keeping last) after each :meth:`update`.

        Returns
        -------
            ``True`` if deduplication is enabled.

        See Also
        --------
        WindowedQuery.update : Performs the deduplication step.

        Examples
        --------
        >>> wq.deduplicate  # doctest: +SKIP
        False
        """
        return self._deduplicate

    def update(
        self,
        *,
        force: bool = False,
    ) -> Self:
        """
        Fetch the delta since the last window end and append it.

        Skips the fetch when *update_frequency* has not elapsed unless
        *force* is ``True``.  On failure the previous data and interval
        are preserved.

        Parameters
        ----------
        force
            When ``True``, bypass the *update_frequency* throttle.

        Returns
        -------
        Self
            The query instance for fluent chaining.

        See Also
        --------
        WindowedQuery.fetch : Low-level fetch for the next window.

        Examples
        --------
        >>> wq.update(force=True)  # doctest: +SKIP
        """
        if not self.should_update(force=force):
            return self

        from mayutils.objects.datetime import DateTime

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
        """
        Re-initialise the window and re-fetch all data from scratch.

        Optionally moves the window start before rebuilding the interval
        and fetching.

        Parameters
        ----------
        start_timestamp
            New left edge for the window.  When ``None``, the existing
            *start_timestamp* is reused.

        Returns
        -------
        Self
            The query instance for fluent chaining.

        See Also
        --------
        WindowedQuery.fetch : Execute the query for a time window.

        Examples
        --------
        >>> wq.reset()  # doctest: +SKIP
        """
        from mayutils.objects.datetime import DateTime, Interval

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
        """
        Execute the query for the current or next time window.

        When *initial* is ``True``, queries the full stored interval.
        Otherwise queries the delta since the last window end, applies
        rolling trim, and advances the interval.

        Parameters
        ----------
        initial
            When ``True``, use the stored interval as-is instead of
            computing a delta.

        Returns
        -------
            The rows returned by the query.

        See Also
        --------
        WindowedQuery.read_query : Render and execute the SQL template.

        Examples
        --------
        >>> delta = wq.fetch()  # doctest: +SKIP
        """
        if initial:
            return self.read_query(
                template_kwargs={
                    "start_timestamp": self._interval.start.strftime(format=self.time_format),
                    "end_timestamp": self._interval.end.strftime(format=self.time_format),
                },
            )

        from mayutils.objects.datetime import DateTime, Interval

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
            template_kwargs={
                "start_timestamp": previous_end.strftime(format=self.time_format),
                "end_timestamp": now.strftime(format=self.time_format),
            },
        )

        self._interval = Interval(start=new_start, end=now, absolute=True)

        return delta

    def read_query(
        self,
        /,
        *,
        default_suffix: str = "sql",
        template_kwargs: Mapping[str, object] | None = None,
    ) -> DataFrameType:
        """
        Render and execute the SQL query template.

        Merges the per-call *template_kwargs* over the mapping stored at
        construction (per-call keys win), renders the template, and
        passes it to *reader*.

        Parameters
        ----------
        default_suffix
            File extension appended when *query* is a filename without
            one.
        template_kwargs
            Per-call Jinja2 template variables merged over the stored
            mapping.

        Returns
        -------
            The DataFrame returned by the reader.

        See Also
        --------
        WindowedQuery.fetch : High-level fetch that calls this method.

        Examples
        --------
        >>> df = wq.read_query(  # doctest: +SKIP
        ...     template_kwargs={
        ...         "start_timestamp": "2024-01-01",
        ...         "end_timestamp": "2024-01-02",
        ...     },
        ... )
        """
        rendered = render_query(
            self.query,
            queries_folders=self.queries_folders,
            default_suffix=default_suffix,
            template_kwargs={**self.template_kwargs, **(template_kwargs or {})},
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
        """
        Return whether enough time has elapsed since the last update.

        Compares the elapsed time since *last_updated* against
        *update_frequency*.

        Parameters
        ----------
        force
            When ``True``, always return ``True`` regardless of elapsed
            time.

        Returns
        -------
            ``True`` if a new fetch should proceed.

        See Also
        --------
        WindowedQuery.update : Calls this before fetching.

        Examples
        --------
        >>> wq.should_update(force=False)  # doctest: +SKIP
        True
        """
        if force or self.update_frequency is None:
            return True

        from mayutils.objects.datetime import DateTime

        return (DateTime.now() - self.last_updated) > self.update_frequency

    def apply_retention(
        self,
    ) -> None:
        """
        Trim data to satisfy *max_age* and *max_rows* constraints.

        Removes rows older than *max_age* first, then truncates to
        *max_rows* from the tail.

        See Also
        --------
        WindowedQuery.validate_retention : Guard against invalid limits.

        Examples
        --------
        >>> wq.apply_retention()  # doctest: +SKIP
        """
        if self.max_age is not None and len(self.data) > 0:
            newest = BackendOperations.max(self.data, self.index_column, backend=self.backend)
            if hasattr(newest, "strftime"):
                from mayutils.objects.datetime import DateTime

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
        """
        Raise if *max_rows* or *max_age* are non-positive.

        Called during ``__init__`` to fail fast on invalid retention
        settings.

        Raises
        ------
        ValueError
            If *max_rows* <= 0 or *max_age* total seconds <= 0.

        See Also
        --------
        WindowedQuery.apply_retention : Enforces the validated limits.

        Examples
        --------
        >>> wq.validate_retention()  # doctest: +SKIP
        """
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
