import json
from functools import lru_cache
import os
from pathlib import Path
from typing import Literal
from hashlib import md5

import pandas as pd
from pandas import DataFrame

from mayutils.environment.filesystem import (
    get_root,
    get_module_root,
    read_file,
)

MODULE_ROOT = get_module_root()

CACHE_FOLDER = Path(__file__).parent / "cache"


def get_queries_folders() -> tuple[Path, ...]:
    ROOT = get_root()
    return (
        ROOT / "queries",
        *[
            ROOT / "src" / module / "data" / "queries"
            for module in os.listdir(path=ROOT / "src")
        ],
        Path(__file__).parent / "queries",
    )


QUERIES_FOLDERS = get_queries_folders()


def get_query(
    query_name: str | None,
    queries_folders: tuple[Path, ...],
) -> str | None:
    for queries_folder in queries_folders:
        try:
            return read_file(queries_folder / f"{query_name}.sql")
        except ValueError:
            continue

    raise ValueError(
        f"No such query {query_name} found in the query folders {', '.join(list(map(str, queries_folders)))}"
    )


def set_column_types(
    df: DataFrame,
    numeric_columns: tuple[str, ...],
) -> DataFrame:
    if len(numeric_columns) > 0:
        try:
            df[list(numeric_columns)] = df[list(numeric_columns)].apply(
                pd.to_numeric,
            )
        except (
            KeyError,
            ValueError,
            TypeError,
        ):
            raise TypeError("Error parsing numeric values")

    return df


def read_query(
    query_string: str,
    reader=None,
    backend: Literal["snowflake"] = "snowflake",
) -> DataFrame:
    if backend == "snowflake":
        if reader is None:
            raise ValueError("No reader provided")

        df = reader.read_to_dataframe(query_string=query_string)
    # elif ...:
    #     ...
    #     df.columns = df.columns.str.lower()
    else:
        raise NotImplementedError(f"Backend {backend} not implemented")

    return df


def generate_file_name(
    *args,
    **kwargs,
) -> str:
    data = json.dumps(
        obj={
            "args": args,
            "kwargs": kwargs,
        },
        sort_keys=True,
    )
    hash_str = md5(string=data.encode()).hexdigest()

    return f"{'-'.join(kwargs.pop('query_name', '').split('/'))}_data_{hash_str}"


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

    cache_name = generate_file_name(
        query_name=query_name,
        date_columns=date_columns,
        time_columns=time_columns,
        numeric_columns=numeric_columns,
        **format_kwargs,
    )
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
            # index_col=0,
            # parse_dates=[*date_columns, *time_columns],
        )

    query_data = set_column_types(
        df=query_data,
        numeric_columns=tuple(),
    )

    return query_data


@lru_cache
def _get_query_data(
    query_name: str,
    queries_folders: tuple[Path],
    reader=None,
    backend: Literal["snowflake"] = "snowflake",
    **format_kwargs,
) -> DataFrame:
    query_string = get_query(
        query_name=query_name,
        queries_folders=queries_folders,
    )
    if query_string is None:
        raise KeyError(f"File {query_name}.sql not found")

    query_string = query_string.format(
        **format_kwargs,
    )

    query_data = read_query(
        query_string=query_string,
        reader=reader,
        backend=backend,
    )

    return query_data
