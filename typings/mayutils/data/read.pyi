import polars as pl
from functools import _lru_cache_wrapper as LRUCacheWrapper
from mayutils.data import CACHE_FOLDER as CACHE_FOLDER
from mayutils.data.queries import (
    QUERIES_FOLDERS as QUERIES_FOLDERS,
    get_formatted_query as get_formatted_query,
)
from mayutils.environment.filesystem import encode_path as encode_path
from mayutils.environment.memoisation import DataframeBackends as DataframeBackends
from mayutils.objects.dataframes import (
    DataFrames as DataFrames,
    read_parquet as read_parquet,
    to_parquet as to_parquet,
)
from mayutils.objects.hashing import hash_inputs as hash_inputs
from pandas import DataFrame
from pathlib import Path
from typing import Literal, overload

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
