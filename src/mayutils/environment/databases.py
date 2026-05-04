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

from collections.abc import Mapping
from typing import Any, Self, cast

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from pandas import DataFrame, read_sql
    from snowflake.sqlalchemy import URL  # pyright: ignore[reportAttributeAccessIssue, reportUnknownVariableType]
    from sqlalchemy import URL as SQLURL
    from sqlalchemy import Engine, create_engine


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
        return cls(
            create_engine(
                url=url,
                **kwargs,
            )
        )

    @classmethod
    def via_snowflake(
        cls,
        snowflake_url_kwargs: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> Self:
        """
        Build an :class:`EngineWrapper` configured for Snowflake.

        Constructs a Snowflake connection URL using
        :class:`snowflake.sqlalchemy.URL` from ``snowflake_url_kwargs``
        and then delegates to :meth:`create` so that remaining keyword
        arguments can still tune the underlying SQLAlchemy engine. This
        split lets connection-identity parameters (account, role, etc.)
        flow to the URL builder while engine-wide options (pool sizing,
        connect args) flow to :func:`sqlalchemy.create_engine`.

        Parameters
        ----------
        snowflake_url_kwargs
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
        ...     snowflake_url_kwargs={
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
                    **(snowflake_url_kwargs or {}),
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
        **kwargs: Any,  # noqa: ANN401
    ) -> DataFrame:
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
            Result set materialised as a DataFrame, with columns
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
        df = cast(
            "DataFrame",
            read_sql(
                sql=query,
                con=self.engine,
                **kwargs,
            ),
        )

        if lower_case:
            df.columns = df.columns.str.lower()

        return df

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
