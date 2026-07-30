"""
Provide an in-memory cache backend with TTL and LRU eviction.

:class:`MemoryStore` wraps an :class:`~collections.OrderedDict` with
lazy TTL eviction and bounded LRU. Persistence is explicit via
:meth:`MemoryStore.save` and :meth:`MemoryStore.load`.

See Also
--------
mayutils.environment.memoisation.types : Shared :data:`MISSING`
    sentinel and :class:`CacheStore` protocol.
mayutils.environment.memoisation.files : File-backed cache backend.
"""

from __future__ import annotations

import pickle
from collections import OrderedDict
from functools import _CacheInfo as CacheInfo  # pyright: ignore[reportPrivateUsage]
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mayutils.environment.memoisation.types import MISSING, Missing
from mayutils.environment.memoisation.utilities import expiry, is_expired

if TYPE_CHECKING:
    from mayutils.objects.datetime import DateTime, Duration


class MemoryStore[CacheObjectType]:
    """
    In-memory cache with TTL eviction and LRU bounding.

    Wraps an :class:`~collections.OrderedDict` with lazy TTL checks
    on reads and LRU eviction on writes.

    Parameters
    ----------
    ttl
        Lifetime of each entry. ``None`` disables expiry.
    maxsize
        Upper bound on live entries. ``None`` disables the bound.

    See Also
    --------
    mayutils.environment.memoisation.types.CacheStore : Protocol this
        class satisfies.
    mayutils.environment.memoisation.files.FileStore : File-backed
        alternative.

    Examples
    --------
    >>> from mayutils.environment.memoisation.memory import MemoryStore
    >>> from mayutils.environment.memoisation.types import MISSING
    >>> store = MemoryStore()
    >>> store.get("k") is MISSING
    True
    >>> store.put("k", value=42)
    >>> store.get("k")
    42
    """

    def __init__(
        self,
        *,
        ttl: Duration | None = None,
        maxsize: int | None = None,
    ) -> None:
        """
        Initialise the store with optional TTL and size bound.

        Creates an empty :class:`~collections.OrderedDict` and zeroes
        the hit/miss counters.

        Parameters
        ----------
        ttl
            Lifetime of each entry. ``None`` disables expiry.
        maxsize
            Upper bound on live entries. ``None`` disables the bound.

        See Also
        --------
        load : Construct a store from a persisted pickle file.

        Examples
        --------
        >>> from mayutils.environment.memoisation.memory import MemoryStore
        >>> store = MemoryStore(maxsize=100)
        >>> store.cache_info().maxsize
        100
        """
        self.ttl = ttl
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0
        self.store: OrderedDict[str, tuple[DateTime | None, CacheObjectType]] = OrderedDict()

    @classmethod
    def load(
        cls,
        path: Path | str,
        /,
        *,
        ttl: Duration | None = None,
        maxsize: int | None = None,
    ) -> MemoryStore[CacheObjectType]:
        """
        Load a store from a ``.pkl`` file.

        Deserialises a pickle file into a new :class:`MemoryStore`
        pre-populated with the persisted entries.

        Parameters
        ----------
        path
            Pickle file to read. Must have ``.pkl`` suffix.
        ttl
            TTL for the loaded store.
        maxsize
            LRU bound for the loaded store.

        Returns
        -------
            A new store pre-populated from the file.

        Raises
        ------
        ValueError
            When *path* does not have a ``.pkl`` suffix.

        See Also
        --------
        save : Persist the current store to a pickle file.

        Examples
        --------
        >>> from mayutils.environment.memoisation.memory import MemoryStore
        >>> store = MemoryStore()
        >>> store.put("k", value=99)
        >>> store.save("/tmp/_test_memo.pkl")
        >>> loaded = MemoryStore.load("/tmp/_test_memo.pkl")
        >>> loaded.get("k")
        99
        """
        path = Path(path)
        if path.suffix != ".pkl":
            msg = f"MemoryStore can only load .pkl files, got '{path.suffix}'"
            raise ValueError(msg)

        instance = cls(ttl=ttl, maxsize=maxsize)
        if path.is_file():
            with path.open(mode="rb") as fh:
                instance.store = pickle.load(file=fh)  # noqa: S301

        return instance

    def save(
        self,
        path: Path | str,
        /,
    ) -> None:
        """
        Persist the store to a ``.pkl`` file.

        Writes the internal :class:`~collections.OrderedDict` to disk
        so it can be reloaded with :meth:`load`.

        Parameters
        ----------
        path
            Destination file. Must have ``.pkl`` suffix.

        Raises
        ------
        ValueError
            When *path* does not have a ``.pkl`` suffix.

        See Also
        --------
        load : Restore a store from a pickle file.

        Examples
        --------
        >>> from mayutils.environment.memoisation.memory import MemoryStore
        >>> store = MemoryStore()
        >>> store.put("k", value=1)
        >>> store.save("/tmp/_test_memo_save.pkl")
        """
        resolved = Path(path)
        if resolved.suffix != ".pkl":
            msg = f"MemoryStore can only save to .pkl files, got '{resolved.suffix}'"
            raise ValueError(msg)

        resolved.parent.mkdir(parents=True, exist_ok=True)
        with resolved.open(mode="wb") as fh:
            pickle.dump(obj=self.store, file=fh)

    def get(
        self,
        key: str,
        /,
    ) -> CacheObjectType | Missing:
        """
        Look up *key*, returning :data:`MISSING` on a miss.

        Expired entries are lazily evicted on access and count as
        misses.

        Parameters
        ----------
        key
            Cache key (typically a hash digest).

        Returns
        -------
            The cached value, or :data:`MISSING` if the key is absent
            or expired.

        See Also
        --------
        put : Store a value under a key.

        Examples
        --------
        >>> from mayutils.environment.memoisation.memory import MemoryStore
        >>> from mayutils.environment.memoisation.types import MISSING
        >>> store = MemoryStore()
        >>> store.get("absent") is MISSING
        True
        """
        entry = self.store.get(key)
        if entry is None:
            self.misses += 1
            return MISSING

        expires_at, value = entry
        if is_expired(expires_at):
            del self.store[key]
            self.misses += 1
            return MISSING

        self.store.move_to_end(key=key)
        self.hits += 1
        return value

    def put(
        self,
        key: str,
        /,
        *,
        value: CacheObjectType,
    ) -> None:
        """
        Store *value* under *key*, evicting LRU entries if needed.

        When ``maxsize`` is set, the oldest entries are removed until
        the store fits within the bound.

        Parameters
        ----------
        key
            Cache key.
        value
            Value to cache.

        See Also
        --------
        get : Retrieve a cached value.
        delete : Remove a single entry.

        Examples
        --------
        >>> from mayutils.environment.memoisation.memory import MemoryStore
        >>> store = MemoryStore(maxsize=2)
        >>> store.put("a", value=1)
        >>> store.put("b", value=2)
        >>> store.put("c", value=3)
        >>> store.cache_info().currsize
        2
        """
        self.store[key] = (expiry(self.ttl), value)
        if self.maxsize is not None:
            while len(self.store) > self.maxsize:
                self.store.popitem(last=False)

    def delete(
        self,
        key: str,
        /,
    ) -> bool:
        """
        Remove *key* if present.

        Returns ``False`` without error when the key is not in the
        store.

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
        >>> store.put("k", value=1)
        >>> store.delete("k")
        True
        >>> store.delete("k")
        False
        """
        if key in self.store:
            del self.store[key]
            return True

        return False

    def clear(
        self,
    ) -> None:
        """
        Remove all entries and reset counters.

        After clearing, ``hits`` and ``misses`` are both zero and
        ``currsize`` is zero.

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
        self.store.clear()
        self.hits = 0
        self.misses = 0

    def cache_info(
        self,
    ) -> CacheInfo:
        """
        Return ``(hits, misses, maxsize, currsize)``.

        Mirrors the interface of :func:`functools.lru_cache` for
        compatibility.

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
        return CacheInfo(
            hits=self.hits,
            misses=self.misses,
            maxsize=self.maxsize,
            currsize=len(self.store),
        )


