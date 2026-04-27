"""
Provide query execution with templating, caching and pluggable readers.

This module is the canonical entry point for reading the result of a
named or inline SQL query into a DataFrame. Query resolution runs
through :func:`mayutils.data.queries.format_query` when ``query`` is a
:class:`~pathlib.Path` and through :meth:`str.format` when ``query`` is
a raw template :class:`str`, so the same interface serves both
filesystem templates and inline SQL. The underlying database
connectivity is abstracted behind the :class:`QueryReader` protocol so
that pandas, polars and bespoke adapters (Snowflake, Redash, fixture
stubs) can be swapped without changing call sites. Caching is opt-in
and layered across a process-wide in-memory store and a persistent
:class:`~mayutils.interfaces.filetypes.DataFile`-backed tier, with TTL
eviction and ``cache_extra`` key extension for non-template execution
parameters.

See Also
--------
mayutils.data.queries : Filesystem lookup and templating of SQL files.
mayutils.environment.databases : Engine wrappers exposing ``read_pandas``.
mayutils.environment.memoisation : Cache key hashing and expiry helpers.
mayutils.interfaces.filetypes : ``DataFile`` registry used by the
    persistent cache tier.
pandas.read_sql : Underlying pandas primitive most readers wrap.
pandas.read_csv : Alternative bulk reader for cached CSV artefacts.

Examples
--------
>>> from mayutils.data.read import read_query
>>> df = read_query(  # doctest: +SKIP
...     "SELECT * FROM loans WHERE product = {product!r}",
...     reader=engine.read_pandas,
...     cache="memory",
...     product="personal",
... )
>>> df.shape  # doctest: +SKIP
(3, 1)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, overload, runtime_checkable

from mayutils.data import CACHE_FOLDER
from mayutils.data.queries import QUERIES_FOLDERS, format_query
from mayutils.environment.filesystem import is_file_stale
from mayutils.environment.memoisation import (
    expiry,
    is_expired,
    make_cache_key,
    register_datafile,
)
from mayutils.interfaces.filetypes import DataFile

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    import polars as pl
    from pandas import DataFrame

    from mayutils.objects.dataframes import DataframeBackends, DataFrames
    from mayutils.objects.datetime import DateTime, Duration
    from mayutils.objects.types import SupportsStr


@runtime_checkable
class QueryReader(Protocol):
    """
    Define the structural contract for executing a rendered query string.

    A reader is any callable with the signature
    ``(str, *, dataframe_backend: DataframeBackends = "pandas") ->
    DataFrames``. The ``dataframe_backend`` keyword lets a single
    reader service both pandas and polars call sites, and keeps
    :func:`read_query` honest — the cold-read branch materialises the
    requested backend via the reader, and the warm-read branch
    materialises the same backend via the :class:`DataFile` cache, so
    the two paths cannot disagree. Simple single-backend callables
    (such as today's
    :meth:`mayutils.environment.databases.EngineWrapper.read_pandas`
    which only returns pandas) can be lifted to the protocol via
    :func:`as_query_reader`. Bespoke readers — an HTTP wrapper around
    Redash, a preconfigured partial over a Snowflake connector, a
    fixtures-backed stub for tests — implement ``__call__`` directly.

    See Also
    --------
    as_query_reader : Lift a single-backend callable to this protocol.
    read_query : Main consumer of :class:`QueryReader` instances.
    mayutils.environment.databases.EngineWrapper.read_pandas : Typical
        concrete reader satisfying the protocol.
    pandas.read_sql : Underlying pandas primitive most readers wrap.

    Examples
    --------
    Any callable matching the protocol signature is a valid reader:

    >>> from mayutils.data.read import QueryReader
    >>> def my_reader(query, /, *, dataframe_backend="pandas"):  # doctest: +SKIP
    ...     return engine.read_pandas(query)
    >>> isinstance(my_reader, QueryReader)  # doctest: +SKIP
    True
    """

    def __call__(
        self,
        query: str,
        /,
        *,
        dataframe_backend: DataframeBackends = "pandas",
    ) -> DataFrames:
        """
        Execute the rendered query and return the result as a DataFrame.

        The callable is invoked by :func:`read_query` exactly once on
        every cache miss, with the fully-rendered SQL already produced
        by :func:`render_query`. Implementations are free to open and
        close their own connections, apply warehouse-level session
        parameters, or route to bespoke transports; they simply need
        to honour the requested ``dataframe_backend`` so the warm and
        cold code paths materialise identical types.

        Parameters
        ----------
        query
            Fully-rendered SQL query string ready to be dispatched to
            the backing database, API or fixture source. Any
            templating has already been applied by the caller.
        dataframe_backend
            DataFrame library the result should be materialised in.
            Implementations that support only one backend should
            raise :class:`NotImplementedError` rather than silently
            returning the wrong type.

        Returns
        -------
            Materialised query result; concrete type matches
            ``dataframe_backend``.

        See Also
        --------
        as_query_reader : Lift a single-backend callable to this
            protocol.
        read_query : Main consumer that calls this method on misses.
        mayutils.environment.databases.EngineWrapper.read_pandas :
            Reference implementation.
        pandas.read_sql : Underlying pandas primitive most readers
            wrap.

        Examples
        --------
        >>> from mayutils.data.read import as_query_reader
        >>> reader = as_query_reader(engine.read_pandas)  # doctest: +SKIP
        >>> df = reader(  # doctest: +SKIP
        ...     "SELECT * FROM loans LIMIT 5",
        ...     dataframe_backend="pandas",
        ... )
        >>> df.shape  # doctest: +SKIP
        (5, 1)
        """
        ...


CacheMode = Literal["memory", "persistent"]
"""Literal set naming the supported caching strategies for :func:`read_query`."""


def as_query_reader(
    fn: Callable[[str], DataFrames],
    /,
    *,
    backend: DataframeBackends = "pandas",
) -> QueryReader:
    """
    Lift a single-backend ``(str) -> DataFrame`` callable to a :class:`QueryReader`.

    Convenience adapter for readers that only service one backend —
    for example :meth:`mayutils.environment.databases.EngineWrapper.read_pandas`,
    which always returns a pandas DataFrame — so they can be plugged
    into :func:`read_query`. The returned wrapper accepts the
    standard ``dataframe_backend`` keyword and raises
    :class:`NotImplementedError` when invoked with a backend other
    than the one ``fn`` supports, which is noisier than returning the
    wrong type and easier to diagnose than a silent failure deep in
    the caching layer. The adapter adds no state of its own and so is
    safe to recreate per call or bind once at module import.

    Parameters
    ----------
    fn
        Backend-fixed query executor taking a rendered SQL string
        and returning a DataFrame.
    backend
        The backend ``fn`` produces. The returned reader will only
        accept this value for ``dataframe_backend``.

    Returns
    -------
        Callable satisfying :class:`QueryReader`, with
        ``dataframe_backend`` routed to ``fn`` when it matches
        ``backend`` and raising otherwise.

    See Also
    --------
    QueryReader : Protocol satisfied by the returned callable.
    read_query : Main consumer of :class:`QueryReader` instances.
    render_query : Helper that produces the string passed to ``fn``.
    mayutils.environment.databases.EngineWrapper.read_pandas : Typical
        ``fn`` passed to this helper.
    pandas.read_sql : Underlying primitive often wrapped by ``fn``.

    Examples
    --------
    >>> from mayutils.data.read import as_query_reader, read_query
    >>> reader = as_query_reader(engine.read_pandas)  # doctest: +SKIP
    >>> df = read_query(  # doctest: +SKIP
    ...     "SELECT 1 AS n",
    ...     reader=reader,
    ... )
    >>> df.shape  # doctest: +SKIP
    (1, 1)
    """

    def reader(
        query: str,
        /,
        *,
        dataframe_backend: DataframeBackends = "pandas",
    ) -> DataFrames:
        """
        Dispatch ``query`` through ``fn`` when the requested backend matches.

        Acts as the closure returned by :func:`as_query_reader`,
        enforcing that ``fn`` is only invoked with the backend it
        advertises. Any other backend value raises
        :class:`NotImplementedError` so misconfigured call sites fail
        loudly at the reader boundary rather than later inside
        :class:`DataFile` deserialisation.

        Parameters
        ----------
        query
            Fully rendered SQL string to execute.
        dataframe_backend
            DataFrame backend requested by :func:`read_query`. Must
            equal the ``backend`` captured from the enclosing
            :func:`as_query_reader` call.

        Returns
        -------
            Result produced by ``fn(query)``; concrete type matches
            the single backend supported by the adapter.

        Raises
        ------
        NotImplementedError
            When ``dataframe_backend`` differs from the captured
            ``backend``.

        See Also
        --------
        as_query_reader : Factory that produces this closure.
        QueryReader : Protocol satisfied by the returned callable.
        pandas.read_sql : Primitive commonly wrapped by ``fn``.

        Examples
        --------
        >>> from mayutils.data.read import as_query_reader
        >>> reader = as_query_reader(engine.read_pandas)  # doctest: +SKIP
        >>> df = reader("SELECT 1", dataframe_backend="pandas")  # doctest: +SKIP
        >>> df.shape  # doctest: +SKIP
        (1, 1)
        """
        if dataframe_backend != backend:
            msg = f"Reader supports '{backend}' only; got '{dataframe_backend}'"
            raise NotImplementedError(msg)
        return fn(query)

    return reader


MEMORY_CACHE: dict[str, tuple[DateTime | None, object]] = {}
"""Process-wide in-memory cache used when ``cache="memory"`` is active.

