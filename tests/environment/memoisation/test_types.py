"""Tests for ``mayutils.environment.memoisation.types``.

Covers the :data:`MISSING` cache-miss sentinel and the runtime-checkable
:class:`CacheStore` protocol. Importing the module pulls in numpy and the
DataFrame backends, so the optional extras are required.
"""

from __future__ import annotations

import pytest

pytest.importorskip("numpy")
pytest.importorskip("pandas")
pytest.importorskip("polars")

from mayutils.environment.memoisation.memory import MemoryStore
from mayutils.environment.memoisation.types import (
    MISSING,
    CacheStore,
    Missing,
)


class TestMissingSentinel:
    """Tests for :data:`MISSING` — the single cache-miss sentinel."""

    def test_missing_is_the_enum_member(self) -> None:
        """``MISSING`` is exactly the single ``Missing`` enum member."""
        assert MISSING is Missing.MISSING

    def test_missing_is_singleton(self) -> None:
        """The enum has exactly one member, so all references are identical."""
        assert list(Missing) == [Missing.MISSING]

    def test_missing_is_distinct_from_none(self) -> None:
        """``MISSING`` is distinguishable from a cached ``None``."""
        assert MISSING is not None

    def test_missing_is_falsey_check_uses_identity(self) -> None:
        """An ``is`` check distinguishes a miss from any stored value, including 0."""
        stored: object = 0
        assert stored is not MISSING


class TestCacheStoreProtocol:
    """Tests for :class:`CacheStore` — the runtime-checkable store protocol."""

    def test_memory_store_satisfies_protocol(self) -> None:
        """:class:`MemoryStore` structurally satisfies :class:`CacheStore`."""
        assert isinstance(MemoryStore(), CacheStore)

    def test_plain_object_does_not_satisfy_protocol(self) -> None:
        """An object missing the required methods fails the runtime check."""
        assert not isinstance(object(), CacheStore)

    @pytest.mark.parametrize(
        "method",
        ["get", "put", "delete", "clear", "cache_info"],
    )
    def test_protocol_requires_method(self, method: str) -> None:
        """Each documented method is part of the protocol surface."""
        assert hasattr(CacheStore, method)
