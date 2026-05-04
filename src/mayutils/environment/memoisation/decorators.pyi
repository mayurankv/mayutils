# pyright: reportUnusedImport=false
from collections.abc import Callable
from functools import _CacheInfo as CacheInfo  # pyright: ignore[reportPrivateUsage]
from pathlib import Path
from typing import Any, overload

from mayutils.environment.memoisation.files import FileStore
from mayutils.environment.memoisation.memory import MemoryStore
from mayutils.environment.memoisation.types import CacheStore
from mayutils.objects.dataframes.backends import Backend
from mayutils.objects.datetime import Duration

class lru_cache:
    func: Callable[..., object]
    maxsize: int | None
    typed: bool

    @overload
    def __new__(
        cls,
        func: Callable[..., object],
        /,
    ) -> lru_cache: ...
    @overload
    def __new__(
        cls,
        *,
        maxsize: int | None = 128,
        typed: bool = False,
    ) -> Callable[[Callable[..., object]], lru_cache]: ...
    def cache_info(self) -> CacheInfo: ...
    def cache_clear(self) -> None: ...
    def bypass_cache(self, *args: object, **kwargs: object) -> object: ...
    def __call__(self, *args: object, **kwargs: object) -> object: ...

class cache[CacheObjectType]:
    func: Callable[..., CacheObjectType]
    store: CacheStore[CacheObjectType]

    @overload
    def __new__(
        cls,
        func: Callable[..., CacheObjectType],
        /,
    ) -> cache[CacheObjectType]: ...
    @overload
    def __new__(
        cls,
        *,
        suffix: str | None = None,
        persist: bool = False,
        path: Path | str | None = None,
        cache_folder: Path | str = ...,
        ttl: Duration | None = None,
        maxsize: int | None = None,
        key_prefix: str | None = None,
        backend: Backend[Any] | None = None,
    ) -> Callable[[Callable[..., CacheObjectType]], cache[CacheObjectType]]: ...
    @property
    def persist_path(self) -> Path | None: ...
    @property
    def key_prefix(self) -> str | None: ...
    @key_prefix.setter
    def key_prefix(self, value: str | None) -> None: ...
    def func_key(self, *args: object, **kwargs: object) -> str: ...
    def cache_info(self) -> CacheInfo: ...
    def cache_clear(self) -> None: ...
    def delete_cache(self, *args: object, **kwargs: object) -> bool: ...
    def get_path(self, *args: object, **kwargs: object) -> Path: ...
    def save(self, path: Path | str, /) -> None: ...
    def load_store(self, path: Path | str, /) -> None: ...
    def bypass_cache(self, *args: object, **kwargs: object) -> CacheObjectType: ...
    def refresh(self, *args: object, **kwargs: object) -> CacheObjectType: ...
    def __call__(self, *args: object, **kwargs: object) -> CacheObjectType: ...
