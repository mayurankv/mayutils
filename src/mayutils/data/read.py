from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Literal, overload


import polars as pl
from pandas import DataFrame

from mayutils.data import CACHE_FOLDER
from mayutils.data.queries import QUERIES_FOLDERS, get_formatted_query
from mayutils.environment.filesystem import encode_path
from mayutils.environment.memoisation import DataframeBackends
from mayutils.objects.hashing import hash_inputs
from mayutils.objects.dataframes import read_parquet, to_parquet, DataFrames

if TYPE_CHECKING:
    from functools import _lru_cache_wrapper as LRUCacheWrapper


@overload
def get_query_data(
    query_name: Path | str,
    read_query: LRUCacheWrapper[DataFrames],
    dataframe_backend: Literal["pandas"],
    queries_folders: tuple[Path, ...],
    cache: bool | Literal["persistent"],
    **format_kwargs,
) -> DataFrame: ...


@overload
def get_query_data(
    query_name: Path | str,
    read_query: LRUCacheWrapper[DataFrames],
    dataframe_backend: Literal["polars"],
    queries_folders: tuple[Path, ...],
    cache: bool | Literal["persistent"],
    **format_kwargs,
) -> pl.DataFrame: ...


@overload
def get_query_data(
    query_name: Path | str,
    read_query: LRUCacheWrapper[DataFrames],
    dataframe_backend: DataframeBackends,
    queries_folders: tuple[Path, ...],
    cache: bool | Literal["persistent"],
    **format_kwargs,
) -> DataFrames: ...


def get_query_data(
    query_name: Path | str,
    read_query: LRUCacheWrapper[DataFrames],
    dataframe_backend: DataframeBackends = "pandas",
    queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
    cache: bool | Literal["persistent"] = True,
    **format_kwargs,
) -> DataFrames:
    if (
        cache is False
        and hasattr(read_query, "cache_clear")
        and callable(getattr(read_query, "cache_clear"))
    ):
        read_query.cache_clear()

    cache_name = f"{encode_path(path=query_name)}_data_{
        hash_inputs(
            query_name=query_name,
            **format_kwargs,
        )
    }"
    cache_file = CACHE_FOLDER / f"{cache_name}.parquet"

    if cache != "persistent" or not cache_file.is_file():
        query_string = get_formatted_query(
            query_name=query_name,
            queries_folders=queries_folders,
            **format_kwargs,
        )

        query_data = read_query(
            query_string=query_string,
            dataframe_backend=dataframe_backend,
        )

        if cache == "persistent":
            kwargs = {
                "pandas": dict(index=True),
                "polars": dict(),
            }

            to_parquet(
                df=query_data,
                path=cache_file,
                dataframe_backend=dataframe_backend,
                **kwargs.get(dataframe_backend, dict()),
            )

    else:
        query_data = read_parquet(
            path=cache_file,
            dataframe_backend=dataframe_backend,
        )

    return query_data
