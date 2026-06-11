"""
Provide query execution with templating, caching and pluggable readers.

This module is the canonical entry point for reading the result of a
named or inline SQL query into a DataFrame. Query resolution runs
through :func:`mayutils.data.queries.format_query` when ``query`` is a
:class:`~pathlib.Path` and through
:func:`mayutils.data.queries.templating.render_template` when ``query``
is a raw Jinja template :class:`str`, so the same interface serves both
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
...     "SELECT * FROM loans WHERE product = '{{ product }}'",
...     reader=engine.read_pandas,
...     cache=True,
...     template_kwargs={"product": "personal"},
... )
>>> df.shape  # doctest: +SKIP
(3, 1)
"""

from __future__ import annotations

import re
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from mayutils.core.extras import may_require_extras
from mayutils.data import CACHE_FOLDER
from mayutils.data.queries import QUERIES_FOLDERS, format_query
from mayutils.data.queries.templating import render_template
from mayutils.environment.logging import Logger
from mayutils.environment.memoisation import cache, make_cache_stem
from mayutils.objects.dataframes.backends import Backend, DataFrames, default_backend
from mayutils.objects.dataframes.temporal import parse_temporal_columns

with may_require_extras():
    import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from mayutils.objects.datetime import Duration
    from mayutils.objects.types import SQL


logger = Logger.spawn()


@runtime_checkable
class QueryReader(Protocol):
    """
    Structural contract for callables that execute SQL into a DataFrame.

    Implementations accept a fully-rendered SQL string plus an optional
    backend token and return the materialised result in the requested
    DataFrame flavour. Engine wrappers such as
    :meth:`mayutils.environment.databases.EngineWrapper.to_reader`
    produce conforming callables, which :func:`read_query` consumes.

    See Also
    --------
    read_query : Consumer that dispatches rendered SQL through a reader.
    QueryStreamer : Streaming counterpart yielding chunked results.

    Examples
    --------
    >>> from mayutils.data.read import QueryReader
    >>> QueryReader
    <class 'mayutils.data.read.QueryReader'>
    """

    def __call__[DataFrameType: DataFrames = pd.DataFrame](
        self,
        query: str,
        /,
        *,
        backend: Backend[DataFrameType] | None = None,
    ) -> DataFrameType:
        """
        Execute the query and return the materialised result.

        Invoked by :func:`read_query` with the fully-rendered SQL string
        and the backend token selecting the DataFrame flavour.

        Parameters
        ----------
        query
            Fully-rendered SQL string ready for execution.
        backend
            DataFrame backend token. Defaults to pandas when ``None``.

        Returns
        -------
            Materialised query result.

        See Also
        --------
        read_query : Consumer that invokes conforming readers.

        Examples
        --------
        >>> from mayutils.data.read import QueryReader
        >>> QueryReader
        <class 'mayutils.data.read.QueryReader'>
        """
        ...


@runtime_checkable
class QueryStreamer(Protocol):
    """
    Structural contract for callables that stream SQL results in chunks.

    Implementations accept a fully-rendered SQL string plus an optional
    backend token and lazily yield the result as DataFrame chunks.
    Engine wrappers such as
    :meth:`mayutils.environment.databases.EngineWrapper.to_streamer`
    produce conforming callables, which :func:`stream_query` consumes.

    See Also
    --------
    stream_query : Consumer that dispatches rendered SQL through a streamer.
    QueryReader : Eager counterpart returning a single DataFrame.

    Examples
    --------
    >>> from mayutils.data.read import QueryStreamer
    >>> QueryStreamer
    <class 'mayutils.data.read.QueryStreamer'>
    """

    def __call__[DataFrameType: DataFrames = pd.DataFrame](
        self,
        query: str,
        /,
        *,
        backend: Backend[DataFrameType] | None = None,
    ) -> Iterator[DataFrameType]:
        """
        Execute the query and return an iterator over result chunks.

        Invoked by :func:`stream_query` with the fully-rendered SQL
        string and the backend token selecting the DataFrame flavour.

        Parameters
        ----------
        query
            Fully-rendered SQL string ready for execution.
        backend
            DataFrame backend token. Defaults to pandas when ``None``.

        Returns
        -------
            Iterator over successive DataFrame chunks of the result.

        See Also
        --------
        stream_query : Consumer that invokes conforming streamers.

        Examples
        --------
        >>> from mayutils.data.read import QueryStreamer
        >>> QueryStreamer
        <class 'mayutils.data.read.QueryStreamer'>
        """
        ...


