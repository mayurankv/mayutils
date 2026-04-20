"""SQLAlchemy engine factories with Snowflake and pandas helpers.

Provides an :class:`EngineWrapper` facade over a SQLAlchemy ``Engine`` that
adds ergonomic constructors for generic database URLs and for Snowflake
connections (via ``snowflake.sqlalchemy.URL``), together with a
``read_pandas`` shortcut that executes a SQL query and returns a
:class:`pandas.DataFrame` with optionally lower-cased column names. The
module is intended as the single entry-point used by higher-level
``mayutils.data`` helpers for obtaining configured database engines.
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
    """Facade around a SQLAlchemy :class:`~sqlalchemy.Engine` with pandas helpers.

    The wrapper owns a single SQLAlchemy engine instance and exposes it
    through :meth:`__call__`, alongside a :meth:`read_pandas` convenience
    that dispatches to :func:`pandas.read_sql` and normalises the output
    column casing. Two class-method constructors are provided so callers
    rarely need to build an engine manually: :meth:`create` takes a raw
    URL or :class:`sqlalchemy.URL` and forwards kwargs to
    :func:`sqlalchemy.create_engine`, while :meth:`via_snowflake` builds
    a Snowflake connection URL from keyword arguments before delegating
    to :meth:`create`.

    Attributes
    ----------
    engine : sqlalchemy.Engine
        The wrapped SQLAlchemy engine used for all query execution.

    Examples
    --------
    >>> engine = EngineWrapper.via_snowflake(account="acme")  # doctest: +SKIP
    >>> df = engine.read_pandas("select 1 as foo")  # doctest: +SKIP
    """

    def __init__(
        self,
        engine: Engine,
        /,
    ) -> None:
        """Wrap an existing SQLAlchemy engine.

        Parameters
        ----------
        engine : sqlalchemy.Engine
            Pre-configured SQLAlchemy engine to be stored on the instance
            and reused for every query issued through the wrapper. The
            wrapper takes no ownership of lifecycle management; callers
            remain responsible for disposing of the engine if required.
        """
        self.engine = engine

    @classmethod
    def create(
        cls,
        url: str | SQLURL,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """Build an :class:`EngineWrapper` from a SQLAlchemy URL.

        Thin constructor that forwards to :func:`sqlalchemy.create_engine`
        and wraps the resulting engine. Use this for any non-Snowflake
        target or when a fully-formed URL is already available.

        Parameters
        ----------
        url : str or sqlalchemy.URL
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
        EngineWrapper
            Wrapper bound to the freshly-created engine, ready for use
            with :meth:`read_pandas` or direct engine access via
            :meth:`__call__`.
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
        snowflake_url_kwargs: Mapping[str, Any] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """Build an :class:`EngineWrapper` configured for Snowflake.

        Constructs a Snowflake connection URL using
        :class:`snowflake.sqlalchemy.URL` from ``snowflake_url_kwargs``
        and then delegates to :meth:`create` so that remaining keyword
        arguments can still tune the underlying SQLAlchemy engine.

        Parameters
        ----------
        snowflake_url_kwargs : collections.abc.Mapping[str, Any], optional
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
        EngineWrapper
            Wrapper bound to a Snowflake-backed SQLAlchemy engine.
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
        """Execute a SQL query and return the result as a pandas DataFrame.

        Wraps :func:`pandas.read_sql` against the stored engine and
        optionally normalises column names to lower case so downstream
        code can rely on a consistent casing regardless of the dialect's
        default identifier folding (Snowflake in particular upper-cases
        unquoted identifiers).

        Parameters
        ----------
        query : str
            SQL statement to execute. Passed as the ``sql`` argument to
            :func:`pandas.read_sql`; may be any string the database
            engine understands, including multi-statement scripts
            supported by the driver.
        lower_case : bool, default True
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
        pandas.DataFrame
            Result set materialised as a DataFrame, with columns
            lower-cased unless ``lower_case`` is ``False``.
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
        """Return the underlying SQLAlchemy engine.

        Allows the wrapper to be used interchangeably with a bare engine
        at call sites that require the native SQLAlchemy object (for
        example when passing to libraries that accept only
        :class:`sqlalchemy.Engine`).

        Returns
        -------
        sqlalchemy.Engine
            The engine stored on :attr:`engine`.
        """
        return self.engine
