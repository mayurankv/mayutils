from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd
from pandas import DataFrame

from mayutils.data import CACHE_FOLDER
from mayutils.data.queries import QUERIES_FOLDERS
from mayutils.environment.filesystem import encode_path
from mayutils.objects.hashing import hash_inputs


def get_query_data(
    query_name: str,
    queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
    date_columns: tuple[str, ...] = tuple(),
    time_columns: tuple[str, ...] = tuple(),
    numeric_columns: tuple[str, ...] = tuple(),
    cache: bool | Literal["persistent"] = True,
    reader=None,
    backend: Literal["snowflake"] = "snowflake",
    **format_kwargs,
) -> DataFrame:
    if cache is False:
        _get_query_data.cache_clear()

    cache_name = f"{encode_path(path=query_name)}_data_{
        hash_inputs(
            query_name=query_name,
            date_columns=date_columns,
            time_columns=time_columns,
            numeric_columns=numeric_columns,
            **format_kwargs,
        )
    }"
    cache_file = CACHE_FOLDER / f"{cache_name}.parquet"
    if cache != "persistent" or not cache_file.is_file():
        query_data = _get_query_data(
            query_name=query_name,
            queries_folders=queries_folders,
            reader=reader,
            backend=backend,
            **format_kwargs,
        )

        if cache == "persistent":
            query_data.to_parquet(
                path=cache_file,
                index=True,
            )
    else:
        query_data = pd.read_parquet(
            path=cache_file,
        )

    return query_data


@lru_cache
def _get_query_data() -> DataFrame:
    return DataFrame()