class QueryExecutor[DataFrameType: DataFrames](Protocol):
    """
    Structural contract for the cacheable query execution closure.

    The closure captures the ``reader`` and ``dataframe_backend`` from
    the enclosing :func:`read_query` call, exposing only the
    cache-key-relevant arguments.

    See Also
    --------
    read_query : Factory that creates closures satisfying this protocol.

    Examples
    --------
    >>> from mayutils.data.read import QueryExecutor
    >>> QueryExecutor
    <class 'mayutils.data.read.QueryExecutor'>
    """

    def __call__(
        self,
        rendered: str,
        /,
        *,
        _extra: dict[str, object] | None = None,
    ) -> DataFrameType:
        """
        Execute the rendered query and return the result.

        Invoked by the caching layer with the fully-rendered SQL string
        and optional extra cache-key metadata.

        Parameters
        ----------
        rendered
            Fully-rendered SQL string ready for execution.
        _extra
            Optional dictionary of additional values included in the
            cache key.

        Returns
        -------
            Materialised query result.

        See Also
        --------
        read_query : Consumer that builds and invokes this closure.

        Examples
        --------
        >>> from mayutils.data.read import QueryExecutor
        >>> QueryExecutor
        <class 'mayutils.data.read.QueryExecutor'>
        """
        ...


class QueryInputWarning(UserWarning):
    """
    Warn when a string passed to :func:`render_query` looks like a file path.

    Emitted by the heuristic in :func:`render_query` when the ``query``
    argument is a :class:`str` (or :data:`~mayutils.objects.types.SQL`)
    that structurally resembles a filesystem path rather than inline SQL.
    The warning gives callers an early signal that they may have forgotten
    to wrap a query-file identifier in :class:`~pathlib.Path`, without
    raising an exception that would break existing code.

    See Also
    --------
    render_query : Function that emits this warning.
    mayutils.objects.types.SQL : NewType distinguishing inline SQL from
        plain :class:`str` at the type level.

    Examples
    --------
    >>> import warnings
    >>> from mayutils.data.read import QueryInputWarning, render_query
    >>> with warnings.catch_warnings(record=True) as w:  # doctest: +SKIP
    ...     warnings.simplefilter("always")
    ...     render_query("my_query.sql")
    ...     assert issubclass(w[0].category, QueryInputWarning)
    """


SQL_KEYWORDS: frozenset[str] = frozenset(
    {
        "ALTER",
        "CALL",
        "CREATE",
        "DECLARE",
        "DELETE",
        "DESCRIBE",
        "DROP",
        "EXEC",
        "EXPLAIN",
        "GRANT",
        "INSERT",
        "MERGE",
        "REVOKE",
        "SELECT",
        "SET",
        "SHOW",
        "TRUNCATE",
        "UPDATE",
        "USE",
        "WITH",
    }
)
"""SQL keywords used by :func:`_looks_like_path` to identify inline SQL."""

SQL_KEYWORD_PATTERN: re.Pattern[str] = re.compile(
    pattern=r"\b(?:" + "|".join(sorted(SQL_KEYWORDS)) + r")\b",
    flags=re.IGNORECASE,
)
"""Compiled pattern matching any :data:`SQL_KEYWORDS` as whole words."""


