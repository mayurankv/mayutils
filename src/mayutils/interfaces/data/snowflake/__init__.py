"""
Configure Snowflake connections and expose them to the ``mayutils`` data layer.

This module is the Snowflake adapter within
:mod:`mayutils.interfaces.data`. It centralises connection identity and
authentication in a :class:`SnowflakeConfig` model u2014 built directly from
explicit values or, via :meth:`SnowflakeConfig.from_env`, from
``SNOWFLAKE_*`` environment variables u2014 and bridges that configuration
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
in u2014 every connection parameter comes from the caller, explicitly or
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
    from snowflake.connector import SnowflakeConnection
    from snowflake.snowpark.session import Session as SnowparkSession

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterator, Mapping, Sequence

    import modin.pandas as mpd
    import pandas as pd
    import polars as pl
    from polars._typing import SchemaDict
    from pyarrow import (
        Table as ArrowTable,
    )  # pyright: ignore[reportMissingModuleSource]
    from snowflake.connector.cursor import SnowflakeCursor

    from mayutils.data.read import QueryReader, QueryStreamer


logger = Logger.spawn()


class Authentication(StrEnum):
    """
    Enumerate the supported Snowflake authentication methods.

    A string enumeration whose members select how :class:`SnowflakeConfig`
    authenticates against Snowflake. The default, ``browser``, drives
    external-browser single sign-on, while the three ``private_key_*``
    members select key-pair authentication and differ only in how the key
    material held on the configuration is encoded and decrypted.

    Attributes
    ----------
    browser
        External-browser single sign-on; no key material required.
    private_key_pem
        Encrypted PEM private key, decrypted with the configured
        private-key password.
    private_key_der
        Base64-encoded encrypted DER private key, decrypted with the
        configured private-key password.
    private_key_raw
        Unencrypted DER private key, used as-is.

    See Also
    --------
    SnowflakeConfig : Configuration model consuming this enumeration.
    SnowflakeConfig.unencrypted_private_key : Decrypts keys according to the member chosen.

    Examples
    --------
    >>> from mayutils.interfaces.data.snowflake import Authentication
    >>> Authentication.browser
    <Authentication.browser: 'browser'>
    >>> Authentication("private_key_pem")
    <Authentication.private_key_pem: 'private_key_pem'>
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
        "client_session_keep_alive": True,
        "client_store_temporary_credential": True,
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
        **overrides: Any,  # noqa: ANN401
    ) -> Self:
        """
        Build a configuration from ``SNOWFLAKE_*`` environment variables.

        Loads *env_file* into the process environment (when given) and then
        reads one variable per field, prefixed with ``SNOWFLAKE_`` and
        upper-cased u2014 so ``account`` is read from ``SNOWFLAKE_ACCOUNT`` and
        ``schema`` (the ``schema_`` alias) from ``SNOWFLAKE_SCHEMA``. Empty
        or unset variables are skipped, leaving field defaults in place, and
        the same validation as direct construction applies, so a missing
        required value raises naming the offending field.

        Parameters
        ----------
        env_file
            Dotenv file loaded before reading the environment. ``None``
            reads the existing environment without loading a file.
        **overrides
            Extra field values, keyed by field name or alias, overriding those
            read from the environment.

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

        return cls.model_validate(values).update(**overrides)

    def update(
        self,
        **updates: Any,  # noqa: ANN401
    ) -> Self:
        """
        Build a copy of the configuration with the given fields replaced.

        Re-validates the merged values through the model constructor rather
        than mutating in place, so the result is a fresh, fully validated
        configuration and the original is left untouched. Field aliases are
        respected, meaning the default schema is overridden with ``schema``
        rather than ``schema_``.

        Parameters
        ----------
        **updates
            Field values, keyed by field name or alias, overriding those of
            the current configuration.

        Returns
        -------
            A new validated configuration with the updates applied.

        See Also
        --------
        SnowflakeConfig.from_env : Build a configuration from environment variables.
        SnowparkExtendedSession.using : Temporary, session-level counterpart.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> config = SnowflakeConfig(account="ab12345.eu-west-1", user="me@example.com")
        >>> config.update(role="ANALYST").role
        'ANALYST'
        >>> config.role is None
        True
        """
        current = {
            (field_info.alias or field_name): getattr(self, field_name) for field_name, field_info in type(self).model_fields.items()
        }

        return type(self).model_validate(current | updates)

    @property
    def unencrypted_private_key(
        self,
    ) -> bytes | None:
        """
        Decrypt and normalise the configured private key.

        Reads the key material from :attr:`private_key` u2014 inline or from a
        file path u2014 decrypts it with :attr:`private_key_password` according
        to the configured :class:`Authentication` member, and re-serialises
        it as unencrypted PKCS#8 DER, the form the Snowflake connector
        expects. When no private key is configured, as under browser
        authentication, ``None`` is returned instead.

        Returns
        -------
            The unencrypted DER-encoded private key, or ``None`` when no key is configured.

        Raises
        ------
        ValueError
            If a private key is set but :attr:`authentication` is not one
            of the private-key methods.

        See Also
        --------
        Authentication : Enumeration of the supported authentication methods.
        SnowflakeConfig.get_connection_arguments : Injects this key into the connector arguments.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> config = SnowflakeConfig(account="ab12345.eu-west-1", user="me@example.com")
        >>> config.unencrypted_private_key is None
        True
        """
        with may_require_extras():
            from cryptography.hazmat.backends.openssl import backend
            from cryptography.hazmat.primitives import serialization

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
        """
        Assemble the core Snowflake connection parameters.

        Builds the mapping shared by every connection style in this module:
        ``account`` and ``user`` always, the optional ``role``,
        ``warehouse``, ``database`` and ``schema`` only when set, and the
        ``externalbrowser`` authenticator when browser authentication is
        configured. Credential-style arguments such as the private key are
        deliberately excluded and supplied by
        :meth:`get_connection_arguments` instead.

        Returns
        -------
            The connection parameters, with unset optional fields omitted.

        See Also
        --------
        SnowflakeConfig.get_connection_arguments : Companion mapping of connector arguments.
        SnowflakeConfig.url : SQLAlchemy URL rendered from these parameters.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> config = SnowflakeConfig(account="ab12345.eu-west-1", user="me@example.com")
        >>> sorted(config.connection_parameters)
        ['account', 'authenticator', 'user']
        """
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
        """
        Render the configuration as a Snowflake SQLAlchemy URL.

        Feeds :attr:`connection_parameters` through
        ``snowflake.sqlalchemy.URL`` so the configuration can be handed to
        plain SQLAlchemy tooling. The URL carries only identity parameters;
        connector arguments such as private keys must still be supplied
        separately, as :meth:`to_engine_wrapper` does via ``connect_args``.

        Returns
        -------
            The ``snowflake://`` SQLAlchemy connection URL.

        See Also
        --------
        SnowflakeConfig.connection_parameters : Parameters encoded into the URL.
        SnowflakeConfig.to_engine_wrapper : Higher-level engine construction.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> config = SnowflakeConfig(account="ab12345.eu-west-1", user="me@example.com")
        >>> config.url.startswith("snowflake://")
        True
        """
        with may_require_extras():
            from snowflake.sqlalchemy import URL  # pyright: ignore[reportUnknownVariableType, reportAttributeAccessIssue]

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
        """
        Build the connector arguments implied by the configuration.

        Starts from :attr:`DEFAULT_CONNECTION_ARGUMENTS`, overlays any
        caller-supplied overrides and, for encrypted private-key
        authentication, injects the decrypted key together with
        ``client_session_keep_alive``. The result complements
        :attr:`connection_parameters`: together the two mappings form the
        full keyword set accepted by the Snowflake connector.

        Parameters
        ----------
        **kwargs
            Connector arguments overriding the defaults.

        Returns
        -------
            The merged connector arguments.

        See Also
        --------
        SnowflakeConfig.connection_parameters : Identity parameters merged alongside these.
        SnowflakeConfig.unencrypted_private_key : Key material injected for key-pair authentication.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> config = SnowflakeConfig(account="ab12345.eu-west-1", user="me@example.com")
        >>> config.get_connection_arguments()["disable_ocsp_checks"]
        True
        """
        kwargs = self.DEFAULT_CONNECTION_ARGUMENTS | kwargs

        if self.authentication in (
            Authentication.private_key_pem,
            Authentication.private_key_der,
        ):
            kwargs["private_key"] = self.unencrypted_private_key

        return kwargs

    def to_engine_wrapper(
        self,
        *,
        connection_arguments: Mapping[str, Any] | None = None,
        engine_kwargs: Mapping[str, Any] | None = None,
    ) -> EngineWrapper:
        """
        Build a reusable SQLAlchemy engine wrapper for this configuration.

        Combines :attr:`connection_parameters` with the connector arguments
        from :meth:`get_connection_arguments` and hands them to
        :meth:`mayutils.environment.databases.EngineWrapper.via_snowflake`.
        The wrapper owns a lazily connecting engine, so no Snowflake
        session is opened until a query is actually executed against it.

        Parameters
        ----------
        connection_arguments
            Connector argument overrides merged into ``connect_args``.
        engine_kwargs
            Extra keyword arguments forwarded to engine creation.

        Returns
        -------
            An engine wrapper bound to this configuration.

        See Also
        --------
        mayutils.environment.databases.EngineWrapper : The returned engine facade.
        SnowflakeConfig.to_reader : Reader built on top of this wrapper.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> config = SnowflakeConfig.from_env()  # doctest: +SKIP
        >>> wrapper = config.to_engine_wrapper()  # doctest: +SKIP
        """
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
        """
        Open an extended Snowflake connector connection.

        Merges :attr:`connection_parameters`, the connector arguments from
        :meth:`get_connection_arguments` and any extra keyword arguments,
        then opens a live :class:`SnowflakeExtendedConnection`. Unlike
        :meth:`to_engine_wrapper` this connects immediately, triggering
        browser single sign-on when that authentication method is
        configured.

        Parameters
        ----------
        connection_arguments
            Connector argument overrides merged into the defaults.
        **kwargs
            Final overrides applied on top of every other parameter source.

        Returns
        -------
            An open extended connection to the configured account.

        See Also
        --------
        SnowflakeExtendedConnection : The returned connection type.
        SnowflakeConfig.to_snowpark_session : Snowpark counterpart of this method.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> connection = SnowflakeConfig.from_env().to_connection()  # doctest: +SKIP
        """
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
        *,
        fresh_session: bool = False,
        **session_kwargs: Any,  # noqa: ANN401
    ) -> SnowparkExtendedSession:
        """
        Create or reuse a Snowpark session for this configuration.

        Loads the Snowpark Modin plugin, merges
        :attr:`connection_parameters` with the connector arguments and any
        overrides, and builds the session with telemetry disabled. By
        default the builder reuses an existing matching session via
        ``getOrCreate``; passing ``fresh_session=True`` forces a brand-new
        session instead.

        Parameters
        ----------
        fresh_session
            Whether to force creation of a new session rather than reusing
            an existing one.
        **session_kwargs
            Final session options applied on top of every other source.

        Returns
        -------
            An extended Snowpark session for the configured account.

        See Also
        --------
        SnowparkExtendedSession : The returned session type.
        SnowflakeConfig.to_connection : Connector-level counterpart of this method.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> session = SnowflakeConfig.from_env().to_snowpark_session()  # doctest: +SKIP
        """
        with may_require_extras():
            import snowflake.snowpark.modin.plugin  # pyright: ignore[reportUnusedImport] # noqa: F401

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
        """
        Build a backend-aware query reader from this configuration.

        Convenience composition of :meth:`to_engine_wrapper` and
        :meth:`mayutils.environment.databases.EngineWrapper.to_reader`: the
        returned callable executes a query and returns a dataframe in the
        requested backend, making the configuration directly usable with
        :func:`mayutils.data.read.read_query`.

        Parameters
        ----------
        lower_case
            Whether to lower-case the column names of returned frames.
        read_kwargs
            Extra keyword arguments forwarded to the underlying read calls.
        connection_arguments
            Connector argument overrides used when building the engine.
        engine_kwargs
            Extra keyword arguments forwarded to engine creation.

        Returns
        -------
            A reader executing queries against the configured account.

        See Also
        --------
        mayutils.data.read.read_query : Cached query execution consuming the reader.
        SnowflakeExtendedConnection.to_reader : Connector-level equivalent of this method.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> reader = SnowflakeConfig.from_env().to_reader()  # doctest: +SKIP
        >>> df = reader("SELECT 1")  # doctest: +SKIP
        """
        engine_wrapper = self.to_engine_wrapper(
            connection_arguments=connection_arguments,
            engine_kwargs=engine_kwargs,
        )

        return engine_wrapper.to_reader(
            lower_case=lower_case,
            read_kwargs=read_kwargs,
        )


class SnowflakeExtendedConnection(SnowflakeConnection):
    """
    Extend the Snowflake connector connection with dataframe helpers.

    A drop-in subclass of :class:`snowflake.connector.SnowflakeConnection`
    adding the conveniences this library leans on: cursor-managed query
    execution (:meth:`execute_query`), eager reads into lists, pandas,
    Arrow or Polars (:meth:`read_lists`, :meth:`read_pandas`,
    :meth:`read_arrow`, :meth:`read_polars`), chunked streaming
    counterparts (:meth:`stream_lists` and friends) and adapters into the
    shared data layer (:meth:`to_reader`, :meth:`to_streamer`). It also
    remembers its construction keyword arguments and can wrap an existing
    base connection without reconnecting via :meth:`from_base`.

    Parameters
    ----------
    **kwargs
        Connection parameters forwarded verbatim to
        :class:`snowflake.connector.SnowflakeConnection`.

    See Also
    --------
    SnowflakeConfig.to_connection : Preferred constructor from a configuration.
    SnowparkExtendedSession : Snowpark analogue of this class.

    Examples
    --------
    >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
    >>> connection = SnowflakeConfig.from_env().to_connection()  # doctest: +SKIP
    >>> connection.read_lists("SELECT 1")  # doctest: +SKIP
    [(1,)]
    """

    def __init__(
        self,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """
        Open an extended Snowflake connection.

        Records the construction keyword arguments on the instance before
        delegating to the base
        :class:`snowflake.connector.SnowflakeConnection` initialiser, so
        the connection parameters can later be recovered (for example by
        :meth:`to_config`) without inspecting the live connection.

        Parameters
        ----------
        **kwargs
            Connection parameters forwarded verbatim to
            :class:`snowflake.connector.SnowflakeConnection`.

        See Also
        --------
        SnowflakeConfig.to_connection : Preferred constructor from a configuration.
        SnowflakeExtendedConnection.from_base : Wraps an already-open base connection.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeExtendedConnection
        >>> connection = SnowflakeExtendedConnection(account="...", user="...")  # doctest: +SKIP
        """
        self._connection_kwargs = kwargs

        super().__init__(**kwargs)  # pyright: ignore[reportUnknownMemberType]

    @classmethod
    def from_base(
        cls,
        connection: SnowflakeConnection,
        /,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """
        Wrap an existing base connection in the extended subclass.

        Creates the instance with ``__new__`` and copies the base
        connection's state across, so the already-open connection is reused
        as-is u2014 no new session, login or network round-trip occurs. The
        recorded construction keyword arguments are set from ``kwargs``
        rather than recovered from the base connection.

        Parameters
        ----------
        connection
            The open base connection whose state is adopted.
        **kwargs
            Construction keyword arguments to record on the instance.

        Returns
        -------
            The same underlying connection, retyped as the extended class.

        See Also
        --------
        SnowflakeConfig.to_connection : Builds an extended connection directly.
        SnowparkExtendedSession.to_connection : Uses this to wrap a session's connection.

        Examples
        --------
        >>> from snowflake.connector import connect
        >>> from mayutils.interfaces.data.snowflake import SnowflakeExtendedConnection
        >>> base = connect(account="...", user="...")  # doctest: +SKIP
        >>> connection = SnowflakeExtendedConnection.from_base(base)  # doctest: +SKIP
        """
        instance = cls.__new__(cls)
        instance.__dict__.update(connection.__dict__)
        instance._connection_kwargs = kwargs  # noqa: SLF001

        return instance

    def to_config(
        self,
        **config_kwargs: Any,  # noqa: ANN401
    ) -> SnowflakeConfig:
        """
        Capture the connection's identity in a configuration model.

        Reads the account, user, role, warehouse, database and schema off
        the live connection and validates them into a
        :class:`SnowflakeConfig`, letting a connection obtained elsewhere
        be reused to mint engine wrappers, readers or Snowpark sessions.
        Authentication settings are not recoverable from a live connection,
        so they fall back to the model defaults unless overridden.

        Parameters
        ----------
        **config_kwargs
            Extra field values, such as ``authentication``, merged into the
            configuration.

        Returns
        -------
            A configuration mirroring the connection's identity.

        See Also
        --------
        SnowflakeConfig : The returned model.
        SnowflakeConfig.to_connection : Inverse operation building a connection.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> connection = SnowflakeConfig.from_env().to_connection()  # doctest: +SKIP
        >>> config = connection.to_config()  # doctest: +SKIP
        """
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
        """
        Execute a query on a managed cursor.

        Opens a fresh cursor, runs the query and yields the cursor with its
        results pending, so the caller chooses the fetch style; the cursor
        is always closed when the context exits, including on error. This
        is the primitive every ``read_*`` and ``stream_*`` helper on this
        class is built from.

        Parameters
        ----------
        query
            SQL text to execute.
        execute_kwargs
            Extra keyword arguments forwarded to the cursor's ``execute``.

        Yields
        ------
            The cursor with the executed query's results available.

        See Also
        --------
        SnowflakeExtendedConnection.read_lists : Fetches all rows from this cursor.
        SnowflakeExtendedConnection.stream_lists : Streams rows from this cursor.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> connection = SnowflakeConfig.from_env().to_connection()  # doctest: +SKIP
        >>> with connection.execute_query("SELECT 1") as cursor:  # doctest: +SKIP
        ...     rows = cursor.fetchall()
        """
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
        """
        Run a query and fetch every row as tuples.

        Thin convenience over :meth:`execute_query` that materialises the
        whole result set with ``fetchall``, suited to small results where a
        dataframe would be overkill. Column names are not returned; reach
        for the dataframe readers when structure matters.

        Parameters
        ----------
        query
            SQL text to execute.
        execute_kwargs
            Extra keyword arguments forwarded to the cursor's ``execute``.

        Returns
        -------
            All result rows as a list of tuples.

        See Also
        --------
        SnowflakeExtendedConnection.read_pandas : Structured pandas counterpart.
        SnowflakeExtendedConnection.stream_lists : Chunked counterpart of this method.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> connection = SnowflakeConfig.from_env().to_connection()  # doctest: +SKIP
        >>> connection.read_lists("SELECT 1")  # doctest: +SKIP
        [(1,)]
        """
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
        """
        Run a query and return the full result as a pandas dataframe.

        Executes through :meth:`execute_query` and materialises the result
        with the connector's native ``fetch_pandas_all``, avoiding a
        round-trip through SQLAlchemy. Column names are lower-cased by
        default to match the conventions of the wider data layer.

        Parameters
        ----------
        query
            SQL text to execute.
        lower_case
            Whether to lower-case the returned column names.
        read_kwargs
            Extra keyword arguments forwarded to ``fetch_pandas_all``.
        execute_kwargs
            Extra keyword arguments forwarded to the cursor's ``execute``.

        Returns
        -------
            The query result as a pandas dataframe.

        See Also
        --------
        SnowflakeExtendedConnection.read_polars : Polars counterpart of this method.
        SnowflakeExtendedConnection.stream_pandas : Chunked counterpart of this method.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> connection = SnowflakeConfig.from_env().to_connection()  # doctest: +SKIP
        >>> df = connection.read_pandas("SELECT 1 AS one")  # doctest: +SKIP
        """
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
        """
        Run a query and return the full result as an Arrow table.

        Executes through :meth:`execute_query` and collects the result with
        the connector's ``fetch_arrow_all``, falling back to an empty table
        so callers always receive a concrete :class:`pyarrow.Table`. This
        is also the transport behind :meth:`read_polars`, which converts
        the table without a pandas detour.

        Parameters
        ----------
        query
            SQL text to execute.
        lower_case
            Whether to lower-case the returned column names.
        read_kwargs
            Extra keyword arguments forwarded to ``fetch_arrow_all``.
        execute_kwargs
            Extra keyword arguments forwarded to the cursor's ``execute``.

        Returns
        -------
            The query result as an Arrow table.

        See Also
        --------
        SnowflakeExtendedConnection.read_polars : Polars conversion of this table.
        SnowflakeExtendedConnection.stream_arrow : Chunked counterpart of this method.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> connection = SnowflakeConfig.from_env().to_connection()  # doctest: +SKIP
        >>> table = connection.read_arrow("SELECT 1 AS one")  # doctest: +SKIP
        """
        with may_require_extras():
            from pyarrow import (
                Table as ArrowTable,
            )  # pyright: ignore[reportUnknownVariableType]
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
        """
        Run a query and return the full result as a Polars dataframe.

        Fetches the result as Arrow via :meth:`read_arrow` and converts it
        with :func:`polars.from_arrow`, so the data crosses from the
        connector into Polars without a pandas detour. Single-column
        results that convert to a series are promoted back to a one-column
        dataframe for a consistent return type.

        Parameters
        ----------
        query
            SQL text to execute.
        lower_case
            Whether to lower-case the returned column names.
        read_kwargs
            Extra keyword arguments forwarded to the Arrow fetch.
        execute_kwargs
            Extra keyword arguments forwarded to the cursor's ``execute``.
        schema_overrides
            Polars schema overrides applied during conversion.

        Returns
        -------
            The query result as a Polars dataframe.

        See Also
        --------
        SnowflakeExtendedConnection.read_arrow : Source of the converted table.
        SnowflakeExtendedConnection.stream_polars : Chunked counterpart of this method.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> connection = SnowflakeConfig.from_env().to_connection()  # doctest: +SKIP
        >>> df = connection.read_polars("SELECT 1 AS one")  # doctest: +SKIP
        """
        with may_require_extras():
            import polars as pl

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
        """
        Build a backend-aware query reader bound to this connection.

        Closes the reading options over a callable satisfying
        :class:`mayutils.data.read.QueryReader`: invoked with a query and
        an optional :class:`~mayutils.objects.dataframes.backends.Backend`,
        it dispatches to :meth:`read_pandas` or :meth:`read_polars`,
        falling back to the process-wide default backend when none is
        given. The reader plugs straight into
        :func:`mayutils.data.read.read_query`.

        Parameters
        ----------
        lower_case
            Whether to lower-case the column names of returned frames.
        read_kwargs
            Extra keyword arguments forwarded to the underlying fetches.
        execute_kwargs
            Extra keyword arguments forwarded to the cursor's ``execute``.
        **kwargs
            Backend-specific options such as ``schema_overrides`` for Polars.

        Returns
        -------
            A reader executing queries on this connection.

        See Also
        --------
        mayutils.data.read.read_query : Cached query execution consuming the reader.
        SnowflakeExtendedConnection.to_streamer : Streaming counterpart of this method.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> reader = SnowflakeConfig.from_env().to_connection().to_reader()  # doctest: +SKIP
        >>> df = reader("SELECT 1")  # doctest: +SKIP
        """

        def reader[DataFrameType: DataFrames = pd.DataFrame](
            query: str,
            /,
            *,
            backend: Backend[DataFrameType] | None = None,
        ) -> DataFrameType:
            """
            Execute the query against the captured connection.

            Closure that dispatches to
            :meth:`SnowflakeExtendedConnection.read_pandas` or
            :meth:`SnowflakeExtendedConnection.read_polars` depending on
            the requested backend, forwarding the captured reading
            options. It satisfies the
            :class:`~mayutils.data.read.QueryReader` protocol.

            Parameters
            ----------
            query
                Fully-rendered SQL string ready for execution.
            backend
                DataFrame backend token. Defaults to pandas when
                ``None``.

            Returns
            -------
                Materialised query result in the requested DataFrame
                flavour.

            Raises
            ------
            ValueError
                If the backend is neither pandas nor polars.

            See Also
            --------
            mayutils.data.read.QueryReader : Protocol this closure satisfies.
            SnowflakeExtendedConnection.to_reader : Factory that builds this closure.

            Examples
            --------
            >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
            >>> reader = SnowflakeConfig.from_env().to_connection().to_reader()  # doctest: +SKIP
            >>> df = reader("SELECT 1")  # doctest: +SKIP
            """
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
        """
        Stream a query's rows in fixed-size chunks of tuples.

        Executes through :meth:`execute_query` and repeatedly calls
        ``fetchmany``, yielding each non-empty batch as it arrives so
        results larger than memory can be consumed incrementally. The
        managed cursor stays open for the lifetime of the generator and is
        closed when iteration finishes or the generator is discarded.

        Parameters
        ----------
        query
            SQL text to execute.
        chunk_size
            Maximum number of rows per yielded batch.
        execute_kwargs
            Extra keyword arguments forwarded to the cursor's ``execute``.

        Yields
        ------
            Successive batches of result rows as lists of tuples.

        See Also
        --------
        SnowflakeExtendedConnection.read_lists : Eager counterpart of this method.
        SnowflakeExtendedConnection.stream_pandas : Dataframe streaming equivalent.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> connection = SnowflakeConfig.from_env().to_connection()  # doctest: +SKIP
        >>> for rows in connection.stream_lists("SELECT 1"):  # doctest: +SKIP
        ...     print(len(rows))
        """
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
        """
        Stream a query's result as pandas dataframe batches.

        Executes through :meth:`execute_query` and yields the connector's
        native ``fetch_pandas_batches`` chunks one at a time, optionally
        lower-casing column names per batch. Batch sizing follows the
        connector's result chunking rather than an explicit row count.

        Parameters
        ----------
        query
            SQL text to execute.
        lower_case
            Whether to lower-case column names on each batch.
        read_kwargs
            Extra keyword arguments forwarded to ``fetch_pandas_batches``.
        execute_kwargs
            Extra keyword arguments forwarded to the cursor's ``execute``.

        Yields
        ------
            Successive batches of the result as pandas dataframes.

        See Also
        --------
        SnowflakeExtendedConnection.read_pandas : Eager counterpart of this method.
        SnowflakeExtendedConnection.stream_arrow : Arrow streaming equivalent.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> connection = SnowflakeConfig.from_env().to_connection()  # doctest: +SKIP
        >>> for df in connection.stream_pandas("SELECT 1 AS one"):  # doctest: +SKIP
        ...     print(df.shape)
        """
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
        """
        Stream a query's result as Arrow table batches.

        Executes through :meth:`execute_query` and yields the connector's
        ``fetch_arrow_batches`` chunks one at a time, optionally
        lower-casing column names per table. This is the transport behind
        :meth:`stream_polars` and never materialises the full result.

        Parameters
        ----------
        query
            SQL text to execute.
        lower_case
            Whether to lower-case column names on each batch.
        read_kwargs
            Extra keyword arguments forwarded to ``fetch_arrow_batches``.
        execute_kwargs
            Extra keyword arguments forwarded to the cursor's ``execute``.

        Yields
        ------
            Successive batches of the result as Arrow tables.

        See Also
        --------
        SnowflakeExtendedConnection.read_arrow : Eager counterpart of this method.
        SnowflakeExtendedConnection.stream_polars : Polars conversion of these batches.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> connection = SnowflakeConfig.from_env().to_connection()  # doctest: +SKIP
        >>> for table in connection.stream_arrow("SELECT 1 AS one"):  # doctest: +SKIP
        ...     print(table.num_rows)
        """
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
        """
        Stream a query's result as Polars dataframe batches.

        Consumes :meth:`stream_arrow` and converts each Arrow batch with
        :func:`polars.from_arrow`, promoting any series produced by a
        single-column batch back to a one-column dataframe. Schema
        overrides are applied to every batch, keeping types consistent
        across the whole stream.

        Parameters
        ----------
        query
            SQL text to execute.
        lower_case
            Whether to lower-case column names on each batch.
        read_kwargs
            Extra keyword arguments forwarded to the Arrow batch fetch.
        execute_kwargs
            Extra keyword arguments forwarded to the cursor's ``execute``.
        schema_overrides
            Polars schema overrides applied to every batch.

        Yields
        ------
            Successive batches of the result as Polars dataframes.

        See Also
        --------
        SnowflakeExtendedConnection.stream_arrow : Source of the converted batches.
        SnowflakeExtendedConnection.read_polars : Eager counterpart of this method.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> connection = SnowflakeConfig.from_env().to_connection()  # doctest: +SKIP
        >>> for df in connection.stream_polars("SELECT 1 AS one"):  # doctest: +SKIP
        ...     print(df.shape)
        """
        with may_require_extras():
            import polars as pl

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
        """
        Build a backend-aware query streamer bound to this connection.

        Streaming sibling of :meth:`to_reader`: the returned callable
        satisfies :class:`mayutils.data.read.QueryStreamer`, dispatching to
        :meth:`stream_pandas` or :meth:`stream_polars` according to the
        requested (or default) backend and returning the resulting iterator
        of dataframe batches. Suited to feeding incremental consumers such
        as :class:`mayutils.data.live.StreamingQuery`.

        Parameters
        ----------
        lower_case
            Whether to lower-case the column names of streamed frames.
        read_kwargs
            Extra keyword arguments forwarded to the underlying fetches.
        execute_kwargs
            Extra keyword arguments forwarded to the cursor's ``execute``.
        **kwargs
            Backend-specific options such as ``schema_overrides`` for Polars.

        Returns
        -------
            A streamer yielding dataframe batches for a query.

        See Also
        --------
        SnowflakeExtendedConnection.to_reader : Eager counterpart of this method.
        mayutils.data.live.StreamingQuery : Incremental consumer of the streamer.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> streamer = SnowflakeConfig.from_env().to_connection().to_streamer()  # doctest: +SKIP
        >>> for df in streamer("SELECT 1"):  # doctest: +SKIP
        ...     print(df.shape)
        """

        def streamer[DataFrameType: DataFrames = pd.DataFrame](
            query: str,
            /,
            *,
            backend: Backend[DataFrameType] | None = None,
        ) -> Iterator[DataFrameType]:
            """
            Stream the query against the captured connection.

            Closure that dispatches to
            :meth:`SnowflakeExtendedConnection.stream_pandas` or
            :meth:`SnowflakeExtendedConnection.stream_polars` depending
            on the requested backend, forwarding the captured streaming
            options. It satisfies the
            :class:`~mayutils.data.read.QueryStreamer` protocol.

            Parameters
            ----------
            query
                Fully-rendered SQL string ready for execution.
            backend
                DataFrame backend token. Defaults to pandas when
                ``None``.

            Returns
            -------
                Iterator over successive DataFrame chunks of the query
                result in the requested DataFrame flavour.

            Raises
            ------
            ValueError
                If the backend is neither pandas nor polars.

            See Also
            --------
            mayutils.data.read.QueryStreamer : Protocol this closure satisfies.
            SnowflakeExtendedConnection.to_streamer : Factory that builds this closure.

            Examples
            --------
            >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
            >>> streamer = SnowflakeConfig.from_env().to_connection().to_streamer()  # doctest: +SKIP
            >>> for df in streamer("SELECT 1"):  # doctest: +SKIP
            ...     print(df.shape)
            """
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
    """
    Extend the Snowpark session with Modin and configuration helpers.

    A drop-in subclass of :class:`snowflake.snowpark.session.Session`
    adding what this library needs on top: Modin dataframe reads from
    queries and tables (:meth:`query_to_dataframe`,
    :meth:`table_to_dataframe`), concurrent fan-out of multiple reads
    (:meth:`read_concurrent_queries`), temporary switching of role,
    warehouse, database and schema (:meth:`using`), bridges into the shared
    ``read``/``stream`` data layer (:meth:`to_reader`, :meth:`to_streamer`)
    and bridges back to the connector and configuration layers
    (:meth:`to_connection`, :meth:`to_config`). Instances are normally produced by
    :meth:`SnowflakeConfig.to_snowpark_session`, which retypes the session
    built by the Snowpark builder via :meth:`from_base`.

    See Also
    --------
    SnowflakeConfig.to_snowpark_session : Preferred constructor from a configuration.
    SnowflakeExtendedConnection : Connector analogue of this class.

    Examples
    --------
    >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
    >>> session = SnowflakeConfig.from_env().to_snowpark_session()  # doctest: +SKIP
    >>> df = session.query_to_dataframe("SELECT 1 AS one")  # doctest: +SKIP
    """

    @classmethod
    def from_base(
        cls,
        session: SnowparkSession,
        /,
    ) -> Self:
        """
        Wrap an existing base Snowpark session in the extended subclass.

        Creates the instance with ``__new__`` and copies the base session's
        state across, so the live session u2014 including its underlying
        connection u2014 is reused as-is and no new session is established.
        This is how :meth:`SnowflakeConfig.to_snowpark_session` retypes the
        session produced by the Snowpark builder.

        Parameters
        ----------
        session
            The open base session whose state is adopted.

        Returns
        -------
            The same underlying session, retyped as the extended class.

        See Also
        --------
        SnowflakeConfig.to_snowpark_session : Builds and wraps a session in one step.
        SnowflakeExtendedConnection.from_base : Connector analogue of this method.

        Examples
        --------
        >>> from snowflake.snowpark.session import Session
        >>> from mayutils.interfaces.data.snowflake import SnowparkExtendedSession
        >>> base = Session.builder.create()  # doctest: +SKIP
        >>> session = SnowparkExtendedSession.from_base(base)  # doctest: +SKIP
        """
        instance = cls.__new__(cls)
        instance.__dict__.update(session.__dict__)

        return instance

    def to_connection(
        self,
    ) -> SnowflakeExtendedConnection:
        """
        Expose the session's connection as an extended connection.

        Wraps the connector connection powering this Snowpark session in
        :class:`SnowflakeExtendedConnection` via
        :meth:`SnowflakeExtendedConnection.from_base`, sharing the live
        connection rather than opening a new one. This gives access to the
        cursor-level read and stream helpers without leaving the session.

        Returns
        -------
            The session's connection, retyped as the extended class.

        See Also
        --------
        SnowflakeExtendedConnection : The returned connection type.
        SnowparkExtendedSession.to_config : Configuration snapshot built on this.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> session = SnowflakeConfig.from_env().to_snowpark_session()  # doctest: +SKIP
        >>> connection = session.to_connection()  # doctest: +SKIP
        """
        return SnowflakeExtendedConnection.from_base(
            self.connection,
        )

    def to_config(
        self,
        **config_kwargs: Any,  # noqa: ANN401
    ) -> SnowflakeConfig:
        """
        Capture the session's identity in a configuration model.

        Convenience composition of :meth:`to_connection` and
        :meth:`SnowflakeExtendedConnection.to_config`, reading the account,
        user, role, warehouse, database and schema off the session's live
        connection. As with the connector version, authentication settings
        cannot be recovered and fall back to defaults unless overridden.

        Parameters
        ----------
        **config_kwargs
            Extra field values, such as ``authentication``, merged into the
            configuration.

        Returns
        -------
            A configuration mirroring the session's identity.

        See Also
        --------
        SnowflakeExtendedConnection.to_config : Underlying implementation.
        SnowflakeConfig.to_snowpark_session : Inverse operation building a session.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> session = SnowflakeConfig.from_env().to_snowpark_session()  # doctest: +SKIP
        >>> config = session.to_config()  # doctest: +SKIP
        """
        return self.to_connection().to_config(**config_kwargs)

    def query_to_dataframe(
        self,
        query: str,
        /,
        *,
        lower_case: bool = True,
        index_col: str | Sequence[str] | None = None,
        columns: Sequence[str] | None = None,
        enforce_ordering: bool = True,
    ) -> mpd.DataFrame:
        """
        Run a query and return the result as a Modin dataframe.

        Reads through ``modin.pandas.read_snowflake`` so execution stays
        inside Snowflake and the result is exposed as a lazily distributed
        Modin frame rather than being pulled locally up front. Column names
        are lower-cased by default to match the conventions of the wider
        data layer.

        Parameters
        ----------
        query
            SQL text, or a bare table name, to read.
        lower_case
            Whether to lower-case the returned column names.
        index_col
            Column name or names to use as the dataframe index; ``None``
            leaves the default integer index in place.
        columns
            Subset of column names to include in the result; ``None``
            returns all columns.
        enforce_ordering
            Whether to enforce the result ordering from Snowflake.

        Returns
        -------
            The query result as a Modin dataframe.

        See Also
        --------
        SnowparkExtendedSession.table_to_dataframe : Table-name convenience over this method.
        SnowflakeExtendedConnection.read_pandas : Local pandas counterpart.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> session = SnowflakeConfig.from_env().to_snowpark_session()  # doctest: +SKIP
        >>> df = session.query_to_dataframe("SELECT 1 AS one")  # doctest: +SKIP
        """
        with may_require_extras():
            import modin.pandas as mpd

        if index_col is not None and not isinstance(index_col, str):
            index_col = list(map(str.lower, index_col)) if lower_case else list(index_col)
        if columns is not None:
            columns = list(map(str.lower, columns)) if lower_case else list(columns)

        df = cast(
            "mpd.DataFrame",
            mpd.read_snowflake(  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
                query,
                index_col=index_col,
                columns=columns,
                enforce_ordering=enforce_ordering,
            ),
        )

        if lower_case:
            df.columns = df.columns.str.lower()

        return df

    def table_to_dataframe(
        self,
        table: str,
        /,
        *,
        lower_case: bool = True,
        index_col: str | Sequence[str] | None = None,
        columns: Sequence[str] | None = None,
        enforce_ordering: bool = True,
    ) -> mpd.DataFrame:
        """
        Read a whole table as a Modin dataframe.

        Thin alias over :meth:`query_to_dataframe` exploiting that
        ``modin.pandas.read_snowflake`` accepts a bare table name as well
        as a query, so a table can be loaded without ``SELECT *``
        boilerplate.

        Parameters
        ----------
        table
            Name of the table to read.
        lower_case
            Whether to lower-case the returned column names.
        index_col
            Column name or names to use as the dataframe index; ``None``
            leaves the default integer index in place.
        columns
            Subset of column names to include in the result; ``None``
            returns all columns.
        enforce_ordering
            Whether to enforce the result ordering from Snowflake.

        Returns
        -------
            The table's contents as a Modin dataframe.

        See Also
        --------
        SnowparkExtendedSession.query_to_dataframe : Underlying implementation.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> session = SnowflakeConfig.from_env().to_snowpark_session()  # doctest: +SKIP
        >>> df = session.table_to_dataframe("MY_DB.MY_SCHEMA.MY_TABLE")  # doctest: +SKIP
        """
        return self.query_to_dataframe(
            table,
            lower_case=lower_case,
            index_col=index_col,
            columns=columns,
            enforce_ordering=enforce_ordering,
        )

    def to_reader(
        self,
        /,
        *,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
        execute_kwargs: Mapping[str, Any] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> QueryReader:
        """
        Build a backend-aware query reader bound to this session.

        Delegates to the session's underlying connection via
        :meth:`to_connection`, returning the reader built by
        :meth:`SnowflakeExtendedConnection.to_reader`. Because the wrapped
        connection shares this session's live connection, reads honour any
        role, warehouse, database or schema set inside a :meth:`using`
        block, and the reader plugs straight into
        :func:`mayutils.data.read.read_query`. Results come back as pandas
        or polars frames — the flavours the shared reader supports — so
        reach for :meth:`query_to_dataframe` when a Modin frame is wanted.

        Parameters
        ----------
        lower_case
            Whether to lower-case the column names of returned frames.
        read_kwargs
            Extra keyword arguments forwarded to the underlying fetches.
        execute_kwargs
            Extra keyword arguments forwarded to the cursor's ``execute``.
        **kwargs
            Backend-specific options such as ``schema_overrides`` for Polars.

        Returns
        -------
            A reader executing queries on this session's connection.

        See Also
        --------
        SnowflakeExtendedConnection.to_reader : Underlying reader factory delegated to.
        SnowparkExtendedSession.to_streamer : Streaming counterpart of this method.
        mayutils.data.read.read_query : Cached query execution consuming the reader.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> reader = SnowflakeConfig.from_env().to_snowpark_session().to_reader()  # doctest: +SKIP
        >>> df = reader("SELECT 1")  # doctest: +SKIP
        """
        return self.to_connection().to_reader(
            lower_case=lower_case,
            read_kwargs=read_kwargs,
            execute_kwargs=execute_kwargs,
            **kwargs,
        )

    def to_streamer(
        self,
        /,
        *,
        lower_case: bool = True,
        read_kwargs: Mapping[str, Any] | None = None,
        execute_kwargs: Mapping[str, Any] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> QueryStreamer:
        """
        Build a backend-aware query streamer bound to this session.

        Streaming sibling of :meth:`to_reader`: delegates to the session's
        underlying connection via :meth:`to_connection` and returns the
        streamer built by :meth:`SnowflakeExtendedConnection.to_streamer`.
        Because the wrapped connection shares this session's live
        connection, streamed reads honour any role, warehouse, database or
        schema set inside a :meth:`using` block, and the streamer feeds
        incremental consumers such as
        :class:`mayutils.data.live.StreamingQuery`. Batches come back as
        pandas or polars frames — the flavours the shared streamer
        supports — rather than Modin.

        Parameters
        ----------
        lower_case
            Whether to lower-case the column names of streamed frames.
        read_kwargs
            Extra keyword arguments forwarded to the underlying fetches.
        execute_kwargs
            Extra keyword arguments forwarded to the cursor's ``execute``.
        **kwargs
            Backend-specific options such as ``schema_overrides`` for Polars.

        Returns
        -------
            A streamer yielding dataframe batches for a query.

        See Also
        --------
        SnowflakeExtendedConnection.to_streamer : Underlying streamer factory delegated to.
        SnowparkExtendedSession.to_reader : Eager counterpart of this method.
        mayutils.data.live.StreamingQuery : Incremental consumer of the streamer.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> streamer = SnowflakeConfig.from_env().to_snowpark_session().to_streamer()  # doctest: +SKIP
        >>> for df in streamer("SELECT 1"):  # doctest: +SKIP
        ...     print(df.shape)
        """
        return self.to_connection().to_streamer(
            lower_case=lower_case,
            read_kwargs=read_kwargs,
            execute_kwargs=execute_kwargs,
            **kwargs,
        )

    def read_concurrent_queries(
        self,
        queries: Sequence[Callable[[SnowparkExtendedSession], mpd.DataFrame]],
    ) -> tuple[mpd.DataFrame, ...]:
        """
        Run several dataframe-producing reads concurrently.

        Submits each callable to a thread pool with this session as its
        argument and gathers the results in input order. Because Modin
        reads mostly wait on Snowflake, the threads overlap the queries'
        server-side execution; any exception raised by a callable
        propagates when its result is collected.

        Parameters
        ----------
        queries
            Callables taking this session and returning a Modin dataframe.

        Returns
        -------
            The resulting dataframes, in the same order as the callables.

        See Also
        --------
        SnowparkExtendedSession.query_to_dataframe : Typical body of each callable.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> session = SnowflakeConfig.from_env().to_snowpark_session()  # doctest: +SKIP
        >>> one, two = session.read_concurrent_queries(  # doctest: +SKIP
        ...     [
        ...         lambda session: session.query_to_dataframe("SELECT 1 AS one"),
        ...         lambda session: session.query_to_dataframe("SELECT 2 AS two"),
        ...     ],
        ... )
        """
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
        """
        Temporarily switch the session context within a block.

        For each of role, warehouse, database and schema that is requested,
        records the current value, switches to the requested one and yields
        the session itself; on exit every recorded value is restored, even
        if the block raises. Dimensions left as ``None`` are not touched,
        so the context narrows only what the caller asks for.

        Parameters
        ----------
        role
            Role to assume inside the block; ``None`` leaves it unchanged.
        warehouse
            Warehouse to use inside the block; ``None`` leaves it unchanged.
        database
            Database to use inside the block; ``None`` leaves it unchanged.
        schema
            Schema to use inside the block; ``None`` leaves it unchanged.

        Yields
        ------
            This session, with the requested context applied.

        See Also
        --------
        SnowflakeConfig.update : Persistent counterpart on the configuration model.

        Examples
        --------
        >>> from mayutils.interfaces.data.snowflake import SnowflakeConfig
        >>> session = SnowflakeConfig.from_env().to_snowpark_session()  # doctest: +SKIP
        >>> with session.using(warehouse="ANALYTICS_WH") as scoped:  # doctest: +SKIP
        ...     df = scoped.query_to_dataframe("SELECT 1 AS one")
        """
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
