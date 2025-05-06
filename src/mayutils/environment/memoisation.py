from functools import update_wrapper, wraps, lru_cache
from functools import _CacheInfo as CacheInfo
from hashlib import sha256
import os
from pathlib import Path
import pickle
from typing import Any, Callable, Optional
from collections import OrderedDict


from mayutils.objects.decorators import flexwrap


# @flexwrap
class cache(object):
    """
    Needs to be used with `cache: bool = True,` at the bottom of the kwargs to prevent type errors
    """

    def __init__(
        self,
        func: Callable,
        *,
        path: Optional[Path | str] = None,
        maxsize: Optional[int] = None,
        typed: bool = False,
    ) -> None:
        self.func = func
        self.path = path
        self.maxsize = maxsize
        self.typed = typed
        self.cached_func = lru_cache(
            maxsize=self.maxsize,
            typed=self.typed,
        )(self.func)
        self.hits = 0
        self.misses = 0

        if self.path is not None:
            if os.path.exists(path=self.path):
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
        # @wraps(wrapped=func)
        # # def wrapper(
        #     *args,
        #     cache: bool = True,
        #     **kwargs,
        # ) -> Any:
        if cache:
            if self.path is not None:
                key = sha256(
                    string=(self.func.__name__ + str(args) + str(kwargs)).encode(),
                ).hexdigest()

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
def _cache(
    func: Callable,
    *,
    path: Optional[Path | str] = None,
    maxsize: Optional[int] = None,
    typed: bool = False,
):
    """
    Needs to be used with `cache: bool = True,` at the bottom of the kwargs to prevent type errors
    """
    cached_func = lru_cache(
        maxsize=maxsize,
        typed=typed,
    )(func)

    if path is not None:
        if os.path.exists(path=path):
            with open(
                file=path,
                mode="rb",
            ) as file:
                persistent_cache = pickle.load(file=file)
        else:
            persistent_cache = OrderedDict()

    @wraps(wrapped=func)
    def wrapper(
        *args,
        cache: bool = True,
        **kwargs,
    ) -> Any:
        if cache:
            if path is not None:
                key = sha256(
                    string=(func.__name__ + str(args) + str(kwargs)).encode(),
                ).hexdigest()

                if key in persistent_cache:
                    persistent_cache.move_to_end(key)
                    return persistent_cache[key]

                result = func(
                    *args,
                    **kwargs,
                )

                if maxsize is not None and len(persistent_cache) >= maxsize:
                    persistent_cache.popitem(last=False)

                persistent_cache[key] = result

                with open(file=path, mode="wb") as file:
                    pickle.dump(obj=persistent_cache, file=file)

            else:
                return cached_func(
                    *args,
                    **kwargs,
                )

        else:
            return func(
                *args,
                **kwargs,
            )

    wrapper.cache_clear = cached_func.cache_clear  # type: ignore
    wrapper.cache_info = cached_func.cache_info  # type: ignore
    wrapper.cache_parameters = cached_func.cache_parameters  # type: ignore

    return wrapper

    # wrapper.cache_clear = cached_func.cache_clear  # type: ignore
    # wrapper.cache_info = cached_func.cache_info  # type: ignore

    # return wrapper