def looks_like_sql_path(
    value: str,
    /,
    *,
    queries_folders: tuple[Path, ...],
) -> str | None:
    """
    Return a diagnostic message when *value* looks like a file path.

    The check is conservative: it returns ``None`` (no warning) when the
    string contains at least one SQL keyword, regardless of other
    structural indicators. This avoids false positives on queries that
    happen to contain path-separator characters.

    Parameters
    ----------
    value
        The string to inspect.
    queries_folders
        Search directories probed when checking whether ``value``
        resolves to an existing query file.

    Returns
    -------
    str or None
        A human-readable diagnostic if the string looks path-like, or
        ``None`` when no warning is warranted.

    See Also
    --------
    render_query : Caller that converts the diagnostic into a
        :class:`QueryInputWarning`.
    QueryInputWarning : Warning category emitted by the caller.
    mayutils.objects.types.SQL : NewType that avoids ambiguity at the
        type level.

    Examples
    --------
    >>> from mayutils.data.read import looks_like_sql_path
    >>> looks_like_sql_path("SELECT 1", queries_folders=()) is None
    True
    >>> looks_like_sql_path("my_query.sql", queries_folders=()) is not None
    True
    """
    if value.lower().endswith(".sql"):
        return f"String ends with '.sql' — pass Path({value!r}) for file lookup."

    if ("/" in value or "\\" in value) and " " not in value:
        return f"String contains path separators but no SQL keywords — pass Path({value!r}) for file lookup."

    if SQL_KEYWORD_PATTERN.search(string=value):
        return None

    candidate = Path(value)
    for folder in queries_folders:
        for suffix in ("", ".sql"):
            resolved = folder / (candidate.with_suffix(f".{suffix.lstrip('.')}") if suffix else candidate)
            if resolved.is_file():
                return f"String matches query file {resolved} — pass Path({value!r}) for file lookup."

    return None


def render_query(
    query: SQL | Path,
    /,
    *,
    queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
    default_suffix: str = "sql",
    template_kwargs: Mapping[str, object] | None = None,
) -> str:
    r"""
    Render a query template to a concrete SQL string.

    The behaviour depends on the runtime type of ``query``. A
    :class:`~pathlib.Path` is resolved against ``queries_folders`` via
    :func:`mayutils.data.queries.format_query`, which reads the
    template from disk and renders it with Jinja2 using
    ``template_kwargs``. An :data:`~mayutils.objects.types.SQL` string is
    treated as an inline Jinja template and rendered directly via
    :func:`~mayutils.data.queries.templating.render_template`. When a
    plain :class:`str` structurally resembles a file path (detected by
    :func:`looks_like_sql_path`), a :class:`QueryInputWarning` is
    emitted and the string is routed through
    :func:`~mayutils.data.queries.format_query` as if it were a
    :class:`~pathlib.Path`. Keeping both paths behind a single helper
    means :func:`read_query`, its caching logic, and any bespoke
    pre-processing agree on exactly one string to hash and to execute.

    Parameters
    ----------
    query
        Either an inline SQL Jinja template wrapped in
        :data:`~mayutils.objects.types.SQL` with ``{{ name }}``
        placeholders, or a :class:`~pathlib.Path` identifying a
        bundled query template on disk. A plain :class:`str` is
        accepted at runtime for backwards compatibility but will be
        flagged by type checkers; if it structurally resembles a file
        path, a :class:`QueryInputWarning` is emitted.
    queries_folders
        Search path forwarded to :func:`format_query` when
        resolving path-typed queries and to
        :func:`~mayutils.data.queries.templating.render_template` for
        resolving ``{% include %}`` directives in inline templates.
        Defaults to :data:`mayutils.data.queries.QUERIES_FOLDERS`.
    default_suffix
        File extension assumed when *query* is a bare filename
        without a suffix. Forwarded to :func:`format_query`.
    template_kwargs
        Mapping of Jinja2 template variable names to their values.
        When ``None`` or omitted the template is rendered with no
        variables, which is only valid for templates that contain no
        variable references.

    Returns
    -------
    str
        Fully rendered SQL string ready to be dispatched through a
        :class:`QueryReader`.
        :class:`~jinja2.exceptions.UndefinedError` propagates from the
        Jinja2 engine when the template references a variable not
        present in ``template_kwargs``.

    Warns
    -----
    QueryInputWarning
        When ``query`` is a :class:`str` that looks like a file path
        rather than inline SQL.

    See Also
    --------
    read_query : Primary caller that renders then executes the query.
    mayutils.data.queries.format_query : Filesystem lookup and
        templating backend.
    mayutils.data.queries.templating.render_template : Jinja2
        rendering engine used for inline templates.
    mayutils.objects.types.SQL : NewType distinguishing inline SQL
        from plain :class:`str`.
    QueryInputWarning : Warning emitted when the heuristic fires.
    mayutils.environment.databases : Engines that consume the rendered
        string.
    pandas.read_sql : Primitive that ultimately executes the rendered
        query.

    Examples
    --------
    >>> from mayutils.objects.types import SQL
    >>> from mayutils.data.read import render_query
    >>> render_query(SQL("SELECT * FROM {{ table }}"), template_kwargs={"table": "loans"})
    'SELECT * FROM loans'
    >>> render_query(
    ...     SQL("SELECT * FROM {{ table }} WHERE product = '{{ product }}'"),
    ...     template_kwargs={"table": "loans", "product": "personal"},
    ... )
    "SELECT * FROM loans WHERE product = 'personal'"
    """
    diagnostic = looks_like_sql_path(query, queries_folders=queries_folders) if isinstance(query, str) else None
    if diagnostic is not None:
        warnings.warn(
            message=f"render_query received a str that looks like a file path: "
            f"{diagnostic} Wrap in Path() for file lookup or SQL() for inline SQL.",
            category=QueryInputWarning,
            stacklevel=2,
        )
        query = Path(query)

    template_kwargs = dict(template_kwargs or {})

    if isinstance(query, Path):
        logger.debug(f"Rendering query file {query} with arguments {sorted(template_kwargs)}")

        return format_query(
            query,
            queries_folders=queries_folders,
            default_suffix=default_suffix,
            template_kwargs=template_kwargs,
        )

    logger.debug(f"Rendering inline SQL ({len(query)} chars) with arguments {sorted(template_kwargs)}")

    return render_template(
        query,
        queries_folders=queries_folders,
        template_kwargs=template_kwargs,
    )