Keys are the digest computed by :func:`make_cache_key` over the
rendered query and any ``cache_extra`` payload; values are
``(expires_at, dataframe)`` tuples with the expiry set according to
the supplied ``ttl``. The store is shared across calls but segmented
by the key digest, so unrelated invocations cannot collide.
"""


def render_query(
    query: str | Path,
    /,
    *,
    queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
    **format_kwargs: str,
) -> str:
    r"""
    Render a query template to a concrete SQL string.

    The behaviour depends on the runtime type of ``query``. A
    :class:`~pathlib.Path` is resolved against ``queries_folders`` via
    :func:`mayutils.data.queries.format_query`, which reads the
    template from disk and applies :meth:`str.format` with
    ``format_kwargs``. A :class:`str` is treated as an inline template
    and rendered directly via :meth:`str.format` when ``format_kwargs``
    is non-empty, or returned verbatim otherwise. Keeping both paths
    behind a single helper means :func:`read_query`, its caching
    logic, and any bespoke pre-processing agree on exactly one string
    to hash and to execute.

    Parameters
    ----------
    query : pathlib.Path or str
        Either the identifier of a bundled query template (use
        :class:`~pathlib.Path` to opt in to filesystem lookup) or a
        raw SQL template with ``{name}`` placeholders.
    queries_folders : tuple[pathlib.Path, ...], optional
        Search path forwarded to :func:`format_query` when
        resolving path-typed queries. Defaults to
        :data:`mayutils.data.queries.QUERIES_FOLDERS`.
    **format_kwargs : SupportsStr
        Keyword substitutions applied to the template. Every value
        must be stringifiable; Python inserts
        ``str(value)`` at each matching ``{name}`` placeholder.

    Returns
    -------
    str
        Fully rendered SQL string ready to be dispatched through a
        :class:`QueryReader`.

    See Also
    --------
    read_query : Primary caller that renders then executes the query.
    mayutils.data.queries.format_query : Filesystem lookup and
        templating backend.
    mayutils.environment.databases : Engines that consume the rendered
        string.
    pandas.read_sql : Primitive that ultimately executes the rendered
        query.

    Examples
    --------
    >>> from mayutils.data.read import render_query
    >>> render_query("SELECT * FROM {table}", table="loans")
    'SELECT * FROM loans'
    >>> render_query(
    ...     "SELECT * FROM {table} WHERE product = {product!r}",
    ...     table="loans",
    ...     product="personal",
    ... )
    "SELECT * FROM loans WHERE product = 'personal'"
    """
    if isinstance(query, Path):
        return format_query(
            query,
            queries_folders=queries_folders,
            **format_kwargs,
        )

    return query.format(**format_kwargs)


@overload
def read_query(  # numpydoc ignore=GL08
    query: str | Path,
    *,
    reader: QueryReader,
    cache: bool | CacheMode = False,
    ttl: Duration | None = None,
    cache_extra: Mapping[str, object] | None = None,
    cache_folder: Path | str = CACHE_FOLDER,
    cache_suffix: str = "parquet",
    dataframe_backend: Literal["pandas"] = "pandas",
    queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
    **format_kwargs: SupportsStr,
) -> DataFrame: ...


@overload
def read_query(  # numpydoc ignore=GL08
    query: str | Path,
    *,
    reader: QueryReader,
    cache: bool | CacheMode = False,
    ttl: Duration | None = None,
    cache_extra: Mapping[str, object] | None = None,
    cache_folder: Path | str = CACHE_FOLDER,
    cache_suffix: str = "parquet",
    dataframe_backend: Literal["polars"],
    queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
    **format_kwargs: SupportsStr,
) -> pl.DataFrame: ...


@overload
def read_query(  # numpydoc ignore=GL08
    query: str | Path,
    *,
    reader: QueryReader,
    cache: bool | CacheMode = False,
    ttl: Duration | None = None,
    cache_extra: Mapping[str, object] | None = None,
    cache_folder: Path | str = CACHE_FOLDER,
    cache_suffix: str = "parquet",
    dataframe_backend: DataframeBackends,
    queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
    **format_kwargs: SupportsStr,
) -> DataFrames: ...


def read_query(
    query: str | Path,
    *,
    reader: QueryReader,
    cache: bool | CacheMode = False,
    ttl: Duration | None = None,
    cache_extra: Mapping[str, object] | None = None,
    cache_folder: Path | str = CACHE_FOLDER,
    cache_suffix: str = "parquet",
    dataframe_backend: DataframeBackends = "pandas",
    queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
    **format_kwargs: SupportsStr,
) -> DataFrames:
    """
    Render a query, dispatch it through a reader, and optionally cache the result.

    The query is first rendered via :func:`render_query` so file
    templates and inline strings share the same entry point. When
    ``cache`` is falsy the rendered query is handed straight to
    ``reader``. Otherwise a cache key is computed via
    :func:`mayutils.environment.memoisation.make_cache_key` over the
    rendered query and any ``cache_extra`` payload, and the key is
    looked up through the cache tier selected by ``cache`` — either
    the process-wide :data:`MEMORY_CACHE` dictionary with lazy TTL
    eviction, or a file under
    ``cache_folder / read_query / <key>.<cache_suffix>`` written and
    read through the :class:`~mayutils.interfaces.filetypes.DataFile`
    registry with staleness determined against
    ``path.stat().st_mtime``. On persistent misses the result is both
    returned and written through :class:`DataFile` so later calls can
    warm-read without touching the database.

    Parameters
    ----------
    query : pathlib.Path or str
        Identifier of a template file (Path) or an inline SQL
        template (str). Path inputs are resolved against
        ``queries_folders`` via :func:`format_query`; string inputs
        are passed through :meth:`str.format` with ``format_kwargs``.
    reader : QueryReader
        Callable implementing ``(str) -> DataFrames``. The rendered
        query is dispatched through ``reader`` on every miss.
    cache : bool or {"memory", "persistent"}, optional
        Caching strategy. ``False`` disables caching entirely.
        ``True`` is normalised to ``"memory"``. ``"memory"`` uses the
        process-wide in-memory store; ``"persistent"`` writes through
        the :class:`DataFile` registry.
    ttl : Duration or None, optional
        Lifetime of the cache entry. Entries older than ``ttl`` are
        treated as stale on the next lookup. ``None`` disables
        expiry.
    cache_extra : Mapping[str, object] or None, optional
        Additional values to fold into the cache key alongside the
        rendered query. Use this for non-template parameters that
        still influence execution (``{"schema": "prod"}``,
        ``{"warehouse": "analytics_m"}``, etc.).
    cache_folder : pathlib.Path or str, optional
        Root directory for the persistent cache files. Defaults to
        :data:`CACHE_FOLDER`.
    cache_suffix : str, optional
        File extension controlling the persistent cache format, with
        or without a leading ``"."``. Any suffix registered on
        :class:`DataFile` works (``"parquet"``, ``"csv"``,
        ``"feather"``, ...). Defaults to ``"parquet"``.
    dataframe_backend : {"pandas", "polars"}, optional
        DataFrame library to materialise the result in. Propagated
        to ``reader`` on cache misses and to :class:`DataFile` on
        persistent-cache hits so both paths return the matching
        backend.
    queries_folders : tuple[pathlib.Path, ...], optional
        Search path forwarded to :func:`format_query` for path
        lookups. Defaults to :data:`QUERIES_FOLDERS`.
    **format_kwargs : SupportsStr
        Keyword substitutions applied to the template via
        :meth:`str.format`.

    Returns
    -------
    pandas.DataFrame or polars.DataFrame
        Materialised query result, either served from the cache or
        freshly computed. Concrete type always matches
        ``dataframe_backend`` — the reader is invoked with that
        keyword on cache misses, and the :class:`DataFile` cache is
        read with the same backend on hits.

    See Also
    --------
    render_query : Template rendering step shared by every call.
    as_query_reader : Lift a single-backend callable to the
        :class:`QueryReader` protocol.
    clear_memory_cache : Drop the process-wide in-memory cache.
    is_file_stale : TTL check used by the persistent cache tier.
    mayutils.data.queries.format_query : Resolves path-typed queries.
    mayutils.environment.databases.EngineWrapper.read_pandas : Common
        ``reader`` argument.
    mayutils.environment.memoisation.make_cache_key : Produces the
        digest that keys both cache tiers.
    mayutils.interfaces.filetypes.DataFile : Persistent cache
        serialiser.
    pandas.read_sql : Underlying pandas primitive most readers wrap.
    pandas.read_csv : Alternative pandas primitive for CSV payloads.

    Examples
    --------
    Execute an inline query without caching:

    >>> from mayutils.data.read import read_query
    >>> df = read_query(  # doctest: +SKIP
    ...     "SELECT * FROM loans WHERE product = {product!r}",
    ...     reader=engine.read_pandas,
    ...     product="personal",
    ... )
    >>> df.shape  # doctest: +SKIP
    (1000, 15)

    Use the in-memory cache with a TTL:

    >>> from mayutils.objects.datetime import Duration
    >>> df = read_query(  # doctest: +SKIP
    ...     "SELECT volume FROM daily_volume",
    ...     reader=engine.read_pandas,
    ...     cache="memory",
    ...     ttl=Duration(hours=6),
    ... )

    Use persistent (file-backed) caching:

    >>> df = read_query(  # doctest: +SKIP
    ...     "SELECT COUNT(*) AS n FROM loans WHERE status = {status!r}",
    ...     reader=engine.read_pandas,
    ...     cache="persistent",
    ...     ttl=Duration(hours=1),
    ...     cache_extra={"warehouse": "analytics_m"},
    ...     status="active",
    ... )
    """
    rendered = render_query(
        query,
        queries_folders=queries_folders,
        **format_kwargs,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
    )

    if cache is False:
        return reader(rendered, dataframe_backend=dataframe_backend)

    cache_mode: CacheMode = "memory" if cache is True else cache

    key = make_cache_key(
        read_query.__name__,
        args=(rendered,),
        kwargs={
            "cache_extra": dict(cache_extra) if cache_extra else {},
            "dataframe_backend": dataframe_backend,
        },
    )

    if cache_mode == "memory":
        entry = MEMORY_CACHE.get(key)
        if entry is not None:
            expires_at, cached = entry
            if not is_expired(expires_at):
                return cached
            del MEMORY_CACHE[key]

        result = reader(rendered, dataframe_backend=dataframe_backend)
        MEMORY_CACHE[key] = (expiry(ttl), result)
        return result

    suffix = cache_suffix if cache_suffix.startswith(".") else f".{cache_suffix}"
    register_datafile(suffix)
    path = Path(cache_folder) / read_query.__name__ / f"{key}{suffix}"

    if path.is_file() and not is_file_stale(path, ttl=ttl):
        return DataFile.from_path(
            path,
            backend=dataframe_backend,
        ).read()

    result = reader(rendered, dataframe_backend=dataframe_backend)
    path.parent.mkdir(parents=True, exist_ok=True)
    DataFile.from_path(
        path,
        backend=dataframe_backend,
    ).write(result)

    return result


def clear_memory_cache() -> None:
    """
    Empty the process-wide in-memory query cache.

    Clears :data:`MEMORY_CACHE` outright rather than evicting by key,
    so every prior ``cache="memory"`` result becomes cold. Useful in
    tests and long-running interactive sessions after the underlying
    data has changed but neither the rendered query text nor the
    ``cache_extra`` payload can be adjusted to invalidate the key
    naturally. The persistent cache tier is untouched; prune it by
    deleting files under the configured ``cache_folder``.

    See Also
    --------
    read_query : Populates the cache this helper clears.
    is_file_stale : TTL check used by the persistent cache tier.
    mayutils.environment.memoisation.expiry : Produces the stored
        ``expires_at`` timestamps.
    pandas.read_sql : Underlying pandas primitive most readers wrap.

    Examples
    --------
    >>> from mayutils.data.read import (
    ...     MEMORY_CACHE,
    ...     clear_memory_cache,
    ...     read_query,
    ... )
    >>> _ = read_query("SELECT 1", reader=engine.read_pandas, cache="memory")  # doctest: +SKIP
    >>> len(MEMORY_CACHE) > 0  # doctest: +SKIP
    True
    >>> clear_memory_cache()
    >>> len(MEMORY_CACHE)
    0
    """
    MEMORY_CACHE.clear()


__all__ = [
    "CacheMode",
    "QueryReader",
    "as_query_reader",
    "clear_memory_cache",
    "read_query",
    "render_query",
]
