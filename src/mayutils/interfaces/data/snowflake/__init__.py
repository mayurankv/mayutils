"""
Configure Snowflake connections and expose them to the ``mayutils`` data layer.

This module is the Snowflake adapter within
:mod:`mayutils.interfaces.data`. It centralises connection identity and
authentication in a :class:`SnowflakeConfig` model — built directly from
explicit values or, via :meth:`SnowflakeConfig.from_env`, from
``SNOWFLAKE_*`` environment variables — and bridges that configuration
into the rest of the library: :meth:`SnowflakeConfig.to_engine_wrapper`
hands back a :class:`~mayutils.environment.databases.EngineWrapper` built
through ``snowflake.sqlalchemy.URL``, while :meth:`SnowflakeConfig.reader`
returns a backend-aware :class:`~mayutils.data.read.QueryReader` ready to
pass straight to :func:`mayutils.data.read.read_query` or the live views
in :mod:`mayutils.data.live`. Querying, templating and caching therefore
stay in the shared ``data`` layer rather than being reimplemented here.
Snowpark and Modin direct-table helpers (:meth:`SnowflakeConfig.create_snowpark_session`,
:func:`get_table`, :class:`Table`) are also provided; their heavy,
optional dependencies are imported lazily so the module stays importable
without them. No account, warehouse, role or database default is baked
in — every connection parameter comes from the caller, explicitly or
through :meth:`SnowflakeConfig.from_env`.

See Also
--------
mayutils.data.read.read_query : Cached query execution consuming a reader.
mayutils.data.read.QueryReader : Protocol satisfied by :meth:`SnowflakeConfig.reader`.
mayutils.environment.databases.EngineWrapper : SQLAlchemy engine facade reused here.
mayutils.objects.dataframes.backends.Backend : Token selecting the result backend.
mayutils.data.live.StreamingQuery : Incremental consumer of the reader produced here.

Examples
--------
>>> from mayutils.interfaces.data.snowflake import Authentication
>>> Authentication.browser.value
'browser'
"""

from __future__ import annotations

import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, cast

from pydantic import BaseModel, Field, FilePath, SecretStr

from mayutils.core.extras import may_require_extras
from mayutils.environment.databases import DEFAULT_CHUNK_SIZE, EngineWrapper
from mayutils.environment.logging import Logger
from mayutils.environment.secrets import load_secrets
from mayutils.objects.dataframes.backends import Backend, DataFrames, default_backend

with may_require_extras():
    import modin.pandas as mpd
    import pandas as pd
    import polars as pl
    from cryptography.hazmat.backends.openssl import backend
    from cryptography.hazmat.primitives import serialization
    from pyarrow import Table as ArrowTable  # pyright: ignore[reportMissingModuleSource]
    from snowflake.connector import SnowflakeConnection
    from snowflake.snowpark.session import Session as SnowparkSession
    from snowflake.sqlalchemy import URL  # pyright: ignore[reportUnknownVariableType, reportAttributeAccessIssue]

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterator, Mapping, Sequence

    from polars._typing import SchemaDict
    from snowflake.connector.cursor import SnowflakeCursor

    from mayutils.data.read import QueryReader, QueryStreamer


logger = Logger.spawn()


class Authentication(StrEnum):
    """
    Supported Snowflake authentication methods.

    A string enumeration whose members select how :class:`SnowflakeConfig`
    establishes a session. ``browser`` triggers Snowflake's
    ``externalbrowser`` single-sign-on flow, while the two key-pair
    members supply a private key through the connector's ``private_key``
    argument — ``private_key`` for an encrypted, base64-encoded DER blob
    or an encrypted PEM file, and ``private_key_pem_raw`` for an
    unencrypted PEM key.

    Attributes
    ----------
    browser
        Interactive ``externalbrowser`` single-sign-on authentication.
    private_key
        Key-pair authentication from an encrypted DER/PEM private key.
    private_key_pem_raw
        Key-pair authentication from an unencrypted PEM private key.

    See Also
    --------
    SnowflakeConfig : Settings object that consumes this enumeration.
    SnowflakeConfig.unencrypted_private_key : Resolves the DER key for the key-pair members.

    Examples
    --------
    >>> Authentication.browser
    <Authentication.browser: 'browser'>
    >>> Authentication("private_key") is Authentication.private_key
    True
    """

    browser = "browser"
    private_key_pem = "private_key_pem"
    private_key_der = "private_key_der"
    private_key_raw = "private_key_raw"