def read_query[DataFrameType: DataFrames = pd.DataFrame](
    query: SQL | Path,
    /,
    *,
    reader: QueryReader | None = None,
    backend: Backend[DataFrameType] | None = None,
    parse_temporal: bool = True,
    suffix: str | None = None,
    persist: bool | None = False,
    ttl: Duration | None = None,
    cache_extra: Mapping[str, object] | None = None,
    cache_description: str | None = None,
    cache_folder: Path | str = CACHE_FOLDER,
    queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
    default_suffix: str = "sql",
    template_kwargs: Mapping[str, object] | None = None,
) -> DataFrameType:
    r"""
    Execute a SQL query through *reader* with optional caching.

    Renders the query via :func:`render_query`, then either executes it
    directly or wraps the call with a cache depending on *persist*.

    Parameters
    ----------
    query
        SQL string or :class:`~pathlib.Path` to a template file.
    reader
        Callable that executes the rendered SQL and returns a DataFrame.
    backend
        DataFrame backend token. Defaults to pandas when ``None``.
    parse_temporal
        Whether to automatically convert string (and object) columns
        that look like dates, times or datetimes into temporal dtypes
        after the query result materialises. Applied after the cache
        layer, so cached artefacts are also upgraded; parsing is
        idempotent. Disable for strict schema stability.
    suffix
        Cache file extension. ``None`` infers from the result type.
    persist
        ``None`` bypasses caching entirely, ``False`` (the default) uses
        an in-memory cache, and ``True`` persists results to disk.
    ttl
        Time-to-live for cached results.
    cache_extra
        Additional values included in the cache key.
    cache_description
        Human-readable label for the cache filename.
    cache_folder
        Root directory for cache files. Only used when
        ``persist is True``.
    queries_folders
        Directories to search when *query* is a filename.
    default_suffix
        File extension assumed when *query* is a bare filename.
    template_kwargs
        Jinja2 template substitutions forwarded to
        :func:`render_query`.

    Returns
    -------
    DataFrameType
        Query result, possibly served from cache.

    See Also
    --------
    render_query : Template rendering used internally.

    Examples
    --------
    >>> from mayutils.data.read import read_query
    >>> df = read_query(  # doctest: +SKIP
    ...     "SELECT 1 AS n",
    ...     reader=engine.read_pandas,
    ... )
    >>> df.shape  # doctest: +SKIP
    (1, 1)
    """
    if reader is None:
        from mayutils.interfaces.data import get_env_reader

        reader = get_env_reader()

    backend = backend if backend is not None else cast("Backend[DataFrameType]", default_backend())

    rendered_query = render_query(
        query,
        queries_folders=queries_folders,
        default_suffix=default_suffix,
        template_kwargs=template_kwargs,
    )

    logger.debug(f"Executing query ({len(rendered_query)} chars) with backend={backend.name!r} and persist={persist!r}")

    if persist is None:
        result = reader(
            rendered_query,
            backend=backend,
        )

        return parse_temporal_columns(result, backend=backend) if parse_temporal else result

    def execute(
        rendered: str,
        /,
        *,
        _extra: dict[str, object] | None = None,
    ) -> DataFrameType:
        """
        Dispatch the rendered query through the captured reader.

        Closure that delegates to the outer ``reader`` with the captured
        ``backend``, satisfying the :class:`QueryExecutor` protocol.

        Parameters
        ----------
        rendered
            Fully-rendered SQL string.
        _extra
            Optional extra cache-key metadata (unused here but
            required by the protocol).

        Returns
        -------
            Materialised query result from the reader.

        See Also
        --------
        QueryExecutor : Protocol this closure satisfies.

        Examples
        --------
        >>> from mayutils.data.read import read_query
        >>> read_query
        <function read_query at ...>
        """
        return reader(
            rendered,
            backend=backend,
        )

    cached_execute: QueryExecutor[DataFrameType]
    if not persist:
        cached_execute = cast(
            "QueryExecutor[DataFrameType]",
            cache(
                ttl=ttl,
            )(execute),
        )
    else:
        cached_execute = cast(
            "QueryExecutor[DataFrameType]",
            cache(
                suffix=suffix,
                persist=persist,
                cache_folder=cache_folder,
                ttl=ttl,
                backend=backend,
                key_prefix=make_cache_stem(
                    query,
                    cache_description=cache_description,
                    ttl=ttl,
                    template_kwargs=dict(template_kwargs or {}),
                    cache_extra=cache_extra,
                    key="",
                ),
            )(execute),
        )

    result = cached_execute(
        rendered_query,
        _extra=dict(cache_extra) if cache_extra else None,
    )

    return parse_temporal_columns(result, backend=backend) if parse_temporal else result


