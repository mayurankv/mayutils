from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import pydantic

from mayutils.core.extras import may_require_extras
from mayutils.data.read import QueryReader, QueryStreamer
from mayutils.environment.logging import Logger
from mayutils.interfaces.data.snowflake import SnowflakeConfig

with may_require_extras():
    from snowflake.connector.errors import Error as SnowflakeError


logger = Logger.spawn()


def get_env_reader(
    *,
    env_file: Path | str | None | Literal[False] = ".env",
    platform: Literal["snowflake"] | None = None,
    connection_arguments: Mapping[str, Any] | None = None,
    lower_case: bool = True,
    read_kwargs: Mapping[str, Any] | None = None,
    execute_kwargs: Mapping[str, Any] | None = None,
) -> QueryReader:
    if platform is None or platform == "snowflake":
        try:
            connection = SnowflakeConfig.from_env(
                env_file=env_file,
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
    if platform is None or platform == "snowflake":
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
