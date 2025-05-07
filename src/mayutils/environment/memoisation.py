from functools import update_wrapper, lru_cache
from functools import _CacheInfo as CacheInfo
from pathlib import Path
import pickle
from typing import Any, Callable, Literal, Optional, TypeVar
from collections import OrderedDict

from pandas import DataFrame


from mayutils.data import CACHE_FOLDER
from mayutils.data.local import DataFile
from mayutils.objects.decorators import flexwrap
from mayutils.objects.hashing import hash_inputs

T = TypeVar("T", bound=Callable[..., Any])


@flexwrap
class cache(object):
    """
    Needs to be used with `cache: bool = True,` at the bottom of the kwargs to prevent type errors
    """

    def __init__(
        self,
        func: Optional[Callable] = None,
        *,
        path: Optional[Path | str] = None,
        maxsize: Optional[int] = None,
        typed: bool = False,
    ) -> None:
        if func is None:
            raise ValueError("No function provided")
        self.func = func
        self.path = Path(path) if path is not None else None
        self.maxsize = maxsize
        self.typed = typed
        self.cached_func = lru_cache(
            maxsize=self.maxsize,
            typed=self.typed,
        )(self.func)
        self.hits = 0
        self.misses = 0

        if self.path is not None:
            if self.path.exists() and self.path.is_file():
                with open(
                    file=self.path,
                    mode="rb",
                ) as file:
                    self.persistent_cache = pickle.load(file=file)
            else:
                self.persistent_cache = OrderedDict()

        update_wrapper(
            wrapper=self,
            wrapped=func,
        )

    def cache_info(
        self,
    ) -> CacheInfo:
        if self.path is None:
            return self.cached_func.cache_info()
        else:
            return CacheInfo(
                hits=self.hits,
                misses=self.misses,
                maxsize=self.maxsize,
                currsize=len(self.persistent_cache),
            )

    def cache_clear(
        self,
    ) -> None:
        if self.path is None:
            self.persistent_cache = OrderedDict()

            return
        else:
            return self.cached_func.cache_clear()

    def __call__(
        self,
        *args,
        cache: bool = True,
        **kwargs,
    ) -> Any:
        if cache:
            if self.path is not None:
                key = hash_inputs(
                    func=self.func, paramers=dict(args=args, kwargs=kwargs)
                )
                if key in self.persistent_cache:
                    self.persistent_cache.move_to_end(key)
                    self.hits += 1
                    return self.persistent_cache[key]

                result = self.func(
                    *args,
                    **kwargs,
                )

                if (
                    self.maxsize is not None
                    and len(self.persistent_cache) >= self.maxsize
                ):
                    self.persistent_cache.popitem(last=False)

                self.misses += 1
                self.persistent_cache[key] = result

                with open(file=self.path, mode="wb") as file:
                    pickle.dump(obj=self.persistent_cache, file=file)

            else:
                return self.cached_func(
                    *args,
                    **kwargs,
                )

        else:
            return self.func(
                *args,
                **kwargs,
            )


@flexwrap
class cache_df(object):
    """
    Needs to be used with `refresh: bool = False,` at the bottom of the kwargs to prevent type errors
    """

    def __init__(
        self,
        func: Optional[Callable[..., DataFrame]] = None,
        *,
        format: Literal["parquet", "csv", "feather", "xlsx"] = "parquet",
        cache_folder: Path | str = CACHE_FOLDER,
        dataframe_backend: Literal["pandas", "polars"] = "pandas",
    ) -> None:
        if func is None:
            raise ValueError("No function provided")
        self.func = func
        self.format = format
        self.cache_path = Path(cache_folder)

        self.dataframe_backend = dataframe_backend
        if self.dataframe_backend != "pandas":
            raise NotImplementedError("Only pandas dataframes are supported currently")

        return

    def get_path(
        self,
        *args,
        refresh: bool = False,
        **kwargs,
    ) -> Path:
        key = hash_inputs(
            func=self.func.__name__,
            paramers=dict(
                args=args,
                kwargs=kwargs,
            ),
        )

        return self.cache_path / f"{key}.{self.format}"

    def update(
        self,
        *args,
        refresh=None,
        **kwargs,
    ) -> DataFrame:
        if refresh is not None:
            raise KeyError("Keyword refresh incorrectly provided")

        return self.__call__(
            *args,
            refresh=True,
            **kwargs,
        )

    def delete_cache(
        self,
        *args,
        refresh: bool = False,
        **kwargs,
    ) -> bool:
        try:
            file = DataFile(self.get_path(*args, refresh=refresh, **kwargs))
            file.path.unlink()
            return True
        except ValueError:
            return False

    def __call__(
        self,
        *args,
        refresh: bool = False,
        **kwargs,
    ) -> DataFrame:
        file = DataFile(
            path=self.get_path(*args, refresh=refresh, **kwargs),
            validate=False,
        )
        if refresh or not file.exists():
            df = self.func(
                *args,
                **kwargs,
            )

            df.utils.save(path=file.path)

            return df

        return file.to_pandas()