def stream_query[DataFrameType: DataFrames = pd.DataFrame](
    query: SQL | Path,
    /,
    *,
    streamer: QueryStreamer | None = None,
    backend: Backend[DataFrameType] | None = None,
    parse_temporal: bool = True,
    queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
    default_suffix: str = "sql",
    template_kwargs: Mapping[str, object] | None = None,
) -> Iterator[DataFrameType]:
    r"""
    Stream a SQL query through *streamer* in DataFrame chunks.

    Renders the query via :func:`render_query` and lazily yields the
    chunks produced by *streamer*. No caching is applied; each chunk is
    forwarded as soon as the underlying driver produces it, keeping
    peak memory bounded for large result sets. Temporal parsing is
    applied to each chunk independently, so the inferred temporal kinds
    can differ between chunks; pass ``parse_temporal=False`` for strict
    schema stability across chunks.

    Parameters
    ----------
    query
        SQL string or :class:`~pathlib.Path` to a template file.
    streamer
        Callable that executes the rendered SQL and yields DataFrame
        chunks.
    backend
        DataFrame backend token. Defaults to pandas when ``None``.
    parse_temporal
        Whether to automatically convert string (and object) columns
        that look like dates, times or datetimes into temporal dtypes
        in each yielded chunk. Chunks are parsed independently, so the
        inferred kinds can differ between chunks; parsing is
        idempotent. Disable for strict schema stability.
    queries_folders
        Directories to search when *query* is a filename.
    default_suffix
        File extension assumed when *query* is a bare filename.
    template_kwargs
        Jinja2 template substitutions forwarded to
        :func:`render_query`.

    Yields
    ------
        Successive DataFrame chunks of the query result.

    See Also
    --------
    read_query : Eager counterpart returning a single DataFrame.
    render_query : Template rendering used internally.
    QueryStreamer : Protocol the *streamer* argument must satisfy.

    Examples
    --------
    >>> import pandas as pd
    >>> from mayutils.data.read import stream_query
    >>> from mayutils.objects.types import SQL
    >>> def streamer(query, /, *, backend=None):
    ...     yield pd.DataFrame({"n": [1]})
    >>> chunks = list(stream_query(SQL("SELECT 1 AS n"), streamer=streamer))
    >>> chunks[0].shape
    (1, 1)
    """
    if streamer is None:
        from mayutils.interfaces.data import get_env_streamer

        streamer = get_env_streamer()

    backend = backend if backend is not None else cast("Backend[DataFrameType]", default_backend())

    rendered_query = render_query(
        query,
        queries_folders=queries_folders,
        default_suffix=default_suffix,
        template_kwargs=template_kwargs,
    )

    logger.debug(f"Streaming query ({len(rendered_query)} chars) with backend={backend.name!r}")

    for chunk in streamer(
        rendered_query,
        backend=backend,
    ):
        yield parse_temporal_columns(chunk, backend=backend) if parse_temporal else chunk


