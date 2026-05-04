"""
Provide shared types for the memoisation package.

:data:`MISSING` is the sentinel distinguishing a cache miss from a
cached ``None``. :class:`CacheStore` is the protocol shared by
:class:`~mayutils.environment.memoisation.memory.MemoryStore` and
:class:`~mayutils.environment.memoisation.files.FileStore`.

See Also
--------
mayutils.environment.memoisation.memory : In-memory backend.
mayutils.environment.memoisation.files : File-backed backend.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from mayutils.core.extras import may_require_extras
from mayutils.objects.dataframes.backends import DataFrames

with may_require_extras():
    from numpy.typing import ArrayLike


if TYPE_CHECKING:
    from functools import _CacheInfo as CacheInfo  # pyright: ignore[reportPrivateUsage]

type CacheObjects = DataFrames | ArrayLike | Mapping[str, ArrayLike] | object


class Missing(enum.Enum):
    """
    Sentinel distinguishing a cache miss from a cached ``None``.

    A single-member enum used by :class:`CacheStore` implementations
    to signal that a key was not found in the cache.

    See Also
    --------
    CacheStore : Protocol that returns :data:`MISSING` on a miss.

    Examples
    --------
    >>> from mayutils.environment.memoisation.types import MISSING, Missing
    >>> MISSING is Missing.MISSING
    True
    """

    MISSING = enum.auto()


MISSING = Missing.MISSING
"""Sentinel returned by :meth:`CacheStore.get` on a cache miss."""


@runtime_checkable
class CacheStore[CacheObjectType](Protocol):
    """
    Protocol shared by :class:`MemoryStore` and :class:`FileStore`.

    Any object implementing ``get``, ``put``, ``delete``, ``clear``,
    and ``cache_info`` satisfies this protocol.

    See Also
    --------
    mayutils.environment.memoisation.memory.MemoryStore : In-memory
        implementation.
    mayutils.environment.memoisation.files.FileStore : File-backed
        implementation.

    Examples
    --------
    >>> from mayutils.environment.memoisation.types import CacheStore
    >>> from mayutils.environment.memoisation.memory import MemoryStore
    >>> isinstance(MemoryStore(), CacheStore)
    True
    """

    hits: int
    misses: int

    def get(
        self,
        key: str,
        /,
    ) -> CacheObjectType | Missing:
        """
        Return the cached value for *key*, or :data:`MISSING` on a miss.

        Implementations should increment ``hits`` or ``misses`` as
        appropriate.

        Parameters
        ----------
        key
            Cache key to look up.

        Returns
        -------
            The cached value, or :data:`MISSING` if absent or expired.

        See Also
        --------
        put : Store a value under a key.

        Examples
        --------
        >>> from mayutils.environment.memoisation.memory import MemoryStore
        >>> from mayutils.environment.memoisation.types import MISSING
        >>> store = MemoryStore()
        >>> store.get("k") is MISSING
        True
        """
        ...

    def put(
        self,
        key: str,
        /,
        *,
        value: CacheObjectType,
    ) -> None:
        """
        Store *value* under *key*.

        Existing entries for the same key are silently overwritten.

        Parameters
        ----------
        key
            Cache key.
        value
            Object to cache.

        See Also
        --------
        get : Retrieve a cached value.

        Examples
        --------
        >>> from mayutils.environment.memoisation.memory import MemoryStore
        >>> store = MemoryStore()
        >>> store.put("k", value=42)
        >>> store.get("k")
        42
        """
        ...

    def delete(
        self,
        key: str,
        /,
    ) -> bool:
        """
        Remove the entry for *key* and return whether it existed.

        Returns ``False`` without error when the key is not present.

        Parameters
        ----------
        key
            Cache key to remove.

        Returns
        -------
            ``True`` if an entry was removed, ``False`` otherwise.

        See Also
        --------
        clear : Remove all entries at once.

        Examples
        --------
        >>> from mayutils.environment.memoisation.memory import MemoryStore
        >>> store = MemoryStore()
        >>> store.delete("absent")
        False
        """
        ...

    def clear(
        self,
    ) -> None:
        """
        Remove all entries and reset counters.

        After clearing, ``hits`` and ``misses`` are both zero.

        See Also
        --------
        delete : Remove a single entry by key.

        Examples
        --------
        >>> from mayutils.environment.memoisation.memory import MemoryStore
        >>> store = MemoryStore()
        >>> store.put("k", value=1)
        >>> store.clear()
        >>> store.cache_info().currsize
        0
        """
        ...

    def cache_info(
        self,
    ) -> CacheInfo:
        """
        Return a :class:`CacheInfo` named tuple of hit/miss statistics.

        The tuple contains ``(hits, misses, maxsize, currsize)``.

        Returns
        -------
            Named tuple with cache statistics.

        See Also
        --------
        clear : Reset the counters reported here.

        Examples
        --------
        >>> from mayutils.environment.memoisation.memory import MemoryStore
        >>> store = MemoryStore()
        >>> info = store.cache_info()
        >>> info.hits
        0
        """
        ...


__all__ = [
    "MISSING",
    "CacheStore",
]
