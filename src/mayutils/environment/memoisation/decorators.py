"""
Provide memoisation decorators with pluggable storage backends.

:class:`cache` is the unified decorator that delegates to
:class:`~mayutils.environment.memoisation.memory.MemoryStore` or
:class:`~mayutils.environment.memoisation.files.FileStore` based on
whether a ``suffix`` is provided. :class:`lru_cache` is kept for
C-accelerated in-memory caching via :func:`functools.lru_cache`.

See Also
--------
mayutils.environment.memoisation.memory : In-memory cache backend.
mayutils.environment.memoisation.files : File-backed cache backend.
"""

from __future__ import annotations

import functools
from functools import _CacheInfo as CacheInfo  # pyright: ignore[reportPrivateUsage]
from functools import _lru_cache_wrapper as LRUCacheWrapper  # pyright: ignore[reportPrivateUsage]  # noqa: N812
from functools import update_wrapper
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from mayutils.data import CACHE_FOLDER
from mayutils.environment.memoisation.files import FileStore
from mayutils.environment.memoisation.memory import MemoryStore, get_shared_store
from mayutils.environment.memoisation.types import Missing
from mayutils.environment.memoisation.utilities import make_cache_key
from mayutils.objects.decorators import flexwrap

if TYPE_CHECKING:
    from collections.abc import Callable

    from mayutils.environment.memoisation import CacheStore
    from mayutils.objects.dataframes.backends import Backend
    from mayutils.objects.datetime import Duration


