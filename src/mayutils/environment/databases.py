"""
Provide SQLAlchemy engine factories with Snowflake and pandas helpers.

Exposes an :class:`EngineWrapper` facade over a SQLAlchemy ``Engine`` that
adds ergonomic constructors for generic database URLs and for Snowflake
connections (via ``snowflake.sqlalchemy.URL``), together with a
``read_pandas`` shortcut that executes a SQL query and returns a
:class:`pandas.DataFrame` with optionally lower-cased column names. The
module is intended as the single entry-point used by higher-level
``mayutils.data`` helpers for obtaining configured database engines. It
centralises driver selection and credential handling so that callers do
not need to know about the specific dialect or connection-pool tuning
applied downstream.

See Also
--------
sqlalchemy.Engine : Core SQLAlchemy engine abstraction wrapped by this module.
sqlalchemy.create_engine : Underlying factory used to instantiate engines.
snowflake.sqlalchemy.URL : Helper for building Snowflake connection URLs.
snowflake.connector : Low-level Snowflake Python driver used by the dialect.
pandas.read_sql : Query-to-DataFrame helper used by :meth:`EngineWrapper.read_pandas`.

Examples
--------
>>> from sqlalchemy import create_engine
>>> from mayutils.environment.databases import EngineWrapper
>>> wrapper = EngineWrapper(create_engine("sqlite:///:memory:"))
>>> isinstance(wrapper, EngineWrapper)
True
"""

from collections.abc import Iterator, Mapping
from typing import Any, Self, cast

from mayutils.core.extras import may_require_extras
from mayutils.data.read import QueryReader, QueryStreamer
from mayutils.environment.logging import Logger
from mayutils.objects.dataframes.backends import Backend, DataFrames, default_backend

with may_require_extras():
    import pandas as pd
    import polars as pl
    from snowflake.sqlalchemy import URL  # pyright: ignore[reportAttributeAccessIssue, reportUnknownVariableType]
    from sqlalchemy import URL as SQLURL
    from sqlalchemy import Engine, create_engine


logger = Logger.spawn()

DEFAULT_CHUNK_SIZE = 10_000