class SnowflakeConfig(BaseModel):
    """
    Hold Snowflake connection settings and adapt them to the data layer.

    Captures connection identity and credentials as plain fields named for
    the Snowflake connection parameters, so the model is constructed with
    those names directly (``SnowflakeConfig(account=..., schema=...)``).
    :meth:`from_env` is the counterpart that reads the same settings from
    ``SNOWFLAKE_*`` environment variables. ``account`` and ``user`` are
    required; ``role``, ``warehouse``, ``database`` and ``schema`` are
    optional and simply omitted from the connection when unset, so no
    deployment-specific default is ever assumed. The model is the single
    integration point with the wider library: :meth:`to_engine_wrapper`
    yields a reusable :class:`~mayutils.environment.databases.EngineWrapper`
    and :meth:`reader` yields a backend-aware
    :class:`~mayutils.data.read.QueryReader`.

    Attributes
    ----------
    authentication
        Authentication method; defaults to browser single-sign-on.
    private_key
        Encrypted base64 DER (``private_key`` auth) or raw PEM
        (``private_key_pem_raw`` auth) key material.
    private_key_path
        Filesystem path to a private-key file, used when the key is not
        supplied inline.
    private_key_password
        Passphrase decrypting an encrypted private key.
    account
        Snowflake account identifier (required).
    user
        Snowflake login name, typically an email address (required).
    role
        Role to assume for the session; omitted when unset.
    warehouse
        Warehouse to use for the session; omitted when unset.
    database
        Default database for the session; omitted when unset.
    schema_
        Default schema for the session; omitted when unset. Constructed
        and read through the ``schema`` alias to avoid shadowing
        :meth:`pydantic.BaseModel.schema`.

    See Also
    --------
    Authentication : Enumeration of the supported authentication methods.
    SnowflakeConfig.from_env : Build the model from ``SNOWFLAKE_*`` variables.
    SnowflakeConfig.to_engine_wrapper : Build a reusable engine wrapper.
    SnowflakeConfig.reader : Build a backend-aware query reader.

    Examples
    --------
    >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
    >>> config = SnowflakeConfig(account="ab12345.eu-west-1", user="me@example.com")
    >>> config.connection_parameters["account"]
    'ab12345.eu-west-1'
    """

    DEFAULT_CONNECTION_ARGUMENTS: ClassVar[dict[str, Any]] = {
        "disable_ocsp_checks": True,
        "session_parameters": {
            "QUERY_TAG": json.dumps({}),
        },
    }

    authentication: Authentication = Authentication.browser
    private_key: SecretStr | FilePath | None = None
    private_key_password: SecretStr | None = None
    account: str
    user: str
    role: str | None = None
    warehouse: str | None = None
    database: str | None = None
    schema_: str | None = Field(
        default=None,
        alias="schema",
    )

    @classmethod
    def from_env(
        cls,
        *,
        env_file: Path | str | None | Literal[False] = ".env",
    ) -> Self:
        """
        Build a configuration from ``SNOWFLAKE_*`` environment variables.

        Loads *env_file* into the process environment (when given) and then
        reads one variable per field, prefixed with ``SNOWFLAKE_`` and
        upper-cased — so ``account`` is read from ``SNOWFLAKE_ACCOUNT`` and
        ``schema`` (the ``schema_`` alias) from ``SNOWFLAKE_SCHEMA``. Empty
        or unset variables are skipped, leaving field defaults in place, and
        the same validation as direct construction applies, so a missing
        required value raises naming the offending field.

        Parameters
        ----------
        env_file
            Dotenv file loaded before reading the environment. ``None``
            reads the existing environment without loading a file.

        Returns
        -------
            A validated configuration populated from the environment.

        See Also
        --------
        SnowflakeConfig : Direct constructor taking explicit values.
        mayutils.environment.secrets.load_secrets : Loads the dotenv file.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> config = SnowflakeConfig.from_env()  # doctest: +SKIP
        """
        if env_file is not False:
            load_secrets(env_file=env_file)

        values: dict[str, str] = {}
        for field_name, field_info in cls.model_fields.items():
            key = field_info.alias or field_name
            env_value = os.environ.get(f"snowflake_{key}".upper())
            if env_value:
                values[key] = env_value

        logger.debug(f"Loaded Snowflake settings {sorted(values)} from the environment")

        return cls.model_validate(values)

    def update(
        self,
        **updates: Any,  # noqa: ANN401
    ) -> Self:
        current = {
            (field_info.alias or field_name): getattr(self, field_name) for field_name, field_info in type(self).model_fields.items()
        }

        return type(self).model_validate(current | updates)

    @property
    def unencrypted_private_key(
        self,
    ) -> bytes | None:
        if self.private_key is None:
            return None

        private_key_bytes = (
            self.private_key.read_bytes() if isinstance(self.private_key, Path) else self.private_key.get_secret_value().encode()
        )
        password = self.private_key_password.get_secret_value().encode() if self.private_key_password is not None else None

        if self.authentication is Authentication.private_key_pem:
            key = serialization.load_pem_private_key(
                data=private_key_bytes,
                password=password,
                backend=backend,
            )
        elif self.authentication is Authentication.private_key_der:
            key = serialization.load_der_private_key(
                data=base64.b64decode(private_key_bytes),
                password=password,
                backend=backend,
            )
        elif self.authentication is Authentication.private_key_raw:
            key = serialization.load_der_private_key(
                data=private_key_bytes,
                password=None,
                backend=backend,
            )
        else:
            msg = f"Unsupported authentication method for private key: {self.authentication.value!r}"
            raise ValueError(msg)

        return key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

    @property
    def connection_parameters(
        self,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "account": self.account,
            "user": self.user,
        }

        if self.role is not None:
            kwargs["role"] = self.role
        if self.warehouse is not None:
            kwargs["warehouse"] = self.warehouse
        if self.database is not None:
            kwargs["database"] = self.database
        if self.schema_ is not None:
            kwargs["schema"] = self.schema_
        if self.authentication is Authentication.browser:
            kwargs["authenticator"] = "externalbrowser"

        return kwargs

    @property
    def url(
        self,
    ) -> str:
        return cast(
            "str",
            URL(
                **self.connection_parameters,
            ),
        )

    def get_connection_arguments(
        self,
        **kwargs: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        kwargs = self.DEFAULT_CONNECTION_ARGUMENTS | kwargs

        if self.authentication in (Authentication.private_key_pem, Authentication.private_key_der):
            kwargs["private_key"] = self.unencrypted_private_key
            kwargs["client_session_keep_alive"] = True

        return kwargs

    def to_engine_wrapper(
        self,
        *,
        connection_arguments: Mapping[str, Any] | None = None,
        engine_kwargs: Mapping[str, Any] | None = None,
    ) -> EngineWrapper:
        engine_kwargs = dict(engine_kwargs or {}) | {
            "connect_args": self.get_connection_arguments(
                **(connection_arguments or {}),
            ),
        }

        logger.info(
            f"Creating Snowflake engine for account={self.account!r} as user={self.user!r} ({self.authentication.value} authentication)"
        )

        return EngineWrapper.via_snowflake(
            connection_parameters=self.connection_parameters,
            **engine_kwargs,
        )

    def to_connection(
        self,
        *,
        connection_arguments: Mapping[str, Any] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> SnowflakeExtendedConnection:
        connection_kwargs = (
            self.connection_parameters
            | self.get_connection_arguments(
                **(connection_arguments or {}),
            )
            | kwargs
        )

        logger.info(
            f"Opening Snowflake connection to account={self.account!r} as user={self.user!r} ({self.authentication.value} authentication)"
        )

        return SnowflakeExtendedConnection(**connection_kwargs)

    def to_snowpark_session(
        self,
        fresh_session: bool = False,
        **session_kwargs: Any,  # noqa: ANN401
    ) -> SnowparkExtendedSession:
        with may_require_extras():
            import snowflake.snowpark.modin.plugin  # pyright: ignore[reportUnusedImport] # noqa: F401, PLC0415

        default_session_kwargs = {
            "telemetry_enabled": False,
        }
        session_kwargs = self.connection_parameters | self.get_connection_arguments() | default_session_kwargs | session_kwargs

        logger.info(
            f"{'Creating fresh' if fresh_session else 'Getting or creating'} Snowpark session "
            f"for account={self.account!r} as user={self.user!r}"
        )

        builder = SnowparkSession.builder.configs(
            options=session_kwargs,
        )
        session = builder.create() if fresh_session else builder.getOrCreate()

        return SnowparkExtendedSession.from_base(session)

    def to_reader(
        self,
        /,
        *,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
        connection_arguments: Mapping[str, Any] | None = None,
        engine_kwargs: Mapping[str, Any] | None = None,
    ) -> QueryReader:
        engine_wrapper = self.to_engine_wrapper(
            connection_arguments=connection_arguments,
            engine_kwargs=engine_kwargs,
        )

        return engine_wrapper.to_reader(
            lower_case=lower_case,
            read_kwargs=read_kwargs,
        )


class SnowflakeExtendedConnection(SnowflakeConnection):
    def __init__(
        self,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        self._connection_kwargs = kwargs

        super().__init__(**kwargs)  # pyright: ignore[reportUnknownMemberType]

    @classmethod
    def from_base(
        cls,
        connection: SnowflakeConnection,
        /,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        instance = cls.__new__(cls)
        instance.__dict__.update(connection.__dict__)
        instance._connection_kwargs = kwargs  # noqa: SLF001

        return instance

    def to_config(
        self,
        **config_kwargs: Any,  # noqa: ANN401
    ) -> SnowflakeConfig:
        return SnowflakeConfig(
            account=self.account,
            user=self.user,
            role=self.role,
            warehouse=self.warehouse,
            database=self.database,
            schema=self.schema,
            **config_kwargs,
        )

    @contextmanager
    def execute_query(
        self,
        query: str,
        /,
        *,
        execute_kwargs: Mapping[str, Any] | None = None,
    ) -> Generator[SnowflakeCursor]:
        cursor = self.cursor()

        logger.debug(f"Executing Snowflake query ({len(query)} chars)")

        try:
            cursor.execute(
                command=query,
                **(execute_kwargs or {}),
            )

            logger.debug(f"Snowflake query completed with query id {cursor.sfqid}")

            yield cursor
        finally:
            cursor.close()

    def read_lists(
        self,
        query: str,
        /,
        *,
        execute_kwargs: Mapping[str, Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        with self.execute_query(
            query,
            execute_kwargs=execute_kwargs,
        ) as cursor:
            return cursor.fetchall()

    def read_pandas(
        self,
        query: str,
        /,
        *,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
        execute_kwargs: Mapping[str, Any] | None = None,
    ) -> pd.DataFrame:
        default_read_kwargs: dict[str, Any] = {}

        with self.execute_query(
            query,
            execute_kwargs=execute_kwargs,
        ) as cursor:
            df = cursor.fetch_pandas_all(
                **(default_read_kwargs | dict(read_kwargs or {})),
            )

        if lower_case:
            df.columns = df.columns.str.lower()

        return df

    def read_arrow(
        self,
        query: str,
        /,
        *,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
        execute_kwargs: Mapping[str, Any] | None = None,
    ) -> ArrowTable:
        default_read_kwargs: dict[str, Any] = {
            "force_return_table": True,
        }

        with self.execute_query(
            query,
            execute_kwargs=execute_kwargs,
        ) as cursor:
            df: ArrowTable | None = cursor.fetch_arrow_all(
                **(default_read_kwargs | dict(read_kwargs or {})),
            )

        if df is None:
            df = ArrowTable()

        if lower_case:
            df = df.rename_columns(names=[col.lower() for col in df.column_names])

        return df

    def read_polars(
        self,
        query: str,
        /,
        *,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
        execute_kwargs: Mapping[str, Any] | None = None,
        schema_overrides: SchemaDict | None = None,
    ) -> pl.DataFrame:
        table = self.read_arrow(
            query,
            lower_case=lower_case,
            read_kwargs=read_kwargs,
            execute_kwargs=execute_kwargs,
        )

        df: pl.DataFrame | pl.Series = pl.from_arrow(  # pyright: ignore[reportUnknownMemberType]
            data=table,
            schema_overrides=schema_overrides,
        )

        if isinstance(df, pl.Series):
            df = df.to_frame()

        return df

    def to_reader(
        self,
        /,
        *,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
        execute_kwargs: Mapping[str, Any] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> QueryReader:
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
                    execute_kwargs=execute_kwargs,
                )

            elif backend.name == "polars":
                df = self.read_polars(
                    query,
                    lower_case=lower_case,
                    read_kwargs=read_kwargs,
                    execute_kwargs=execute_kwargs,
                    schema_overrides=kwargs.get("schema_overrides"),
                )

            else:
                msg = f"Unsupported backend: {backend.name!r}"
                raise ValueError(msg)

            return cast("DataFrameType", df)

        return reader

    def stream_lists(
        self,
        query: str,
        /,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        execute_kwargs: Mapping[str, Any] | None = None,
    ) -> Iterator[list[tuple[Any, ...]]]:
        with self.execute_query(
            query,
            execute_kwargs=execute_kwargs,
        ) as cursor:
            while rows := cursor.fetchmany(size=chunk_size):
                yield rows

    def stream_pandas(
        self,
        query: str,
        /,
        *,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
        execute_kwargs: Mapping[str, Any] | None = None,
    ) -> Iterator[pd.DataFrame]:
        with self.execute_query(
            query,
            execute_kwargs=execute_kwargs,
        ) as cursor:
            for df in cursor.fetch_pandas_batches(**dict(read_kwargs or {})):
                yield (
                    df
                    if not lower_case
                    else df.rename(
                        columns=str.lower,
                    )
                )

    def stream_arrow(
        self,
        query: str,
        /,
        *,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
        execute_kwargs: Mapping[str, Any] | None = None,
    ) -> Iterator[ArrowTable]:
        with self.execute_query(
            query,
            execute_kwargs=execute_kwargs,
        ) as cursor:
            for table in cursor.fetch_arrow_batches(**dict(read_kwargs or {})):
                yield (
                    table
                    if not lower_case
                    else table.rename_columns(
                        names=[col.lower() for col in table.column_names],
                    )
                )

    def stream_polars(
        self,
        query: str,
        /,
        *,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
        execute_kwargs: Mapping[str, Any] | None = None,
        schema_overrides: SchemaDict | None = None,
    ) -> Iterator[pl.DataFrame]:
        for table in self.stream_arrow(
            query,
            lower_case=lower_case,
            read_kwargs=read_kwargs,
            execute_kwargs=execute_kwargs,
        ):
            df: pl.DataFrame | pl.Series = pl.from_arrow(  # pyright: ignore[reportUnknownMemberType]
                data=table,
                schema_overrides=schema_overrides,
            )

            yield df if not isinstance(df, pl.Series) else df.to_frame()

    def to_streamer(
        self,
        /,
        *,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
        execute_kwargs: Mapping[str, Any] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> QueryStreamer:
        def streamer[DataFrameType: DataFrames = pd.DataFrame](
            query: str,
            /,
            *,
            backend: Backend[DataFrameType] | None = None,
        ) -> Iterator[DataFrameType]:
            backend = (
                backend
                if backend is not None
                else cast(
                    "Backend[DataFrameType]",
                    default_backend(),
                )
            )

            if backend.name == "pandas":
                return cast(
                    "Iterator[DataFrameType]",
                    self.stream_pandas(
                        query,
                        lower_case=lower_case,
                        read_kwargs=read_kwargs,
                        execute_kwargs=execute_kwargs,
                    ),
                )

            if backend.name == "polars":
                return cast(
                    "Iterator[DataFrameType]",
                    self.stream_polars(
                        query,
                        lower_case=lower_case,
                        read_kwargs=read_kwargs,
                        execute_kwargs=execute_kwargs,
                        schema_overrides=kwargs.get("schema_overrides"),
                    ),
                )

            msg = f"Unsupported backend: {backend.name!r}"
            raise ValueError(msg)

        return streamer


class SnowparkExtendedSession(SnowparkSession):
    @classmethod
    def from_base(
        cls,
        session: SnowparkSession,
        /,
    ) -> Self:
        instance = cls.__new__(cls)
        instance.__dict__.update(session.__dict__)

        return instance

    def to_connection(
        self,
    ) -> SnowflakeExtendedConnection:
        return SnowflakeExtendedConnection.from_base(
            self.connection,
        )

    def to_config(
        self,
        **config_kwargs: Any,  # noqa: ANN401
    ) -> SnowflakeConfig:
        return self.to_connection().to_config(**config_kwargs)

    def query_to_dataframe(
        self,
        query: str,
        /,
        *,
        lower_case: bool = True,
    ) -> mpd.DataFrame:
        df = cast("mpd.DataFrame", mpd.read_snowflake(query))  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

        if lower_case:
            df.columns = df.columns.str.lower()

        return df

    def table_to_dataframe(
        self,
        table: str,
        /,
        *,
        lower_case: bool = True,
    ) -> mpd.DataFrame:
        return self.query_to_dataframe(
            table,
            lower_case=lower_case,
        )

    def read_concurrent_queries(
        self,
        queries: Sequence[Callable[[SnowparkExtendedSession], mpd.DataFrame]],
    ) -> tuple[mpd.DataFrame, ...]:

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(query, self) for query in queries]
            results = [future.result() for future in futures]

        return tuple(results)

    @contextmanager
    def using(
        self,
        /,
        *,
        role: str | None = None,
        warehouse: str | None = None,
        database: str | None = None,
        schema: str | None = None,
    ) -> Generator[Self]:
        dimensions: tuple[tuple[Callable[[], str | None], Callable[[str], None], str | None], ...] = (
            (self.get_current_role, self.use_role, role),
            (self.get_current_warehouse, self.use_warehouse, warehouse),
            (self.get_current_database, self.use_database, database),
            (self.get_current_schema, self.use_schema, schema),
        )

        restores: list[tuple[Callable[[str], None], str]] = []
        for getter, setter, requested in dimensions:
            if requested is None:
                continue

            previous = getter()
            if previous is not None:
                restores.append((setter, previous))

            setter(requested)

        try:
            yield self
        finally:
            for setter, previous in restores:
                setter(previous)


__all__ = [
    "Authentication",
    "SnowflakeConfig",
    "SnowflakeExtendedConnection",
    "SnowparkExtendedSession",
]
