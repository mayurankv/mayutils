"""
Provide filesystem-backed memoisation with optional TTL semantics.

This package groups cache stores, memoisation decorators, and cache
clearing into a cohesive namespace. All public symbols are re-exported
here so that ``from mayutils.environment.memoisation import ...`` works.

See Also
--------
mayutils.environment.memoisation.types : Shared :data:`MISSING`
    sentinel and :class:`CacheStore` protocol.
mayutils.environment.memoisation.utilities : Cache-key generation and
    TTL helpers.
mayutils.environment.memoisation.memory : In-memory cache backend.
mayutils.environment.memoisation.files : File-backed cache backend
    with pluggable serialisation.
mayutils.environment.memoisation.decorators : :class:`cache` and
    :class:`lru_cache` decorator classes.
mayutils.environment.memoisation.clearing : Cache clearing.
"""

from mayutils.data import CACHE_FOLDER
from mayutils.environment.memoisation.clearing import clear_cache
from mayutils.environment.memoisation.decorators import (
    cache,
    lru_cache,
)
from mayutils.environment.memoisation.files import (
    FileStore,
    get_serialiser,
    make_cache_stem,
)
from mayutils.environment.memoisation.memory import (
    SHARED_STORES,
    MemoryStore,
    clear_shared_stores,
    get_shared_store,
)
from mayutils.environment.memoisation.types import (
    MISSING,
    CacheStore,
)
from mayutils.environment.memoisation.utilities import (
    expiry,
    format_ttl,
    is_expired,
    make_cache_key,
)

__all__ = [
    "CACHE_FOLDER",
    "MISSING",
    "SHARED_STORES",
    "CacheStore",
    "FileStore",
    "MemoryStore",
    "cache",
    "clear_cache",
    "clear_shared_stores",
    "expiry",
    "format_ttl",
    "get_serialiser",
    "get_shared_store",
    "is_expired",
    "lru_cache",
    "make_cache_key",
    "make_cache_stem",
]