SHARED_STORES: dict[str, MemoryStore[Any]] = {}


def get_shared_store(
    namespace: str,
    /,
    *,
    ttl: Duration | None = None,
    maxsize: int | None = None,
) -> MemoryStore[Any]:
    """
    Return the process-global :class:`MemoryStore` for *namespace*.

    Unlike a bare :class:`MemoryStore` (a fresh per-instance
    :class:`~collections.OrderedDict`), stores handed out here are shared
    across callers by *namespace*, so independently constructed decorators
    that resolve to the same namespace memoise against one another. The
    first request for a namespace creates the store (with the given ``ttl``
    and ``maxsize``); later requests return that same instance and ignore
    their ``ttl``/``maxsize`` arguments.

    Parameters
    ----------
    namespace
        Stable identifier for the logical cache. Callers that should share
        entries must pass the same string (e.g. a callable's
        module-qualified ``__qualname__``).
    ttl
        Lifetime of each entry, applied only when the store is first created.
    maxsize
        LRU bound, applied only when the store is first created.

    Returns
    -------
        The shared store registered under ``namespace``.

    See Also
    --------
    clear_shared_stores : Drop every shared store.
    MemoryStore : The per-instance backend returned here.

    Examples
    --------
    >>> from mayutils.environment.memoisation.memory import (
    ...     clear_shared_stores,
    ...     get_shared_store,
    ... )
    >>> clear_shared_stores()
    >>> get_shared_store("ns") is get_shared_store("ns")
    True
    >>> get_shared_store("other") is get_shared_store("ns")
    False
    """
    store: MemoryStore[Any] | None = SHARED_STORES.get(namespace)
    if store is None:
        store = MemoryStore[Any](ttl=ttl, maxsize=maxsize)
        SHARED_STORES[namespace] = store

    return store


def clear_shared_stores() -> None:
    """
    Drop every process-global shared in-memory store.

    Empties :data:`SHARED_STORES` so subsequent :func:`get_shared_store`
    calls rebuild fresh stores. Used by :func:`~mayutils.environment.memoisation.clearing.clear_cache`
    and by tests to reset shared state between cases.

    See Also
    --------
    get_shared_store : Accessor that populates the registry.

    Examples
    --------
    >>> from mayutils.environment.memoisation.memory import (
    ...     SHARED_STORES,
    ...     clear_shared_stores,
    ...     get_shared_store,
    ... )
    >>> _ = get_shared_store("ns")
    >>> bool(SHARED_STORES)
    True
    >>> clear_shared_stores()
    >>> bool(SHARED_STORES)
    False
    """
    SHARED_STORES.clear()


__all__ = [
    "SHARED_STORES",
    "MemoryStore",
    "clear_shared_stores",
    "get_shared_store",
]
