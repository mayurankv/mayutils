"""
Build database readers and streamers from environment configuration.

This package is the database-connectivity corner of
:mod:`mayutils.interfaces`: platform adapters live in subpackages —
currently :mod:`mayutils.interfaces.data.snowflake` with its
:class:`~mayutils.interfaces.data.snowflake.SnowflakeConfig` model —
while this module layers environment-driven discovery on top.
:func:`get_env_reader` and :func:`get_env_streamer` walk the supported
platforms, build a configuration from environment variables (loading a
dotenv file first when one is given), open a connection, and hand back
a :class:`~mayutils.data.read.QueryReader` or
:class:`~mayutils.data.read.QueryStreamer` ready to drive
:func:`mayutils.data.read.read_query`. Platforms whose configuration is
incomplete or whose connection fails are logged and skipped, so the
factories only raise once no candidate remains.

See Also
--------
mayutils.interfaces.data.snowflake : Snowflake configuration and connection adapter.
mayutils.data.read.read_query : Cached query execution consuming a reader.
mayutils.data.read.QueryReader : Protocol satisfied by the returned readers.
mayutils.data.read.QueryStreamer : Protocol satisfied by the returned streamers.

Examples
--------
>>> from mayutils.interfaces.data import get_env_reader, get_env_streamer
>>> reader = get_env_reader(platform="snowflake")  # doctest: +SKIP
>>> df = reader("SELECT 1 AS one")  # doctest: +SKIP
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import pydantic

from mayutils.core.extras import may_require_extras
from mayutils.environment.logging import Logger

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from mayutils.data.read import QueryReader, QueryStreamer


logger = Logger.spawn()


def get_env_reader(
    *,
    env_file: Path | str | None | Literal[False] = ".env",
    env_overrides: Mapping[str, Any] | None = None,
    platform: Literal["snowflake"] | None = None,
    connection_arguments: Mapping[str, Any] | None = None,
    lower_case: bool = True,
    read_kwargs: Mapping[str, Any] | None = None,
    execute_kwargs: Mapping[str, Any] | None = None,
) -> QueryReader:
    """
    Build a query reader from connection settings in the environment.

    Walks the supported data platforms — currently only Snowflake — and
    returns the first reader that can be constructed. For Snowflake the
    configuration is read from ``SNOWFLAKE_*`` environment variables via
    :meth:`~mayutils.interfaces.data.snowflake.SnowflakeConfig.from_env`
    (loading ``env_file`` first when given), a connection is opened, and
    the reader produced by its ``to_reader`` method is returned.
    Platforms with incomplete configuration or failing connections are
    logged at info level and skipped rather than raising immediately, so
    the factory only fails once every candidate is exhausted.

    Parameters
    ----------
    env_file
        Dotenv file loaded before reading the environment. ``None``
        auto-discovers a ``.env`` file by walking upwards from the
        current working directory; ``False`` skips loading entirely and
        reads the existing environment.
    env_overrides
        Extra field values, keyed by field name or alias, overriding those
        read from the environment.
    platform
        Restrict the search to a single platform; ``None`` tries every
        supported platform in turn.
    connection_arguments
        Extra keyword arguments merged into the platform connection.
    lower_case
        Whether the reader lower-cases result column names.
    read_kwargs
        Extra keyword arguments forwarded to the platform fetch call.
    execute_kwargs
        Extra keyword arguments forwarded to query execution.

    Returns
    -------
        A reader satisfying :class:`~mayutils.data.read.QueryReader`,
        ready to pass to :func:`mayutils.data.read.read_query`.

    Raises
    ------
    ValueError
        If no reader could be constructed from the environment for the
        requested platform(s).

    See Also
    --------
    get_env_streamer : Streaming counterpart yielding chunked results.
    mayutils.interfaces.data.snowflake.SnowflakeConfig.from_env : Environment-driven configuration.
    mayutils.data.read.read_query : Cached query execution consuming the reader.

    Examples
    --------
    >>> from mayutils.interfaces.data import get_env_reader
    >>> reader = get_env_reader()  # doctest: +SKIP
    >>> df = reader("SELECT 1 AS one")  # doctest: +SKIP
    """
    if platform is None or platform == "snowflake":
        from mayutils.interfaces.data.snowflake import SnowflakeConfig

        with may_require_extras():
            from snowflake.connector.errors import Error as SnowflakeError

        try:
            connection = SnowflakeConfig.from_env(
                env_file=env_file,
                **(env_overrides or {}),
            ).to_connection(
                connection_arguments=connection_arguments,
            )

            return connection.to_reader(
                lower_case=lower_case,
                read_kwargs=read_kwargs,
                execute_kwargs=execute_kwargs,
            )
        except (pydantic.ValidationError, SnowflakeError) as err:
            logger.info(f"Failed to create Snowflake reader from env file {env_file}: {err}")

    msg = "No reader found from env file" if platform is None else f"No reader found for platform {platform}"
    raise ValueError(msg)


def get_env_streamer(
    *,
    env_file: Path | str | None | Literal[False] = ".env",
    platform: Literal["snowflake"] | None = None,
    connection_arguments: Mapping[str, Any] | None = None,
    lower_case: bool = True,
    read_kwargs: Mapping[str, Any] | None = None,
    execute_kwargs: Mapping[str, Any] | None = None,
) -> QueryStreamer:
    """
    Build a query streamer from connection settings in the environment.

    Walks the supported data platforms — currently only Snowflake — and
    returns the first streamer that can be constructed. For Snowflake
    the configuration is read from ``SNOWFLAKE_*`` environment variables
    via
    :meth:`~mayutils.interfaces.data.snowflake.SnowflakeConfig.from_env`
    (loading ``env_file`` first when given), a connection is opened, and
    the streamer produced by its ``to_streamer`` method is returned.
    Platforms with incomplete configuration or failing connections are
    logged at info level and skipped rather than raising immediately, so
    the factory only fails once every candidate is exhausted.

    Parameters
    ----------
    env_file
        Dotenv file loaded before reading the environment. ``None``
        auto-discovers a ``.env`` file by walking upwards from the
        current working directory; ``False`` skips loading entirely and
        reads the existing environment.
    platform
        Restrict the search to a single platform; ``None`` tries every
        supported platform in turn.
    connection_arguments
        Extra keyword arguments merged into the platform connection.
    lower_case
        Whether the streamer lower-cases result column names.
    read_kwargs
        Extra keyword arguments forwarded to the platform fetch call.
    execute_kwargs
        Extra keyword arguments forwarded to query execution.

    Returns
    -------
        A streamer satisfying :class:`~mayutils.data.read.QueryStreamer`
        that yields result chunks as DataFrames.

    Raises
    ------
    ValueError
        If no streamer could be constructed from the environment for the
        requested platform(s).

    See Also
    --------
    get_env_reader : Materialising counterpart returning a single DataFrame.
    mayutils.interfaces.data.snowflake.SnowflakeConfig.from_env : Environment-driven configuration.
    mayutils.data.read.QueryStreamer : Protocol the returned callable satisfies.

    Examples
    --------
    >>> from mayutils.interfaces.data import get_env_streamer
    >>> streamer = get_env_streamer()  # doctest: +SKIP
    >>> for chunk in streamer("SELECT * FROM loans"):  # doctest: +SKIP
    ...     print(chunk.shape)
    """
    if platform is None or platform == "snowflake":
        from mayutils.interfaces.data.snowflake import SnowflakeConfig

        with may_require_extras():
            from snowflake.connector.errors import Error as SnowflakeError

        try:
            connection = SnowflakeConfig.from_env(
                env_file=env_file,
            ).to_connection(
                connection_arguments=connection_arguments,
            )

            return connection.to_streamer(
                lower_case=lower_case,
                read_kwargs=read_kwargs,
                execute_kwargs=execute_kwargs,
            )
        except (pydantic.ValidationError, SnowflakeError) as err:
            logger.info(f"Failed to create Snowflake streamer from env file {env_file}: {err}")

    msg = "No streamer found from env file" if platform is None else f"No streamer found for platform {platform}"
    raise ValueError(msg)
