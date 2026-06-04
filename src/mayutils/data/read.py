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
...     cache=True,
...     product="personal",
... )
>>> df.shape  # doctest: +SKIP
(3, 1)
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from mayutils.core.extras import may_require_extras
from mayutils.data import CACHE_FOLDER
from mayutils.data.queries import QUERIES_FOLDERS, format_query
from mayutils.environment.memoisation import cache, make_cache_stem
from mayutils.objects.dataframes.backends import Backend, DataFrames, default_backend

with may_require_extras():
    import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from mayutils.objects.datetime import Duration
    from mayutils.objects.types import SQL, SupportsStr


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
    >>> QueryExecutor  # doctest: +SKIP
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
        >>> QueryExecutor  # doctest: +SKIP
        <class 'mayutils.data.read.QueryExecutor'>
        """
        ...


@runtime_checkable
class QueryReader[DataFrameType: DataFrames = pd.DataFrame](Protocol):
    """
    Define the structural contract for executing a rendered query string.

    A reader is any callable with the signature
    ``(str, *, dataframe_backend: ?? = "pandas") ->
    ??``. The ``dataframe_backend`` keyword lets a single
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
        backend: Backend[DataFrameType] | None = None,
    ) -> DataFrameType:
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
        backend
            DataFrame library the result should be materialised in.
            Implementations that support only one backend should
            raise :class:`NotImplementedError` rather than silently
            returning the wrong type.

        Returns
        -------
            Materialised query result; concrete type matches
            ``backend``.

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


def as_query_reader[DataFrameType: DataFrames = pd.DataFrame](
    func: Callable[[str], DataFrameType],
    /,
    *,
    required_backend: Backend[DataFrameType] | None = None,
) -> QueryReader[DataFrameType]:
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
    func
        Backend-fixed query executor taking a rendered SQL string
        and returning a DataFrame.
    required_backend
        The backend ``func`` produces. The returned reader will only
        accept this value for ``backend``.

    Returns
    -------
        Callable satisfying :class:`QueryReader`, with
        ``backend`` routed to ``func`` when it matches
        ``required_backend`` and raising otherwise.

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
    required_backend = required_backend if required_backend is not None else cast("Backend[DataFrameType]", default_backend())

    def reader(
        query: str,
        /,
        *,
        backend: Backend[DataFrameType] | None = None,
    ) -> DataFrameType:
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
        backend
            DataFrame backend requested by :func:`read_query`. Must
            equal the ``required_backend`` captured from the enclosing
            :func:`as_query_reader` call.

        Returns
        -------
            Result produced by ``func(query)``; concrete type matches
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
        backend = backend if backend is not None else cast("Backend[DataFrameType]", default_backend())
        if required_backend.name != backend.name:
            msg = f"Reader supports '{backend}' only; got '{required_backend}'"
            raise NotImplementedError(msg)

        return func(query)

    return reader


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
    **format_kwargs: SupportsStr,
) -> str:
    r"""
    Render a query template to a concrete SQL string.

    The behaviour depends on the runtime type of ``query``. A
    :class:`~pathlib.Path` is resolved against ``queries_folders`` via
    :func:`mayutils.data.queries.format_query`, which reads the
    template from disk and applies :meth:`str.format` with
    ``format_kwargs``. An :data:`~mayutils.objects.types.SQL` string is
    treated as an inline template and rendered directly via
    :meth:`str.format` when ``format_kwargs`` is non-empty, or returned
    verbatim otherwise. When a plain :class:`str` structurally resembles
    a file path (detected by :func:`looks_like_sql_path`), a
    :class:`QueryInputWarning` is emitted and the string is routed
    through :func:`~mayutils.data.queries.format_query` as if it were a
    :class:`~pathlib.Path`. Keeping both paths behind a single helper
    means :func:`read_query`, its caching logic, and any bespoke
    pre-processing agree on exactly one string to hash and to execute.

    Parameters
    ----------
    query
        Either an inline SQL template wrapped in
        :data:`~mayutils.objects.types.SQL` with ``{name}``
        placeholders, or a :class:`~pathlib.Path` identifying a
        bundled query template on disk. A plain :class:`str` is
        accepted at runtime for backwards compatibility but will be
        flagged by type checkers; if it structurally resembles a file
        path, a :class:`QueryInputWarning` is emitted.
    queries_folders
        Search path forwarded to :func:`format_query` when
        resolving path-typed queries. Defaults to
        :data:`mayutils.data.queries.QUERIES_FOLDERS`.
    default_suffix
        File extension assumed when *query* is a bare filename
        without a suffix. Forwarded to :func:`format_query`.
    **format_kwargs
        Keyword substitutions applied to the template. Every value
        must be stringifiable; Python inserts
        ``str(value)`` at each matching ``{name}`` placeholder.

    Returns
    -------
    str
        Fully rendered SQL string ready to be dispatched through a
        :class:`QueryReader`.

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
    >>> render_query(SQL("SELECT * FROM {table}"), table="loans")
    'SELECT * FROM loans'
    >>> render_query(
    ...     SQL("SELECT * FROM {table} WHERE product = {product!r}"),
    ...     table="loans",
    ...     product="personal",
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

    if isinstance(query, Path):
        return format_query(
            query,
            queries_folders=queries_folders,
            default_suffix=default_suffix,
            **format_kwargs,
        )

    return query.format(**format_kwargs)


def read_query[DataFrameType: DataFrames = pd.DataFrame](
    query: SQL | Path,
    /,
    *,
    reader: QueryReader[DataFrameType],
    backend: Backend[DataFrameType] | None = None,
    suffix: str | None = None,
    persist: bool | None = False,
    ttl: Duration | None = None,
    cache_extra: Mapping[str, object] | None = None,
    cache_description: str | None = None,
    cache_folder: Path | str = CACHE_FOLDER,
    queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
    default_suffix: str = "sql",
    **format_kwargs: SupportsStr,
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
    **format_kwargs
        Template substitutions forwarded to :func:`render_query`.

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
    backend = backend if backend is not None else cast("Backend[DataFrameType]", default_backend())

    rendered_query = render_query(
        query,
        queries_folders=queries_folders,
        default_suffix=default_suffix,
        **format_kwargs,
    )

    if persist is None:
        return reader(
            rendered_query,
            backend=backend,
        )

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
        >>> read_query  # doctest: +SKIP
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
                    format_kwargs=format_kwargs,
                    cache_extra=cache_extra,
                    key="",
                ),
            )(execute),
        )

    return cached_execute(
        rendered_query,
        _extra=dict(cache_extra) if cache_extra else None,
    )


__all__ = [
    "QueryInputWarning",
    "QueryReader",
    "as_query_reader",
    "read_query",
    "render_query",
]