def read_queries[DataFrameType: DataFrames = pd.DataFrame](
    queries: Sequence[SQL | Path],
    /,
    *,
    reader: QueryReader,
    backend: Backend[DataFrameType] | None = None,
    parse_temporal: bool = True,
    suffix: str | None = None,
    persist: bool | None = False,
    ttl: Duration | None = None,
    cache_extra: Mapping[str, object] | None = None,
    cache_description: str | None = None,
    cache_folder: Path | str = CACHE_FOLDER,
    queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
    default_suffix: str = "sql",
    max_workers: int = 4,
    template_kwargs: Mapping[str, object] | None = None,
) -> tuple[DataFrameType, ...]:
    r"""
    Execute multiple SQL queries concurrently through *reader*.

    Fans the queries out across a
    :class:`~concurrent.futures.ThreadPoolExecutor`, delegating each one
    to :func:`read_query` with the shared caching and templating
    configuration. Results are returned in the same order as the input
    queries regardless of completion order.

    Parameters
    ----------
    queries
        Sequence of SQL strings or template file paths, each accepted in
        the same forms as the ``query`` argument of :func:`read_query`.
    reader
        Callable that executes each rendered SQL string and returns a
        DataFrame.
    backend
        DataFrame backend token. Defaults to pandas when ``None``.
    parse_temporal
        Whether to automatically convert string (and object) columns
        that look like dates, times or datetimes into temporal dtypes
        in each query result. Forwarded to every :func:`read_query`
        call; applied after the cache layer, so cached artefacts are
        also upgraded. Disable for strict schema stability.
    suffix
        Cache file extension. ``None`` infers from the result type.
    persist
        ``None`` bypasses caching entirely, ``False`` (the default) uses
        an in-memory cache, and ``True`` persists results to disk.
    ttl
        Time-to-live for cached results.
    cache_extra
        Additional values included in the cache keys.
    cache_description
        Human-readable label for the cache filenames.
    cache_folder
        Root directory for cache files. Only used when
        ``persist is True``.
    queries_folders
        Directories to search when a query is a filename.
    default_suffix
        File extension assumed when a query is a bare filename.
    max_workers
        Maximum number of worker threads executing queries in parallel.
    template_kwargs
        Jinja2 template substitutions forwarded to every
        :func:`read_query` call.

    Returns
    -------
        Query results in the same order as ``queries``.

    See Also
    --------
    read_query : Single-query helper invoked for each element.

    Examples
    --------
    >>> import pandas as pd
    >>> from mayutils.data.read import read_queries
    >>> from mayutils.objects.types import SQL
    >>> def reader(query, /, *, backend=None):
    ...     return pd.DataFrame({"n": [1]})
    >>> dfs = read_queries(
    ...     [SQL("SELECT 1 AS n"), SQL("SELECT 2 AS n")],
    ...     reader=reader,
    ...     persist=None,
    ... )
    >>> len(dfs)
    2
    """
    logger.debug(f"Reading {len(queries)} queries with up to {max_workers} workers")

    with ThreadPoolExecutor(
        max_workers=max_workers,
    ) as executor:
        futures = tuple(
            executor.submit(
                read_query,
                query,
                reader=reader,
                backend=backend,  # ty:ignore[invalid-argument-type]
                parse_temporal=parse_temporal,
                suffix=suffix,
                persist=persist,
                ttl=ttl,
                cache_extra=cache_extra,
                cache_description=cache_description,
                cache_folder=cache_folder,
                queries_folders=queries_folders,
                default_suffix=default_suffix,
                template_kwargs=template_kwargs,
            )
            for query in queries
        )

        return tuple(future.result() for future in futures)  # ty:ignore[invalid-return-type]


__all__ = [
    "QueryInputWarning",
    "QueryReader",
    "QueryStreamer",
    "read_queries",
    "read_query",
    "render_query",
    "stream_query",
]