class EngineWrapper:
    """
    Wrap a SQLAlchemy :class:`~sqlalchemy.Engine` with pandas-friendly helpers.

    The wrapper owns a single SQLAlchemy engine instance and exposes it
    through :meth:`__call__`, alongside a :meth:`read_pandas` convenience
    that dispatches to :func:`pandas.read_sql` and normalises the output
    column casing. Two class-method constructors are provided so callers
    rarely need to build an engine manually: :meth:`create` takes a raw
    URL or :class:`sqlalchemy.URL` and forwards kwargs to
    :func:`sqlalchemy.create_engine`, while :meth:`via_snowflake` builds
    a Snowflake connection URL from keyword arguments before delegating
    to :meth:`create`. The stored engine retains its own connection pool,
    so a single wrapper instance can be safely reused across threads.

    Parameters
    ----------
    engine
        Pre-configured SQLAlchemy engine stored on the instance and
        reused for every query issued through the wrapper. Ownership of
        the engine's lifecycle remains with the caller.

    Attributes
    ----------
    engine
        The wrapped SQLAlchemy engine used for all query execution.
        Retains its own connection pool and is reused across calls.

    See Also
    --------
    sqlalchemy.Engine : The underlying engine type stored on the wrapper.
    sqlalchemy.create_engine : Factory used by :meth:`create` to build the engine.
    sqlalchemy.Connection : Connection object checked out from the engine's pool.
    snowflake.sqlalchemy.URL : Helper used by :meth:`via_snowflake` to assemble URLs.
    snowflake.connector : Backing driver used once the Snowflake dialect connects.

    Examples
    --------
    >>> from sqlalchemy import create_engine
    >>> from mayutils.environment.databases import EngineWrapper
    >>> wrapper = EngineWrapper(create_engine("sqlite:///:memory:"))
    >>> isinstance(wrapper, EngineWrapper)
    True
    >>> import pandas as pd
    >>> from sqlalchemy import create_engine
    >>> from mayutils.environment.databases import EngineWrapper
    >>> engine = create_engine("sqlite:///:memory:")
    >>> _ = pd.DataFrame({"foo": [1]}).to_sql("t", engine, index=False)
    >>> wrapper = EngineWrapper(engine)
    >>> wrapper.read_pandas("SELECT * FROM t").shape
    (1, 1)
    >>> from sqlalchemy import Engine
    >>> isinstance(wrapper(), Engine)
    True
    """

    def __init__(
        self,
        engine: Engine,
        /,
    ) -> None:
        """
        Wrap an existing SQLAlchemy engine.

        Stores the supplied engine on the instance without taking
        ownership of its lifecycle. The wrapper relies on the engine's
        internal connection pool for session management, so the caller
        remains responsible for disposing of the engine (via
        :meth:`sqlalchemy.Engine.dispose`) once it is no longer needed.

        Parameters
        ----------
        engine
            Pre-configured SQLAlchemy engine to be stored on the instance
            and reused for every query issued through the wrapper. The
            wrapper takes no ownership of lifecycle management; callers
            remain responsible for disposing of the engine if required.

        See Also
        --------
        sqlalchemy.Engine : Type of the wrapped engine instance.
        sqlalchemy.Engine.dispose : Lifecycle method the caller remains responsible for.
        EngineWrapper.create : Convenience constructor building the engine for you.
        EngineWrapper.via_snowflake : Snowflake-specific sibling constructor.

        Examples
        --------
        >>> from sqlalchemy import create_engine
        >>> from mayutils.environment.databases import EngineWrapper
        >>> engine = create_engine("sqlite:///:memory:")
        >>> wrapper = EngineWrapper(engine)
        >>> isinstance(wrapper, EngineWrapper)
        True
        """
        self.engine = engine

    @classmethod
    def create(
        cls,
        url: str | SQLURL,
        **kwargs: object,
    ) -> Self:
        """
        Build an :class:`EngineWrapper` from a SQLAlchemy URL.

        Thin constructor that forwards to :func:`sqlalchemy.create_engine`
        and wraps the resulting engine. Use this for any non-Snowflake
        target or when a fully-formed URL is already available. The
        SQLAlchemy dialect is selected from the URL scheme, and the
        underlying connection pool is materialised lazily on first use.

        Parameters
        ----------
        url
            Database connection URL understood by
            :func:`sqlalchemy.create_engine`. Either a raw connection
            string (e.g. ``"postgresql+psycopg://user:pw@host/db"``) or a
            pre-built :class:`sqlalchemy.URL` object.
        **kwargs
            Additional keyword arguments forwarded verbatim to
            :func:`sqlalchemy.create_engine` to configure pool sizing,
            isolation level, connect args, and similar engine options.

        Returns
        -------
            Wrapper bound to the freshly-created engine, ready for use
            with :meth:`read_pandas` or direct engine access via
            :meth:`__call__`.

        See Also
        --------
        sqlalchemy.create_engine : Factory invoked internally to build the engine.
        sqlalchemy.Engine : Type of the engine wrapped by the returned instance.
        sqlalchemy.Connection : Connection object obtained from the engine's pool.
        EngineWrapper.via_snowflake : Snowflake-specific counterpart of this helper.
        EngineWrapper.__init__ : Underlying constructor the returned engine is passed to.

        Examples
        --------
        >>> from mayutils.environment.databases import EngineWrapper
        >>> wrapper = EngineWrapper.create("sqlite:///:memory:")
        >>> isinstance(wrapper, EngineWrapper)
        True
        """
        engine = create_engine(
            url=url,
            **kwargs,
        )

        logger.info(f"Created database engine for {engine.url.render_as_string(hide_password=True)}")

        return cls(engine)

    @classmethod
    def via_snowflake(
        cls,
        connection_parameters: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> Self:
        """
        Build an :class:`EngineWrapper` configured for Snowflake.

        Constructs a Snowflake connection URL using
        :class:`snowflake.sqlalchemy.URL` from ``connection_parameters``
        and then delegates to :meth:`create` so that remaining keyword
        arguments can still tune the underlying SQLAlchemy engine. This
        split lets connection-identity parameters (account, role, etc.)
        flow to the URL builder while engine-wide options (pool sizing,
        connect args) flow to :func:`sqlalchemy.create_engine`.

        Parameters
        ----------
        connection_parameters
            Keyword arguments forwarded to :class:`snowflake.sqlalchemy.URL`
            to describe the target account and session (typical keys
            include ``account``, ``user``, ``password``, ``warehouse``,
            ``database``, ``schema``, ``role``, ``authenticator``). When
            ``None`` an empty mapping is used, which relies on Snowflake
            defaults or environment-based credentials.
        **kwargs
            Additional keyword arguments forwarded through :meth:`create`
            to :func:`sqlalchemy.create_engine` (pool settings, connect
            args, etc.).

        Returns
        -------
            Wrapper bound to a Snowflake-backed SQLAlchemy engine.

        See Also
        --------
        snowflake.sqlalchemy.URL : Helper used to assemble the connection URL.
        snowflake.connector : Underlying Python driver opened by the dialect.
        sqlalchemy.create_engine : Engine factory invoked via :meth:`create`.
        sqlalchemy.Engine : Type of the engine the returned wrapper holds.
        EngineWrapper.create : Sibling constructor used once the URL is built.

        Examples
        --------
        >>> from mayutils.environment.databases import EngineWrapper
        >>> wrapper = EngineWrapper.via_snowflake(  # doctest: +SKIP
        ...     connection_parameters={
        ...         "account": "xy12345.eu-west-2.aws",
        ...         "user": "analyst",
        ...         "password": "***",
        ...         "database": "ANALYTICS",
        ...         "warehouse": "COMPUTE_WH",
        ...         "schema": "PUBLIC",
        ...     },
        ... )  # doctest: +SKIP
        >>> df = wrapper.read_pandas("SELECT 1 AS n")  # doctest: +SKIP
        """
        return cls.create(
            url=cast(
                "SQLURL",
                URL(
                    **(connection_parameters or {}),
                ),
            ),
            **kwargs,
        )

    def read_pandas(
        self,
        query: str,
        /,
        *,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
    ) -> pd.DataFrame:
        """
        Execute a SQL query and return the result as a pandas DataFrame.

        Wraps :func:`pandas.read_sql` against the stored engine and
        optionally normalises column names to lower case so downstream
        code can rely on a consistent casing regardless of the dialect's
        default identifier folding (Snowflake in particular upper-cases
        unquoted identifiers). A connection is checked out of the
        engine's pool for the duration of the query and returned on
        completion, so no explicit session management is required.

        Parameters
        ----------
        query
            SQL statement to execute. Passed as the ``sql`` argument to
            :func:`pandas.read_sql`; may be any string the database
            engine understands, including multi-statement scripts
            supported by the driver.
        lower_case
            When ``True`` the returned DataFrame's columns are
            lower-cased in place before being returned. Set to ``False``
            to preserve the exact casing returned by the driver (useful
            when the caller needs to match case-sensitive downstream
            schemas).
        **kwargs
            Additional keyword arguments forwarded to
            :func:`pandas.read_sql` (e.g. ``params``, ``parse_dates``,
            ``chunksize``, ``dtype``).

        Returns
        -------
            Result set materialised as a ``pd.DataFrame``, with columns
            lower-cased unless ``lower_case`` is ``False``.

        See Also
        --------
        pandas.read_sql : Underlying function used to execute the query.
        sqlalchemy.Engine : Engine providing the connection pool used for execution.
        sqlalchemy.Connection : Connection checked out from the engine for the query.
        EngineWrapper.__call__ : Accessor for the engine if finer control is needed.
        EngineWrapper.create : Constructor used to obtain an :class:`EngineWrapper`.

        Examples
        --------
        >>> import pandas as pd
        >>> from sqlalchemy import create_engine
        >>> from mayutils.environment.databases import EngineWrapper
        >>> engine = create_engine("sqlite:///:memory:")
        >>> _ = pd.DataFrame({"A": [1, 2, 3]}).to_sql("t", engine, index=False)
        >>> df = EngineWrapper(engine).read_pandas("SELECT * FROM t")
        >>> df.shape
        (3, 1)
        >>> df.columns.tolist()
        ['a']
        """
        default_read_kwargs: dict[str, Any] = {}

        logger.debug(f"Reading query ({len(query)} chars) into pandas")

        df = cast(
            "pd.DataFrame",
            pd.read_sql(
                sql=query,
                con=self.engine,
                **(default_read_kwargs | dict(read_kwargs or {})),
            ),
        )

        if lower_case:
            df.columns = df.columns.str.lower()

        logger.debug(f"Query returned pandas dataframe with shape {df.shape}")

        return df

    def read_polars(
        self,
        query: str,
        /,
        *,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
    ) -> pl.DataFrame:
        """
        Execute a SQL query and return the result as a polars DataFrame.

        Wraps :func:`polars.read_database` against the stored engine and
        optionally normalises column names to lower case so downstream
        code can rely on a consistent casing regardless of the dialect's
        default identifier folding (Snowflake in particular upper-cases
        unquoted identifiers). A connection is checked out of the
        engine's pool for the duration of the query and returned on
        completion, so no explicit session management is required.

        Parameters
        ----------
        query
            SQL statement to execute. Passed as the ``query`` argument
            to :func:`polars.read_database`; may be any string the
            database engine understands.
        lower_case
            When ``True`` the returned DataFrame's columns are
            lower-cased before being returned. Set to ``False`` to
            preserve the exact casing returned by the driver (useful
            when the caller needs to match case-sensitive downstream
            schemas).
        read_kwargs
            Additional keyword arguments forwarded to
            :func:`polars.read_database` (e.g. ``schema_overrides``,
            ``infer_schema_length``, ``execute_options``).

        Returns
        -------
            Result set materialised as a ``pl.DataFrame``, with columns
            lower-cased unless ``lower_case`` is ``False``.

        See Also
        --------
        polars.read_database : Underlying function used to execute the query.
        sqlalchemy.Engine : Engine providing the connection pool used for execution.
        EngineWrapper.read_pandas : Pandas counterpart of this helper.
        EngineWrapper.stream_polars : Chunked streaming variant of this helper.

        Examples
        --------
        >>> import pandas as pd
        >>> from sqlalchemy import create_engine
        >>> from mayutils.environment.databases import EngineWrapper
        >>> engine = create_engine("sqlite:///:memory:")
        >>> _ = pd.DataFrame({"A": [1, 2, 3]}).to_sql("t", engine, index=False)
        >>> df = EngineWrapper(engine).read_polars("SELECT * FROM t")
        >>> df.shape
        (3, 1)
        >>> df.columns
        ['a']
        """
        default_read_kwargs: dict[str, Any] = {}

        logger.debug(f"Reading query ({len(query)} chars) into polars")

        df = cast(
            "pl.DataFrame",
            pl.read_database(
                query=query,
                connection=self.engine,
                **(default_read_kwargs | dict(read_kwargs or {})),
            ),
        )

        if lower_case:
            df.columns = [col.lower() for col in df.columns]

        logger.debug(f"Query returned polars dataframe with shape {df.shape}")

        return df

    def to_reader(
        self,
        /,
        *,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
    ) -> QueryReader:
        """
        Build a :class:`~mayutils.data.read.QueryReader` bound to this engine.

        The returned closure captures the wrapper together with the
        supplied reading options and dispatches to :meth:`read_pandas`
        or :meth:`read_polars` according to the requested backend. This
        makes the wrapper directly usable as the ``reader`` argument of
        :func:`mayutils.data.read.read_query`.

        Parameters
        ----------
        lower_case
            When ``True`` result columns are lower-cased before being
            returned. Forwarded to the backend-specific read method.
        read_kwargs
            Additional keyword arguments forwarded to the underlying
            read function of the selected backend.

        Returns
        -------
            Callable satisfying the ``QueryReader`` protocol.

        See Also
        --------
        mayutils.data.read.QueryReader : Protocol the returned callable satisfies.
        mayutils.data.read.read_query : Primary consumer of the returned reader.
        EngineWrapper.read_pandas : Pandas read method the closure dispatches to.
        EngineWrapper.read_polars : Polars read method the closure dispatches to.
        EngineWrapper.to_streamer : Streaming counterpart of this helper.

        Examples
        --------
        >>> import pandas as pd
        >>> from sqlalchemy import create_engine
        >>> from mayutils.environment.databases import EngineWrapper
        >>> engine = create_engine("sqlite:///:memory:")
        >>> _ = pd.DataFrame({"A": [1]}).to_sql("t", engine, index=False)
        >>> reader = EngineWrapper(engine).to_reader()
        >>> reader("SELECT * FROM t").shape
        (1, 1)
        """

        def reader[DataFrameType: DataFrames = pd.DataFrame](
            query: str,
            /,
            *,
            backend: Backend[DataFrameType] | None = None,
        ) -> DataFrameType:
            backend = backend if backend is not None else cast("Backend[DataFrameType]", default_backend())

            if backend.name == "pandas":
                df = self.read_pandas(
                    query,
                    lower_case=lower_case,
                    read_kwargs=read_kwargs,
                )

            elif backend.name == "polars":
                df = self.read_polars(
                    query,
                    lower_case=lower_case,
                    read_kwargs=read_kwargs,
                )

            else:
                msg = f"Unsupported backend: {backend.name!r}"
                raise ValueError(msg)

            return cast("DataFrameType", df)

        return reader

    def stream_pandas(
        self,
        query: str,
        /,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
    ) -> Iterator[pd.DataFrame]:
        """
        Execute a SQL query and yield the result in pandas chunks.

        Wraps :func:`pandas.read_sql` with ``chunksize`` set so the
        driver materialises the result incrementally instead of all at
        once, keeping peak memory bounded for large result sets. Column
        names are optionally lower-cased on each chunk before it is
        yielded, mirroring the behaviour of :meth:`read_pandas`.

        Parameters
        ----------
        query
            SQL statement to execute. Passed as the ``sql`` argument to
            :func:`pandas.read_sql`; may be any string the database
            engine understands.
        chunk_size
            Maximum number of rows per yielded chunk.
        lower_case
            When ``True`` each chunk's columns are lower-cased before
            being yielded. Set to ``False`` to preserve the exact casing
            returned by the driver.
        read_kwargs
            Additional keyword arguments forwarded to
            :func:`pandas.read_sql` (e.g. ``params``, ``parse_dates``,
            ``dtype``). A ``chunksize`` entry overrides ``chunk_size``.

        Yields
        ------
            Successive ``pd.DataFrame`` chunks of the result set, with
            columns lower-cased unless ``lower_case`` is ``False``.

        See Also
        --------
        pandas.read_sql : Underlying function used to execute the query.
        sqlalchemy.Engine : Engine providing the connection pool used for execution.
        EngineWrapper.read_pandas : Eager counterpart returning a single DataFrame.
        EngineWrapper.stream_polars : Polars counterpart of this helper.

        Examples
        --------
        >>> import pandas as pd
        >>> from sqlalchemy import create_engine
        >>> from mayutils.environment.databases import EngineWrapper
        >>> engine = create_engine("sqlite:///:memory:")
        >>> _ = pd.DataFrame({"A": [1, 2, 3]}).to_sql("t", engine, index=False)
        >>> chunks = list(EngineWrapper(engine).stream_pandas("SELECT * FROM t", chunk_size=2))
        >>> [chunk.shape for chunk in chunks]
        [(2, 1), (1, 1)]
        """
        default_read_kwargs: dict[str, Any] = {
            "chunksize": chunk_size,
        }

        logger.debug(f"Streaming query ({len(query)} chars) into pandas chunks of {chunk_size}")

        dfs = cast(
            "Iterator[pd.DataFrame]",
            pd.read_sql(
                sql=query,
                con=self.engine,
                **(default_read_kwargs | dict(read_kwargs or {})),
            ),
        )

        for df in dfs:
            if lower_case:
                df.columns = df.columns.str.lower()

            yield df

    def stream_polars(
        self,
        query: str,
        /,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
    ) -> Iterator[pl.DataFrame]:
        """
        Execute a SQL query and yield the result in polars chunks.

        Wraps :func:`polars.read_database` with ``iter_batches`` enabled
        so the driver materialises the result incrementally instead of
        all at once, keeping peak memory bounded for large result sets.
        Column names are optionally lower-cased on each chunk before it
        is yielded, mirroring the behaviour of :meth:`read_polars`.

        Parameters
        ----------
        query
            SQL statement to execute. Passed as the ``query`` argument
            to :func:`polars.read_database`; may be any string the
            database engine understands.
        chunk_size
            Maximum number of rows per yielded chunk. Forwarded as
            ``batch_size`` to :func:`polars.read_database`.
        lower_case
            When ``True`` each chunk's columns are lower-cased before
            being yielded. Set to ``False`` to preserve the exact casing
            returned by the driver.
        read_kwargs
            Additional keyword arguments forwarded to
            :func:`polars.read_database` (e.g. ``schema_overrides``,
            ``infer_schema_length``). ``iter_batches`` and
            ``batch_size`` entries override the streaming defaults.

        Yields
        ------
            Successive ``pl.DataFrame`` chunks of the result set, with
            columns lower-cased unless ``lower_case`` is ``False``.

        See Also
        --------
        polars.read_database : Underlying function used to execute the query.
        sqlalchemy.Engine : Engine providing the connection pool used for execution.
        EngineWrapper.read_polars : Eager counterpart returning a single DataFrame.
        EngineWrapper.stream_pandas : Pandas counterpart of this helper.

        Examples
        --------
        >>> import pandas as pd
        >>> from sqlalchemy import create_engine
        >>> from mayutils.environment.databases import EngineWrapper
        >>> engine = create_engine("sqlite:///:memory:")
        >>> _ = pd.DataFrame({"A": [1, 2, 3]}).to_sql("t", engine, index=False)
        >>> chunks = list(EngineWrapper(engine).stream_polars("SELECT * FROM t", chunk_size=2))
        >>> [chunk.shape for chunk in chunks]
        [(2, 1), (1, 1)]
        """
        default_read_kwargs: dict[str, Any] = {
            "iter_batches": True,
            "batch_size": chunk_size,
        }

        logger.debug(f"Streaming query ({len(query)} chars) into polars chunks of {chunk_size}")

        dfs = cast(
            "Iterator[pl.DataFrame]",
            pl.read_database(
                query=query,
                connection=self.engine,
                **(default_read_kwargs | dict(read_kwargs or {})),
            ),
        )

        for df in dfs:
            if lower_case:
                df.columns = [col.lower() for col in df.columns]
            yield df

    def to_streamer(
        self,
        /,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
    ) -> QueryStreamer:
        """
        Build a :class:`~mayutils.data.read.QueryStreamer` bound to this engine.

        The returned closure captures the wrapper together with the
        supplied streaming options and dispatches to
        :meth:`stream_pandas` or :meth:`stream_polars` according to the
        requested backend. This makes the wrapper directly usable as the
        ``streamer`` argument of :func:`mayutils.data.read.stream_query`.

        Parameters
        ----------
        chunk_size
            Maximum number of rows per yielded chunk. Forwarded to the
            backend-specific streaming method.
        lower_case
            When ``True`` each chunk's columns are lower-cased before
            being yielded. Forwarded to the backend-specific streaming
            method.
        read_kwargs
            Additional keyword arguments forwarded to the underlying
            read function of the selected backend.

        Returns
        -------
            Callable satisfying the ``QueryStreamer`` protocol.

        See Also
        --------
        mayutils.data.read.QueryStreamer : Protocol the returned callable satisfies.
        mayutils.data.read.stream_query : Primary consumer of the returned streamer.
        EngineWrapper.stream_pandas : Pandas streaming method the closure dispatches to.
        EngineWrapper.stream_polars : Polars streaming method the closure dispatches to.
        EngineWrapper.to_reader : Eager counterpart of this helper.

        Examples
        --------
        >>> import pandas as pd
        >>> from sqlalchemy import create_engine
        >>> from mayutils.environment.databases import EngineWrapper
        >>> engine = create_engine("sqlite:///:memory:")
        >>> _ = pd.DataFrame({"A": [1, 2, 3]}).to_sql("t", engine, index=False)
        >>> streamer = EngineWrapper(engine).to_streamer(chunk_size=2)
        >>> [chunk.shape for chunk in streamer("SELECT * FROM t")]
        [(2, 1), (1, 1)]
        """

        def streamer[DataFrameType: DataFrames = pd.DataFrame](
            query: str,
            /,
            *,
            backend: Backend[DataFrameType] | None = None,
        ) -> Iterator[DataFrameType]:
            backend = backend if backend is not None else cast("Backend[DataFrameType]", default_backend())

            if backend.name == "pandas":
                dfs = self.stream_pandas(
                    query,
                    chunk_size=chunk_size,
                    lower_case=lower_case,
                    read_kwargs=read_kwargs,
                )

            elif backend.name == "polars":
                dfs = self.stream_polars(
                    query,
                    chunk_size=chunk_size,
                    lower_case=lower_case,
                    read_kwargs=read_kwargs,
                )

            else:
                msg = f"Unsupported backend: {backend.name!r}"
                raise ValueError(msg)

            yield from cast("Iterator[DataFrameType]", dfs)

        return streamer

    def __call__(
        self,
    ) -> Engine:
        """
        Return the underlying SQLAlchemy engine.

        Allows the wrapper to be used interchangeably with a bare engine
        at call sites that require the native SQLAlchemy object (for
        example when passing to libraries that accept only
        :class:`sqlalchemy.Engine`). No copy is made; the exposed engine
        shares its connection pool with any other consumers of the
        wrapper, so callers should avoid mutating configuration on it.

        Returns
        -------
            The engine stored on :attr:`engine`.

        See Also
        --------
        sqlalchemy.Engine : Type of the returned object.
        sqlalchemy.Connection : Connection obtained by calling ``engine.connect()``.
        sqlalchemy.create_engine : Factory used to originally build the engine.
        EngineWrapper.read_pandas : Higher-level helper that uses this engine internally.
        EngineWrapper.create : Constructor producing the wrapper exposed here.

        Examples
        --------
        >>> from sqlalchemy import Engine, text
        >>> from mayutils.environment.databases import EngineWrapper
        >>> wrapper = EngineWrapper.create("sqlite:///:memory:")
        >>> engine = wrapper()
        >>> isinstance(engine, Engine)
        True
        >>> with engine.connect() as conn:
        ...     conn.execute(text("SELECT 1")).scalar()
        1
        """
        return self.engine