@flexwrap
class lru_cache:  # noqa: N801
    """
    Decorate a callable with a fast in-process LRU cache.

    Thin flexwrap-wrapped layer over :func:`functools.lru_cache` that
    keeps the hot-path behaviour — argument hashing in C, LRU
    eviction, bounded ``maxsize`` — while adding the mayutils
    decorator conventions. In particular, every call site can pass
    ``cache=False`` as a trailing keyword to bypass the cache for a
    single invocation without having to reach for
    :meth:`cache_clear`; and :meth:`cache_info`/:meth:`cache_clear`
    stay callable from the decorator instance itself. Use this when
    the goal is purely in-memory memoisation with no TTL and no
    persistence, where the C-accelerated path is worth the simpler
    contract. Reach for :class:`cache` when TTL eviction or a
    pickle-backed persistent tier is needed.

    Parameters
    ----------
    func
        The wrapped callable. Supplied automatically by
        :func:`flexwrap` when the decorator is applied; callers do
        not pass it directly.
    maxsize
        Upper bound on the number of retained entries. ``None``
        disables the bound, matching :func:`functools.lru_cache`'s
        ``maxsize=None`` semantics (unbounded cache). Defaults to
        ``128``, matching the stdlib default.
    typed
        When ``True``, arguments that compare equal but differ in
        type are cached under separate keys. Mirrors
        :func:`functools.lru_cache`'s ``typed`` argument exactly.

    Attributes
    ----------
    func
        The wrapped callable.
    maxsize
        Configured bound on live entries.
    typed
        Whether arguments are keyed by type as well as value.

    See Also
    --------
    cache : TTL-aware, optionally-persistent sibling that wraps an
        :class:`~collections.OrderedDict` directly.
    cache_df : DataFrame-specialised sibling that persists results
        through the :class:`~mayutils.interfaces.filetypes.DataFile`
        registry.
    functools.lru_cache : Standard-library primitive this decorator
        delegates to for the hot path.
    functools.cache : Unbounded stdlib analogue (equivalent to
        ``lru_cache(maxsize=None)``).

    Examples
    --------
    >>> from mayutils.environment.memoisation import lru_cache
    >>> @lru_cache
    ... def square(n: int) -> int:
    ...     return n * n
    >>> square(3), square(3)
    (9, 9)
    >>> square.cache_info().hits
    1
    >>> @lru_cache(maxsize=256, typed=True)
    ... def add(a, b):
    ...     return a + b
    >>> add(1, 2)
    3
    >>> add(1, 2, cache=False)  # bypass the cache for this call
    3
    """

    def __init__(
        self,
        func: Callable[..., object],
        /,
        *,
        maxsize: int | None = 128,
        typed: bool = False,
    ) -> None:
        """
        Bind the wrapped callable behind a :func:`functools.lru_cache`.

        Stores the wrapped callable, the caching knobs, and a
        memoised view produced by :func:`functools.lru_cache`. The
        wrapper metadata is then copied from ``func`` so the
        decorated object mirrors the original's ``__name__``,
        ``__doc__`` and ``__wrapped__`` attributes.

        Parameters
        ----------
        func
            The callable whose return values should be memoised. Set
            automatically by :func:`flexwrap`.
        maxsize
            LRU bound forwarded to :func:`functools.lru_cache`.
            ``None`` disables the bound.
        typed
            Forwarded to :func:`functools.lru_cache` to control
            whether equal-but-differently-typed arguments are
            distinguished by the cache key.

        See Also
        --------
        functools.lru_cache : Underlying cache engine wrapped here.
        cache_info : Inspect hit/miss statistics.

        Examples
        --------
        >>> from mayutils.environment.memoisation import lru_cache
        >>> @lru_cache(maxsize=4)
        ... def add(a, b):
        ...     return a + b
        >>> add(1, 2)
        3
        """
        self.func = func
        self.maxsize = maxsize
        self.typed = typed
        self._cached: LRUCacheWrapper[object] = functools.lru_cache(
            maxsize=maxsize,
            typed=typed,
        )(func)

        update_wrapper(wrapper=self, wrapped=func)

    def cache_info(
        self,
    ) -> CacheInfo:
        """
        Report accumulated hit/miss statistics for the underlying LRU.

        Delegates to the :class:`functools._CacheInfo` surface
        exposed by :func:`functools.lru_cache`, so callers see the
        same ``(hits, misses, maxsize, currsize)`` quadruple they
        would from an un-decorated stdlib LRU.

        Returns
        -------
            Named tuple as returned by
            :meth:`functools.lru_cache.cache_info`.

        See Also
        --------
        functools.lru_cache : Stdlib cache whose statistics are forwarded.
        cache_clear : Reset the counters by clearing the cache.

        Examples
        --------
        >>> from mayutils.environment.memoisation import lru_cache
        >>> @lru_cache
        ... def square(n):
        ...     return n * n
        >>> _ = square(2)
        >>> square.cache_info().misses
        1
        """
        return self._cached.cache_info()

    def cache_clear(
        self,
    ) -> None:
        """
        Evict every entry from the underlying LRU cache.

        Delegates directly to :meth:`functools.lru_cache.cache_clear`,
        resetting the hit/miss counters in the process.

        See Also
        --------
        functools.lru_cache : Stdlib cache whose ``cache_clear`` is forwarded.
        cache_info : Inspect hit/miss statistics after clearing.

        Examples
        --------
        >>> from mayutils.environment.memoisation import lru_cache
        >>> @lru_cache
        ... def square(n):
        ...     return n * n
        >>> _ = square(2)
        >>> square.cache_clear()
        >>> square.cache_info().hits
        0
        """
        self._cached.cache_clear()

    def bypass_cache(
        self,
        *args: object,
        **kwargs: object,
    ) -> object:
        """
        Invoke the wrapped function directly, bypassing the cache.

        Skips the LRU lookup entirely and forwards all arguments to
        the original callable unchanged.

        Parameters
        ----------
        *args
            Positional arguments forwarded to the wrapped callable.
        **kwargs
            Keyword arguments forwarded to the wrapped callable.

        Returns
        -------
            The value produced by the wrapped callable.

        See Also
        --------
        cache_clear : Evict every entry from the underlying LRU cache.
        cache_info : Inspect hit/miss statistics.

        Examples
        --------
        >>> from mayutils.environment.memoisation import lru_cache
        >>> @lru_cache
        ... def square(n):
        ...     return n * n
        >>> square.bypass_cache(4)
        16
        """
        return self.func(*args, **kwargs)

    def __call__(
        self,
        *args: object,
        **kwargs: object,
    ) -> object:
        """
        Dispatch the call through the LRU cache, honouring ``cache=False``.

        Routes through :func:`functools.lru_cache` when ``cache`` is
        truthy and otherwise calls the wrapped function directly so
        side-effecting code paths (live queries, randomised
        computations) can skip caching on demand without needing a
        separate API.

        Parameters
        ----------
        *args
            Positional arguments forwarded to the wrapped callable
            and included in the LRU cache key.
        **kwargs
            Keyword arguments forwarded to the wrapped callable and
            included in the LRU cache key. Pass ``cache=False`` to
            bypass the LRU for a single invocation.

        Returns
        -------
            The value produced by the wrapped callable, either served
            from the cache or freshly computed.

        See Also
        --------
        functools.lru_cache : Stdlib cache that services hits.
        cache_info : Inspect hit/miss statistics post-call.

        Examples
        --------
        >>> from mayutils.environment.memoisation import lru_cache
        >>> @lru_cache
        ... def square(n):
        ...     return n * n
        >>> square(3)
        9
        >>> square(3, cache=False)
        9
        """
        use_cache = kwargs.pop("cache", True)
        if not use_cache:
            return self.bypass_cache(*args, **kwargs)

        return self._cached(*args, **kwargs)


