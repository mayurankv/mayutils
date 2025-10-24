from _typeshed import Incomplete
from functools import _CacheInfo as CacheInfo
from mayutils.data import CACHE_FOLDER as CACHE_FOLDER
from mayutils.data.local import DataFile as DataFile
from mayutils.objects.dataframes import DataframeBackends as DataframeBackends
from mayutils.objects.decorators import flexwrap as flexwrap
from mayutils.objects.hashing import hash_inputs as hash_inputs
from pandas import DataFrame
from pathlib import Path
from typing import Any, Callable, Literal, TypeVar

T = TypeVar("T", bound=Callable[..., Any])

class cache:
    """
    Needs to be used with `cache: bool = True,` at the bottom of the kwargs to prevent type errors
    """

    func: Incomplete
    path: Incomplete
    maxsize: Incomplete
    typed: Incomplete
    cached_func: Incomplete
    hits: int
    misses: int
    persistent_cache: Incomplete
    def __init__(
        self,
        func: Callable | None = None,
        *,
        path: Path | str | None = None,
        maxsize: int | None = None,
        typed: bool = False,
    ) -> None: ...
    def cache_info(self) -> CacheInfo: ...
    def cache_clear(self) -> None: ...
    def __call__(self, *args, cache: bool = True, **kwargs) -> Any: ...

class cache_df:
    """
    Needs to be used with `refresh: bool = False,` at the bottom of the kwargs to prevent type errors
    """

    func: Incomplete
    format: Incomplete
    cache_path: Incomplete
    dataframe_backend: Incomplete
    def __init__(
        self,
        func: Callable[..., DataFrame] | None = None,
        *,
        format: Literal["parquet", "csv", "feather", "xlsx"] = "parquet",
        cache_folder: Path | str = ...,
        dataframe_backend: DataframeBackends = "pandas",
    ) -> None: ...
    def get_path(self, *args, refresh: bool = False, **kwargs) -> Path: ...
    def update(self, *args, refresh=None, **kwargs) -> DataFrame: ...
    def delete_cache(self, *args, refresh: bool = False, **kwargs) -> bool: ...
    def __call__(self, *args, refresh: bool = False, **kwargs) -> DataFrame: ...
