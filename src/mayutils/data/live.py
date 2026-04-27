"""
Provide live, incrementally-refreshed pandas data views backed by SQL queries.

This module exposes :class:`LiveData`, a thin wrapper that keeps a
pandas DataFrame in sync with a rolling (or expanding) window over a
parameterised SQL query. The initial window is pulled on construction
and subsequent :meth:`LiveData.update` calls issue delta queries for
just the rows that have appeared since the previous pull, appending
them to the cache and (when ``rolling`` is enabled) discarding rows
that have fallen out the back of the window. Database connectivity is
abstracted through the :class:`~mayutils.data.read.QueryReader`
protocol, so a :class:`LiveData` can be driven by
:meth:`mayutils.environment.databases.EngineWrapper.read_pandas`, a
Redash HTTP wrapper, a preconfigured Snowflake connector, or any other
callable that maps a rendered SQL string to a pandas DataFrame.

See Also
--------
mayutils.data.read : Shared query rendering and reader protocol.
pandas.DataFrame : Underlying frame type cached by :class:`LiveData`.
mayutils.objects.datetime.Interval : Window boundaries managed per refresh.

Examples
--------
>>> from mayutils.data.live import LiveData
>>> from mayutils.objects.datetime import DateTime, UTC
>>> live = LiveData(  # doctest: +SKIP
...     "SELECT * FROM t WHERE c BETWEEN '{start_timestamp}' AND '{end_timestamp}'",
...     reader=engine.read_pandas,
...     index_column="created_at",
...     start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
...     rolling=False,
... )
>>> _ = live.update(force=True)  # doctest: +SKIP
>>> live.data.shape  # doctest: +SKIP
(2, 2)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from mayutils.core.extras import may_require_extras
from mayutils.data.queries import QUERIES_FOLDERS
from mayutils.data.read import QueryReader, render_query
from mayutils.objects.datetime import DateTime, Interval

with may_require_extras():
    import pandas as pd
    from pandas import DataFrame

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from mayutils.objects.datetime import Duration
    from mayutils.objects.types import SupportsStr


class LiveData:
    """
    Cache a parameterised query result and refresh it incrementally.

    A :class:`LiveData` owns a single query template that accepts
    ``{start_timestamp}`` and ``{end_timestamp}`` placeholders together
    with any number of additional keyword substitutions. On
    construction, the full window ``[start_timestamp, now]`` is pulled
    and stored in :attr:`data`. Subsequent :meth:`update` calls fetch
    only the rows that have appeared since the previous pull, append
    them to the cache, and (when ``rolling`` is enabled) discard rows
    older than the new window start. Each refresh also re-runs every
    aggregation registered in :attr:`aggregations` so derived views
    stay consistent with :attr:`data`.

    Parameters
    ----------
    query
        Query template. A :class:`~pathlib.Path` is resolved against
        ``queries_folders`` via
        :func:`mayutils.data.queries.format_query`; a :class:`str` is
        treated as an inline template rendered through
        :meth:`str.format`. Either form must contain
        ``{start_timestamp}`` and ``{end_timestamp}`` placeholders in
        addition to any custom tokens satisfied by ``format_kwargs``.
    reader
        Callable that maps a rendered SQL string to a pandas
        :class:`~pandas.DataFrame`. The instance stores it as the
        default; :meth:`update` accepts an override per call.
    index_column
        Column in the query result holding the timestamp that orders
        rows in time. Used to discard rows that have fallen behind a
        rolling window.
    start_timestamp
        Inclusive lower bound of the initial pull window.
    rolling
        When ``True``, :meth:`update` keeps the window width constant
        and slides it forward. When ``False``, only the upper bound
        advances and the cache grows without bound.
    aggregations
        Named transformations applied to :attr:`data` after every
        successful refresh. ``None`` is normalised to an empty
        mapping.
    update_frequency
        Minimum wall-clock spacing between successive pulls. Calls to
        :meth:`update` issued before this duration has elapsed are
        no-ops unless ``force`` is set. ``None`` disables rate
        limiting. Any :class:`datetime.timedelta` is also accepted
        because pendulum's :class:`~pendulum.Duration` subclasses
        ``timedelta``.
    time_format
        :func:`~datetime.datetime.strftime` pattern used to render
        the two timestamp placeholders.
    queries_folders
        Search path forwarded to :func:`format_query` for
        :class:`~pathlib.Path`-typed queries.
    **format_kwargs
        Extra keyword substitutions for the query template; reused on
        every refresh.

    Attributes
    ----------
    query
        The template identifier or inline string supplied at
        construction.
    reader
        Default reader used to execute the rendered query.
    index_column
        See parameter documentation.
    format_kwargs
        The non-timestamp substitutions reused on every pull.
    queries_folders
        Search path used for :class:`~pathlib.Path`-typed queries.
    rolling
        See parameter documentation.
    aggregations
        Registered named transformations.
    aggregated_data
        Cached outputs of each aggregation against the current frame.
    initialisation_timestamp
        Wall-clock timestamp captured at construction or last
        :meth:`reset`.
    interval
        Absolute interval ``[start, end]`` representing the window
        currently materialised in :attr:`data`.
    update_frequency
        See parameter documentation.
    time_format
        See parameter documentation.
    data
        The cached query result.
    empty
        ``True`` when the initial pull returned no rows.

    See Also
    --------
    mayutils.data.read.render_query : Template renderer used to build SQL strings.
    mayutils.data.read.QueryReader : Protocol implemented by the injected reader.
    pandas.DataFrame : Underlying frame cached in :attr:`data`.
    mayutils.objects.datetime.Interval : Window boundary helper used by :attr:`interval`.

    Notes
    -----
    The query must emit a column named ``index_column`` containing
    timezone-naive timestamps so the rolling-window filter can compare
    it against :meth:`DateTime.naive`. This class currently targets
    pandas only; polars support can be layered on top once the
    underlying frame-level operations are backend-agnostic.

    Examples
    --------
    >>> from mayutils.data.live import LiveData
    >>> from mayutils.objects.datetime import DateTime, UTC
    >>> live = LiveData(  # doctest: +SKIP
    ...     "SELECT created_at, day FROM t",
    ...     reader=engine.read_pandas,
    ...     index_column="created_at",
    ...     start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
    ...     rolling=False,
    ...     aggregations={"by_day": lambda df: df.groupby("day").size().to_frame("n")},
    ... )
    >>> _ = live.update(force=True)  # doctest: +SKIP
    >>> live.data.shape  # doctest: +SKIP
    (4, 2)
    >>> live.aggregated_data["by_day"].shape  # doctest: +SKIP
    (2, 1)
    """

    def __init__(
        self,
        query: Path | str,
        /,
        *,
        reader: QueryReader,
        index_column: str,
        start_timestamp: DateTime,
        rolling: bool = True,
        aggregations: Mapping[str, Callable[[DataFrame], DataFrame]] | None = None,
        update_frequency: Duration | None = None,
        time_format: str = "%Y-%m-%d",
        queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
        **format_kwargs: SupportsStr,
    ) -> None:
        """
        Build a :class:`LiveData` and materialise its initial window.

        Delegates to :meth:`_initialise` so construction and
        :meth:`reset` share a single seeding path. The initial pull
        covers ``[start_timestamp, DateTime.now()]`` and subsequent
        calls to :meth:`update` only fetch rows after the captured
        upper bound, minimising redundant work against the reader.

        Parameters
        ----------
        query
            Template identifier or inline SQL string; see class
            docstring for resolution rules.
        reader
            Callable executing rendered queries against the backing
            data source.
        index_column
            Timestamp column used to maintain the rolling window.
        start_timestamp
            Inclusive lower bound of the initial window.
        rolling
            Whether :meth:`update` slides the window forward or grows
            it.
        aggregations
            Named transformations applied after every refresh.
        update_frequency
            Minimum spacing between refreshes; ``None`` disables rate
            limiting.
        time_format
            ``strftime`` pattern for rendering the timestamp
            placeholders.
        queries_folders
            Search path for :class:`~pathlib.Path`-typed queries.
        **format_kwargs
            Extra substitutions reused on every pull.

        See Also
        --------
        LiveData._initialise : Shared seeding routine invoked here.
        LiveData.update : Incremental refresh entry point.
        mayutils.data.read.QueryReader : Protocol satisfied by ``reader``.

        Examples
        --------
        >>> from mayutils.data.live import LiveData
        >>> from mayutils.objects.datetime import DateTime, UTC
        >>> live = LiveData(  # doctest: +SKIP
        ...     "SELECT created_at FROM t",
        ...     reader=engine.read_pandas,
        ...     index_column="created_at",
        ...     start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
        ...     rolling=False,
        ... )
        >>> isinstance(live, LiveData)  # doctest: +SKIP
        True
        """
        self._initialise(
            query,
            reader=reader,
            index_column=index_column,
            start_timestamp=start_timestamp,
            rolling=rolling,
            aggregations=aggregations,
            update_frequency=update_frequency,
            time_format=time_format,
            queries_folders=queries_folders,
            **format_kwargs,
        )

    def _initialise(
        self,
        query: Path | str,
        /,
        *,
        reader: QueryReader,
        index_column: str,
        start_timestamp: DateTime,
        rolling: bool,
        aggregations: Mapping[str, Callable[[DataFrame], DataFrame]] | None,
        update_frequency: Duration | None,
        time_format: str,
        queries_folders: tuple[Path, ...],
        **format_kwargs: SupportsStr,
    ) -> None:
        """
        Populate instance state with a fresh pull of the configured window.

        Shared seeding path used by :meth:`__init__` and
        :meth:`reset` so both leave the object in an identical,
        fully-initialised condition. The configured interval is
        captured, an initial window pull is performed through the
        supplied reader, and registered aggregations are evaluated
        exactly once so downstream views are ready before the first
        consumer touches :attr:`data`.

        Parameters
        ----------
        query
            Template identifier or inline SQL string.
        reader
            Callable executing rendered queries.
        index_column
            Timestamp column used to filter stale rows.
        start_timestamp
            Inclusive lower bound of the initial window.
        rolling
            Whether :meth:`update` slides or extends the window.
        aggregations
            Named transformations applied after every pull.
        update_frequency
            Minimum spacing between refreshes.
        time_format
            ``strftime`` pattern for timestamp placeholders.
        queries_folders
            Search path for path-typed queries.
        **format_kwargs
            Extra substitutions reused on every pull.

        See Also
        --------
        LiveData.__init__ : Public constructor that delegates here.
        LiveData.reset : Re-seeds an existing instance via this method.
        LiveData._read_window : Executes the initial reader call.
        pandas.DataFrame : Frame type stored on :attr:`data`.

        Examples
        --------
        >>> from mayutils.data.live import LiveData
        >>> from mayutils.objects.datetime import DateTime, UTC
        >>> live = LiveData.__new__(LiveData)  # doctest: +SKIP
        >>> live._initialise(  # doctest: +SKIP
        ...     "SELECT created_at FROM t",
        ...     reader=engine.read_pandas,
        ...     index_column="created_at",
        ...     start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
        ...     rolling=False,
        ...     aggregations=None,
        ...     update_frequency=None,
        ...     time_format="%Y-%m-%d",
        ...     queries_folders=(),
        ... )
        >>> live.data.shape  # doctest: +SKIP
        (1, 1)
        """
        self.query = query
        self.reader = reader
        self.index_column = index_column
        self.format_kwargs = dict(format_kwargs)
        self.queries_folders = queries_folders

        self.rolling = rolling
        self.aggregations = dict(aggregations) if aggregations is not None else {}

        self.time_format = time_format
        self.update_frequency = update_frequency

        self.initialisation_timestamp = DateTime.now()
        self.interval = Interval(
            start=start_timestamp,
            end=self.initialisation_timestamp,
            absolute=True,
        )

        self.data = self._read_window(
            reader=reader,
            start=self.interval.start,
            end=self.interval.end,
        )

        self.empty = self.data.empty
        if not self.empty:
            self._refresh_aggregations()

    def _render(
        self,
        *,
        start: DateTime,
        end: DateTime,
    ) -> str:
        """
        Render the template for the window ``[start, end]``.

        Substitutes both timestamp placeholders with the configured
        ``strftime`` pattern and forwards any stored ``format_kwargs``
        so the same template can be reused across refreshes. The
        rendering step is isolated from the reader invocation so that
        tests and tooling can inspect the exact SQL string.

        Parameters
        ----------
        start
            Lower bound used to format ``{start_timestamp}``.
        end
            Upper bound used to format ``{end_timestamp}``.

        Returns
        -------
            SQL string ready to be passed through :attr:`reader`.

        See Also
        --------
        mayutils.data.read.render_query : Underlying template renderer.
        LiveData._read_window : Consumer of the rendered string.
        LiveData.update : Top-level refresh that drives this method.

        Examples
        --------
        >>> from mayutils.data.live import LiveData
        >>> from mayutils.objects.datetime import DateTime, UTC
        >>> live = LiveData(  # doctest: +SKIP
        ...     "SELECT * FROM t WHERE c BETWEEN '{start_timestamp}' AND '{end_timestamp}'",
        ...     reader=engine.read_pandas,
        ...     index_column="created_at",
        ...     start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
        ...     rolling=False,
        ... )
        >>> live._render(  # doctest: +SKIP
        ...     start=DateTime(2026, 1, 1, tzinfo=UTC),
        ...     end=DateTime(2026, 1, 2, tzinfo=UTC),
        ... )
        "SELECT * FROM t WHERE c BETWEEN '2026-01-01' AND '2026-01-02'"
        """
        return render_query(
            self.query,
            queries_folders=self.queries_folders,
            start_timestamp=start.strftime(self.time_format),
            end_timestamp=end.strftime(self.time_format),
            **self.format_kwargs,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        )

    def _read_window(
        self,
        *,
        reader: QueryReader,
        start: DateTime,
        end: DateTime,
    ) -> DataFrame:
        """
        Execute the rendered template and return a pandas DataFrame.

        Renders the template through :meth:`_render` and drives the
        provided reader, explicitly requesting the pandas backend so
        the cache can remain type-stable. The caller may pass a reader
        override so a single :meth:`update` can route through a
        different connection (for example a warm connection pool used
        only during scheduled refreshes).

        Parameters
        ----------
        reader
            Callable used to execute the rendered query; allows
            :meth:`update` to override :attr:`reader` for a single
            pull.
        start
            Window lower bound.
        end
            Window upper bound.

        Returns
        -------
            Fresh rows covering ``[start, end]``.

        Raises
        ------
        TypeError
            If ``reader`` returns a non-pandas DataFrame. LiveData
            currently maintains a pandas-only cache; polars support
            would require backend-agnostic frame operations inside
            :meth:`_update`.

        See Also
        --------
        LiveData._render : Produces the SQL string driven here.
        mayutils.data.read.QueryReader : Reader protocol invoked with ``dataframe_backend="pandas"``.
        pandas.DataFrame : Required return type for cache compatibility.

        Examples
        --------
        >>> from mayutils.data.live import LiveData
        >>> from mayutils.objects.datetime import DateTime, UTC
        >>> live = LiveData(  # doctest: +SKIP
        ...     "SELECT * FROM t WHERE c BETWEEN '{start_timestamp}' AND '{end_timestamp}'",
        ...     reader=engine.read_pandas,
        ...     index_column="created_at",
        ...     start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
        ...     rolling=False,
        ... )
        >>> frame = live._read_window(  # doctest: +SKIP
        ...     reader=live.reader,
        ...     start=DateTime(2026, 1, 1, tzinfo=UTC),
        ...     end=DateTime(2026, 1, 2, tzinfo=UTC),
        ... )
        >>> frame.shape  # doctest: +SKIP
        (1, 2)
        """
        rendered = self._render(start=start, end=end)
        result = reader(rendered, dataframe_backend="pandas")
        if not isinstance(result, DataFrame):
            msg = f"LiveData requires a pandas reader; got {type(result).__name__}"
            raise TypeError(msg)

        return result

    def _refresh_aggregations(
        self,
    ) -> dict[str, DataFrame]:
        """
        Recompute every registered aggregation against :attr:`data`.

        Walks :attr:`aggregations` in insertion order, invoking each
        callable with the latest cached frame and caching the output
        under the same key on :attr:`aggregated_data`. Running this
        after every successful refresh keeps derived views consistent
        with the underlying data without requiring consumers to
        manage dependencies themselves.

        Returns
        -------
            Freshly computed aggregation outputs keyed by the name
            under which each callable was registered. Also assigned
            to :attr:`aggregated_data`.

        See Also
        --------
        LiveData._update : Triggers aggregation refreshes after delta pulls.
        LiveData._initialise : Primes :attr:`aggregated_data` on construction.
        pandas.DataFrame : Frame passed to each registered callable.

        Examples
        --------
        >>> from mayutils.data.live import LiveData
        >>> from mayutils.objects.datetime import DateTime, UTC
        >>> live = LiveData(  # doctest: +SKIP
        ...     "SELECT created_at, day FROM t",
        ...     reader=engine.read_pandas,
        ...     index_column="created_at",
        ...     start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
        ...     rolling=False,
        ...     aggregations={"by_day": lambda df: df.groupby("day").size().to_frame("n")},
        ... )
        >>> outputs = live._refresh_aggregations()  # doctest: +SKIP
        >>> sorted(outputs)  # doctest: +SKIP
        ['by_day']
        >>> outputs["by_day"].shape  # doctest: +SKIP
        (2, 1)
        """
        self.aggregated_data = {name: aggregation(self.data) for name, aggregation in self.aggregations.items()}

        return self.aggregated_data

    def _update(
        self,
        *,
        now: DateTime,
        reader: QueryReader,
    ) -> None:
        """
        Pull the delta between the previous window end and ``now``.

        Constructs the next interval relative to ``now``: for rolling
        instances the window width is preserved by anchoring
        ``new_interval.start`` to ``now - current_width``; otherwise
        the original start is kept and only the end advances. Rows
        older than the new start are dropped from the cache first;
        then the query is rendered for ``[previous_end, now]`` and
        any returned rows are concatenated onto :attr:`data`.
        Aggregations and :attr:`interval` are refreshed only when new
        rows arrive, so a no-op pull leaves the instance unchanged.

        Parameters
        ----------
        now
            Upper bound of the new window; captured once so all
            timestamp substitutions agree for this refresh.
        reader
            Callable used for this pull; may differ from
            :attr:`reader` when a caller supplies an override.

        See Also
        --------
        LiveData.update : Public, rate-limited entry point that invokes this method.
        LiveData._read_window : Issues the delta query.
        LiveData._refresh_aggregations : Re-runs derived views after a successful pull.
        mayutils.objects.datetime.Interval : Represents the refreshed window.

        Examples
        --------
        >>> from mayutils.data.live import LiveData
        >>> from mayutils.objects.datetime import DateTime, UTC
        >>> live = LiveData(  # doctest: +SKIP
        ...     "SELECT * FROM t WHERE c BETWEEN '{start_timestamp}' AND '{end_timestamp}'",
        ...     reader=engine.read_pandas,
        ...     index_column="created_at",
        ...     start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
        ...     rolling=False,
        ... )
        >>> live._update(now=DateTime.now(), reader=live.reader)  # doctest: +SKIP
        >>> live.data.shape  # doctest: +SKIP
        (2, 2)
        """
        previous_end = self.interval.end
        new_start = (now - self.interval.as_duration()) if self.rolling else self.interval.start
        new_interval = Interval(
            start=new_start,
            end=now,
        )

        if self.rolling and not self.empty:
            self.data = self.data.loc[self.data[self.index_column] >= new_start.naive()]

        additional_data = self._read_window(
            reader=reader,
            start=previous_end,
            end=now,
        )

        if not additional_data.empty:
            self.data = additional_data if self.empty else pd.concat([self.data, additional_data])
            self.empty = False
            self._refresh_aggregations()

        self.interval = new_interval

    def update(
        self,
        *,
        reader: QueryReader | None = None,
        force: bool = False,
    ) -> Self:
        """
        Refresh the cached DataFrame with rows that arrived since the last pull.

        Honours the rate-limit imposed by :attr:`update_frequency`:
        when the wall-clock time since the previous pull is smaller
        than the configured duration, the call is a no-op unless
        ``force`` is set. When a pull does occur, new rows are
        appended (and, for rolling instances, stale rows discarded)
        via :meth:`_update`, and aggregations are recomputed against
        the refreshed frame.

        Parameters
        ----------
        reader
            One-off override for this refresh. When ``None``, the
            stored :attr:`reader` is used. Does not replace the
            stored value for future calls.
        force
            Bypass the :attr:`update_frequency` gate and pull
            unconditionally.

        Returns
        -------
            The instance itself, to support method chaining.

        See Also
        --------
        LiveData._update : Performs the underlying delta pull.
        LiveData.reset : Re-seeds the window rather than extending it.
        mayutils.data.read.QueryReader : Protocol for the optional reader override.
        pandas.DataFrame : Frame mutated in-place during the refresh.

        Examples
        --------
        >>> from mayutils.data.live import LiveData
        >>> from mayutils.objects.datetime import DateTime, UTC
        >>> live = LiveData(  # doctest: +SKIP
        ...     "SELECT * FROM t WHERE c BETWEEN '{start_timestamp}' AND '{end_timestamp}'",
        ...     reader=engine.read_pandas,
        ...     index_column="created_at",
        ...     start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
        ...     rolling=False,
        ... )
        >>> _ = live.update()  # doctest: +SKIP
        >>> _ = live.update(force=True)  # doctest: +SKIP
        >>> live.data.shape  # doctest: +SKIP
        (3, 2)
        """
        now = DateTime.now()
        effective_reader = reader if reader is not None else self.reader

        if force or self.update_frequency is None or ((now - self.interval.end) > self.update_frequency):
            self._update(
                now=now,
                reader=effective_reader,
            )

        return self

    def reset(
        self,
        *,
        start_timestamp: DateTime | None = None,
    ) -> Self:
        """
        Re-seed the instance with a fresh pull.

        Invokes :meth:`_initialise` with the existing configuration
        (query, reader, index column, rolling mode, aggregations,
        update frequency and format kwargs), rebuilding :attr:`data`,
        :attr:`aggregated_data` and :attr:`interval` from scratch.
        Useful when a long-running process suspects the cache has
        diverged from the source or when the caller wants to move to
        a different window lower bound without recreating the
        instance.

        Parameters
        ----------
        start_timestamp
            Lower bound for the new window. When ``None``, the
            current :attr:`interval.start` is reused, so the reset
            refreshes the existing window rather than moving it.

        Returns
        -------
            The instance itself, to support chaining.

        See Also
        --------
        LiveData._initialise : Shared seeding path invoked here.
        LiveData.update : Incremental alternative when a full reset is not needed.
        mayutils.objects.datetime.DateTime : Type of the optional lower bound.
        pandas.DataFrame : Frame fully recomputed by this method.

        Examples
        --------
        >>> from mayutils.data.live import LiveData
        >>> from mayutils.objects.datetime import DateTime, UTC
        >>> live = LiveData(  # doctest: +SKIP
        ...     "SELECT * FROM t WHERE c BETWEEN '{start_timestamp}' AND '{end_timestamp}'",
        ...     reader=engine.read_pandas,
        ...     index_column="created_at",
        ...     start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
        ...     rolling=False,
        ... )
        >>> _ = live.reset()  # doctest: +SKIP
        >>> _ = live.reset(start_timestamp=DateTime(2026, 1, 5, tzinfo=UTC))  # doctest: +SKIP
        >>> live.interval.start.date().isoformat()  # doctest: +SKIP
        '2026-01-05'
        """
        self._initialise(
            self.query,
            reader=self.reader,
            index_column=self.index_column,
            start_timestamp=start_timestamp or self.interval.start,
            rolling=self.rolling,
            aggregations=self.aggregations,
            update_frequency=self.update_frequency,
            time_format=self.time_format,
            queries_folders=self.queries_folders,
            **self.format_kwargs,
        )

        return self


__all__ = [
    "LiveData",
]