@flexwrap
class cache[CacheObjectType]:  # noqa: N801
    """
    Unified memoisation decorator with pluggable storage backend.

    Backend selection:

    - ``@cache`` — in-memory via :class:`MemoryStore`
    - ``@cache(persist=True)`` — file-backed, suffix inferred from
      return type on first call
    - ``@cache(suffix="parquet")`` — file-backed with explicit suffix
    - ``@cache(path="store.pkl")`` — in-memory with pickle warm-start

    The store is accessible via :attr:`store`.

    Parameters
    ----------
    func
        The callable to memoise. Set by :func:`flexwrap`.
    suffix
        File extension for file-backed caching. Implies
        ``persist=True``. ``None`` with ``persist=False`` means
        in-memory only.
    persist
        When ``True`` without ``suffix``, uses file-backed caching
        with suffix inferred from the return type on first call.
    path
        Pickle file for warm-start persistence (memory mode only).
    cache_folder
        Root directory for file-backed caches.
    ttl
        Lifetime of each entry.
    maxsize
        LRU bound (memory mode only).
    key_prefix
        Human-readable prefix prepended to cache keys. Useful for
        file-backed caches to produce readable filenames.
    backend
        DataFrame backend token for DataFile formats.
    shared
        Memory mode only. When ``True``, share a process-global store across
        decorations of the same callable (see :meth:`__init__`). Mutually
        exclusive with ``path``.

    See Also
    --------
    lru_cache : C-accelerated in-memory LRU cache without TTL or
        persistence.
    mayutils.environment.memoisation.memory.MemoryStore : In-memory
        backend used by default.
    mayutils.environment.memoisation.files.FileStore : File-backed
        backend selected when ``suffix`` or ``persist`` is set.

    Examples
    --------
    >>> from mayutils.environment.memoisation import cache
    >>> @cache
    ... def square(n: int) -> int:
    ...     return n * n
    >>> square(3)
    9
    >>> square.cache_info().misses
    1
    """

    def __init__(
        self,
        func: Callable[..., CacheObjectType],
        /,
        *,
        suffix: str | None = None,
        persist: bool = False,
        path: Path | str | None = None,
        cache_folder: Path | str = CACHE_FOLDER,
        ttl: Duration | None = None,
        maxsize: int | None = None,
        key_prefix: str | None = None,
        backend: Backend[Any] | None = None,
        shared: bool = False,
    ) -> None:
        """
        Bind the wrapped callable and configure the cache backend.

        Selects :class:`FileStore` when ``suffix`` or ``persist`` is
        set, otherwise falls back to :class:`MemoryStore`.

        Parameters
        ----------
        func
            The callable to memoise. Set by :func:`flexwrap`.
        suffix
            File extension for file-backed caching. Implies
            ``persist=True``. ``None`` with ``persist=False`` means
            in-memory only.
        persist
            When ``True`` without ``suffix``, uses file-backed caching
            with suffix inferred from the return type on first call.
        path
            Pickle file for warm-start persistence (memory mode only).
        cache_folder
            Root directory for file-backed caches.
        ttl
            Lifetime of each entry.
        maxsize
            LRU bound (memory mode only).
        key_prefix
            Human-readable prefix prepended to cache keys. Useful for
            file-backed caches to produce readable filenames.
        backend
            DataFrame backend token for DataFile formats.
        shared
            Memory mode only. When ``True``, resolve a process-global store
            keyed by the callable's ``module.__qualname__`` (via
            :func:`~mayutils.environment.memoisation.memory.get_shared_store`)
            instead of a fresh per-instance store, so independently-constructed
            decorators of the same callable memoise against one another. Mutually
            exclusive with ``path``.

        Raises
        ------
        ValueError
            If ``shared`` is combined with ``path`` (they are mutually exclusive).

        See Also
        --------
        lru_cache : C-accelerated in-memory LRU cache.
        MemoryStore : In-memory backend.
        FileStore : File-backed backend.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache(ttl=None)
        ... def add(a, b):
        ...     return a + b
        >>> add(1, 2)
        3
        """
        self.func = func
        self._key_prefix: str | None = key_prefix
        self._persist_path: Path | None = None

        if suffix is not None or persist:
            self.store: CacheStore[CacheObjectType] = FileStore(
                getattr(func, "__name__", type(func).__name__),
                cache_folder=Path(cache_folder),
                suffix=suffix,
                ttl=ttl,
                backend=backend,
            )

        elif path is not None:
            if shared:
                msg = "cache(shared=True) is incompatible with path= (pickle warm-start)."
                raise ValueError(msg)

            self.store = MemoryStore.load(
                path,
                ttl=ttl,
                maxsize=maxsize,
            )
            self._persist_path = Path(path)

        elif shared:
            self.store = get_shared_store(
                f"{getattr(func, '__module__', '')}.{getattr(func, '__qualname__', type(func).__name__)}",
                ttl=ttl,
                maxsize=maxsize,
            )

        else:
            self.store = MemoryStore(ttl=ttl, maxsize=maxsize)

        update_wrapper(wrapper=self, wrapped=func)

    @property
    def persist_path(self) -> Path | None:
        """
        Return the pickle persistence path, or ``None`` if not configured.

        Only meaningful for :class:`MemoryStore`-backed caches
        constructed with a ``path`` argument.

        Returns
        -------
            The configured pickle path, or ``None``.

        See Also
        --------
        save : Persist the in-memory cache to the returned path.
        load_store : Reload a previously saved pickle cache.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache
        ... def square(n):
        ...     return n * n
        >>> square.persist_path is None
        True
        """
        return getattr(self, "_persist_path", None)

    @property
    def key_prefix(
        self,
    ) -> str | None:
        """
        Human-readable prefix prepended to cache keys for file-backed stores.

        When set, the prefix is joined to the hash digest with ``--``
        so that cache files are easier to identify on disk.

        Returns
        -------
            The current prefix string, or ``None`` if unset.

        See Also
        --------
        func_key : Builds the full cache key using this prefix.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache(key_prefix="demo")
        ... def square(n):
        ...     return n * n
        >>> square.key_prefix
        'demo'
        """
        return self._key_prefix

    @key_prefix.setter
    def key_prefix(
        self,
        value: str | None,
    ) -> None:
        """
        Set the human-readable prefix prepended to cache keys.

        Updating the prefix affects all subsequent cache key
        computations via :meth:`func_key`.

        Parameters
        ----------
        value
            New prefix string, or ``None`` to disable prefixing.

        See Also
        --------
        func_key : Builds the full cache key using this prefix.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache
        ... def square(n):
        ...     return n * n
        >>> square.key_prefix = "v2"
        >>> square.key_prefix
        'v2'
        """
        self._key_prefix = value

    def func_key(
        self,
        *args: object,
        **kwargs: object,
    ) -> str:
        """
        Compute the cache key, optionally prepending :attr:`key_prefix`.

        Delegates to :func:`make_cache_key` with the wrapped callable's
        name and the supplied call arguments.

        Parameters
        ----------
        *args
            Positional arguments that form part of the cache key.
        **kwargs
            Keyword arguments that form part of the cache key.

        Returns
        -------
            The computed cache key string.

        See Also
        --------
        mayutils.environment.memoisation.utilities.make_cache_key :
            Underlying key builder.
        key_prefix : Human-readable prefix joined to the key.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache
        ... def square(n):
        ...     return n * n
        >>> isinstance(square.func_key(3), str)
        True
        """
        base_key = make_cache_key(
            getattr(self.func, "__name__", type(self.func).__name__),
            args=args,
            kwargs=kwargs,
        )
        if self._key_prefix is not None:
            return f"{self._key_prefix}--{base_key}"

        return base_key

    def cache_info(
        self,
    ) -> CacheInfo:
        """
        Return ``(hits, misses, maxsize, currsize)``.

        Delegates to the underlying store's
        :meth:`~mayutils.environment.memoisation.types.CacheStore.cache_info`.

        Returns
        -------
            Named tuple with cache statistics.

        See Also
        --------
        cache_clear : Reset statistics by clearing all entries.
        lru_cache.cache_info : Equivalent on the LRU sibling.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache
        ... def square(n):
        ...     return n * n
        >>> _ = square(2)
        >>> square.cache_info().misses
        1
        """
        return self.store.cache_info()

    def cache_clear(
        self,
    ) -> None:
        """
        Remove all cached entries.

        Delegates to the underlying store's ``clear`` method, evicting
        every key.

        See Also
        --------
        cache_info : Inspect statistics after clearing.
        delete_cache : Remove a single entry by call signature.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache
        ... def square(n):
        ...     return n * n
        >>> _ = square(2)
        >>> square.cache_clear()
        >>> square.cache_info().currsize
        0
        """
        self.store.clear()

    def delete_cache(
        self,
        *args: object,
        **kwargs: object,
    ) -> bool:
        """
        Remove the cache entry for a specific call signature.

        Computes the cache key from the supplied arguments and deletes
        the corresponding entry from the store.

        Parameters
        ----------
        *args
            Positional arguments identifying the cached call.
        **kwargs
            Keyword arguments identifying the cached call.

        Returns
        -------
            ``True`` if an entry was removed, ``False`` otherwise.

        See Also
        --------
        cache_clear : Remove all entries at once.
        func_key : Inspect the key that would be deleted.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache
        ... def square(n):
        ...     return n * n
        >>> _ = square(5)
        >>> square.delete_cache(5)
        True
        """
        return self.store.delete(self.func_key(*args, **kwargs))

    def get_path(
        self,
        *args: object,
        **kwargs: object,
    ) -> Path:
        """
        Return the cache file path for a call signature.

        Only available for file-backed caches.

        Parameters
        ----------
        *args
            Positional arguments identifying the cached call.
        **kwargs
            Keyword arguments identifying the cached call.

        Returns
        -------
            The resolved cache file path for the given arguments.

        Raises
        ------
        TypeError
            When the store is not a :class:`FileStore`.

        See Also
        --------
        func_key : Inspect the key used to derive the path.
        mayutils.environment.memoisation.files.FileStore.get_path :
            Underlying path resolution.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache(suffix="pkl")
        ... def square(n):
        ...     return n * n
        >>> square.get_path(3).suffix
        '.pkl'
        """
        if not isinstance(self.store, FileStore):
            msg = "get_path() requires a file-backed cache"
            raise TypeError(msg)

        return self.store.get_path(self.func_key(*args, **kwargs))

    def save(
        self,
        path: Path | str,
        /,
    ) -> None:
        """
        Persist the in-memory cache to a ``.pkl`` file.

        Only available for :class:`MemoryStore`-backed caches.
        :class:`FileStore` caches are already persisted on each put.

        Parameters
        ----------
        path
            Destination ``.pkl`` file.

        Raises
        ------
        TypeError
            When the store is not a :class:`MemoryStore`.

        See Also
        --------
        load_store : Reload a previously saved pickle cache.
        persist_path : Configured default persistence path.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache
        ... def square(n):
        ...     return n * n
        >>> _ = square(2)
        >>> square.save("/tmp/square_cache.pkl")  # doctest: +SKIP
        """
        if not isinstance(self.store, MemoryStore):
            msg = "save() is only available for in-memory caches"
            raise TypeError(msg)

        self.store.save(path)

    def load_store(
        self,
        path: Path | str,
        /,
    ) -> None:
        """
        Merge a previously saved ``.pkl`` cache into this store.

        Only available for :class:`MemoryStore`-backed caches.

        Parameters
        ----------
        path
            Source ``.pkl`` file to load.

        Raises
        ------
        TypeError
            When the store is not a :class:`MemoryStore`.

        See Also
        --------
        save : Persist the in-memory cache to a pickle file.
        persist_path : Configured default persistence path.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache
        ... def square(n):
        ...     return n * n
        >>> square.load_store("/tmp/square_cache.pkl")  # doctest: +SKIP
        """
        if not isinstance(self.store, MemoryStore):
            msg = "load_store() is only available for in-memory caches"
            raise TypeError(msg)

        loaded = cast(
            "MemoryStore[CacheObjectType]",
            MemoryStore.load(
                path,
                ttl=self.store.ttl,
                maxsize=self.store.maxsize,
            ),
        )

        self.store.store.update(loaded.store)  # ty:ignore[no-matching-overload]

    def bypass_cache(
        self,
        *args: object,
        **kwargs: object,
    ) -> CacheObjectType:
        """
        Invoke the wrapped function directly, bypassing the cache.

        Skips both the cache lookup and the cache update, forwarding
        all arguments to the original callable unchanged.

        Parameters
        ----------
        *args
            Positional arguments forwarded to the wrapped callable.
        **kwargs
            Keyword arguments forwarded to the wrapped callable.

        Returns
        -------
            The value produced by the wrapped callable.

        See Also
        --------
        refresh : Recompute and update the cached entry.
        cache_clear : Evict every cached entry.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache
        ... def square(n):
        ...     return n * n
        >>> square.bypass_cache(4)
        16
        """
        return self.func(*args, **kwargs)

    def refresh(
        self,
        *args: object,
        **kwargs: object,
    ) -> CacheObjectType:
        """
        Force recomputation and cache the fresh result.

        Bypasses the existing cached value, invokes the wrapped
        callable, stores the new result, and returns it.

        Parameters
        ----------
        *args
            Positional arguments forwarded to the wrapped callable.
        **kwargs
            Keyword arguments forwarded to the wrapped callable.

        Returns
        -------
            The freshly computed value.

        See Also
        --------
        bypass_cache : Call without touching the cache at all.
        delete_cache : Remove an entry without recomputing.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache
        ... def square(n):
        ...     return n * n
        >>> square.refresh(3)
        9
        """
        key = self.func_key(*args, **kwargs)
        result = self.bypass_cache(*args, **kwargs)
        self.store.put(key, value=result)

        if isinstance(self.store, MemoryStore) and self.persist_path is not None:
            self.store.save(self.persist_path)

        return result

    def __call__(
        self,
        *args: object,
        **kwargs: object,
    ) -> CacheObjectType:
        """
        Dispatch through the cache.

        Looks up the cache key derived from the arguments, returns the
        stored value on a hit, or computes and stores it on a miss.

        Parameters
        ----------
        *args
            Positional arguments forwarded to the wrapped callable.
        **kwargs
            Keyword arguments forwarded to the wrapped callable.

        Returns
        -------
            The cached or freshly computed value.

        See Also
        --------
        bypass_cache : Skip the cache entirely.
        refresh : Force recomputation even on a hit.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache
        ... def square(n):
        ...     return n * n
        >>> square(3)
        9
        """
        key = self.func_key(*args, **kwargs)

        result = self.store.get(key)
        if not isinstance(result, Missing):
            return result

        result = self.func(*args, **kwargs)
        self.store.put(key, value=result)

        if isinstance(self.store, MemoryStore) and self.persist_path is not None:
            self.store.save(self.persist_path)

        return result


__all__ = [
    "cache",
    "lru_cache",
]
