"""Tests for ``mayutils.environment.memoisation.memory``.

Covers the in-memory :class:`MemoryStore`: get/put round-trips, hit and
miss accounting, lazy TTL eviction, LRU bounding, deletion, clearing, and
the pickle save/load cycle. Requires the ``datetime`` extra (pendulum) via
the TTL helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("pendulum")

from mayutils.environment.memoisation.memory import MemoryStore
from mayutils.environment.memoisation.types import MISSING
from mayutils.objects.datetime import Duration

if TYPE_CHECKING:
    from pathlib import Path


class TestGetPut:
    """Tests for :meth:`MemoryStore.get` / :meth:`MemoryStore.put` round-trips."""

    def test_miss_returns_missing(self) -> None:
        """An absent key returns the :data:`MISSING` sentinel."""
        assert MemoryStore[int]().get("absent") is MISSING

    def test_put_then_get_returns_value(self) -> None:
        """A stored value is returned by a subsequent lookup."""
        store = MemoryStore[int]()
        store.put("k", value=42)
        assert store.get("k") == 42  # noqa: PLR2004

    def test_cached_none_is_not_a_miss(self) -> None:
        """A cached ``None`` is distinguishable from a miss via :data:`MISSING`."""
        store = MemoryStore[None]()
        store.put("k", value=None)
        assert store.get("k") is None
        assert store.get("k") is not MISSING

    def test_put_overwrites_existing(self) -> None:
        """Re-putting a key overwrites the previous value."""
        store = MemoryStore[int]()
        store.put("k", value=1)
        store.put("k", value=2)
        assert store.get("k") == 2  # noqa: PLR2004


class TestHitMissCounters:
    """Tests for the ``hits`` / ``misses`` accounting surfaced by :meth:`cache_info`."""

    def test_miss_increments_misses(self) -> None:
        """A lookup of an absent key increments ``misses``."""
        store = MemoryStore[int]()
        store.get("absent")
        assert store.cache_info().misses == 1
        assert store.cache_info().hits == 0

    def test_hit_increments_hits(self) -> None:
        """A lookup of a present key increments ``hits``."""
        store = MemoryStore[int]()
        store.put("k", value=1)
        store.get("k")
        assert store.cache_info().hits == 1

    def test_cache_info_reports_currsize_and_maxsize(self) -> None:
        """``cache_info`` reflects live entries and the configured bound."""
        store = MemoryStore[int](maxsize=5)
        store.put("a", value=1)
        store.put("b", value=2)
        info = store.cache_info()
        assert info.currsize == 2  # noqa: PLR2004
        assert info.maxsize == 5  # noqa: PLR2004


class TestTTLEviction:
    """Tests for lazy TTL eviction on :meth:`MemoryStore.get`."""

    def test_expired_entry_is_a_miss(self) -> None:
        """An entry past its TTL is evicted on access and counts as a miss."""
        store = MemoryStore[int](ttl=Duration(seconds=-1))
        store.put("k", value=1)
        assert store.get("k") is MISSING
        assert store.cache_info().misses == 1

    def test_expired_entry_is_removed_from_store(self) -> None:
        """Accessing an expired entry drops it from the backing store."""
        store = MemoryStore[int](ttl=Duration(seconds=-1))
        store.put("k", value=1)
        store.get("k")
        assert store.cache_info().currsize == 0

    def test_unexpired_entry_is_a_hit(self) -> None:
        """A live entry within its TTL is served as a hit."""
        store = MemoryStore[int](ttl=Duration(hours=1))
        store.put("k", value=1)
        assert store.get("k") == 1
        assert store.cache_info().hits == 1

    def test_no_ttl_never_expires(self) -> None:
        """With no TTL configured, entries are served indefinitely."""
        store = MemoryStore[int]()
        store.put("k", value=1)
        assert store.get("k") == 1


class TestLRUEviction:
    """Tests for the bounded-LRU behaviour of :meth:`MemoryStore.put`."""

    def test_oldest_entry_evicted_when_over_maxsize(self) -> None:
        """Inserting beyond ``maxsize`` evicts the least-recently-used entry."""
        store = MemoryStore[int](maxsize=2)
        store.put("a", value=1)
        store.put("b", value=2)
        store.put("c", value=3)
        assert store.cache_info().currsize == 2  # noqa: PLR2004
        assert store.get("a") is MISSING
        assert store.get("c") == 3  # noqa: PLR2004

    def test_get_refreshes_recency(self) -> None:
        """A read moves an entry to the most-recent end, sparing it from eviction."""
        store = MemoryStore[int](maxsize=2)
        store.put("a", value=1)
        store.put("b", value=2)
        store.get("a")  # "a" is now most-recently-used
        store.put("c", value=3)  # should evict "b", not "a"
        assert store.get("a") == 1
        assert store.get("b") is MISSING

    def test_unbounded_when_maxsize_none(self) -> None:
        """A ``None`` maxsize keeps every entry."""
        store = MemoryStore[int]()
        for index in range(50):
            store.put(str(index), value=index)
        assert store.cache_info().currsize == 50  # noqa: PLR2004


class TestDelete:
    """Tests for :meth:`MemoryStore.delete`."""

    def test_delete_present_returns_true(self) -> None:
        """Deleting a present key removes it and returns ``True``."""
        store = MemoryStore[int]()
        store.put("k", value=1)
        assert store.delete("k") is True
        assert store.get("k") is MISSING

    def test_delete_absent_returns_false(self) -> None:
        """Deleting an absent key is a no-op returning ``False``."""
        assert MemoryStore[int]().delete("absent") is False


class TestClear:
    """Tests for :meth:`MemoryStore.clear`."""

    def test_clear_empties_store_and_resets_counters(self) -> None:
        """Clearing removes every entry and zeroes the hit/miss counters."""
        store = MemoryStore[int]()
        store.put("k", value=1)
        store.get("k")  # hit
        store.get("x")  # miss
        store.clear()
        info = store.cache_info()
        assert info.currsize == 0
        assert info.hits == 0
        assert info.misses == 0


class TestSaveLoad:
    """Tests for the pickle :meth:`MemoryStore.save` / :meth:`MemoryStore.load` cycle."""

    def test_round_trip_preserves_entries(self, tmp_path: Path) -> None:
        """A saved store reloads with its entries intact."""
        path = tmp_path / "memo.pkl"
        store = MemoryStore[int]()
        store.put("k", value=99)
        store.save(path)
        loaded = MemoryStore[int].load(path)
        assert loaded.get("k") == 99  # noqa: PLR2004

    def test_save_creates_parent_directory(self, tmp_path: Path) -> None:
        """Saving into a missing directory creates the parent path."""
        path = tmp_path / "nested" / "dir" / "memo.pkl"
        store = MemoryStore[int]()
        store.put("k", value=1)
        store.save(path)
        assert path.is_file()

    def test_load_missing_file_yields_empty_store(self, tmp_path: Path) -> None:
        """Loading a non-existent ``.pkl`` produces an empty store rather than erroring."""
        loaded = MemoryStore[int].load(tmp_path / "missing.pkl")
        assert loaded.cache_info().currsize == 0

    def test_load_carries_ttl_and_maxsize(self, tmp_path: Path) -> None:
        """``load`` applies the supplied TTL and maxsize to the new store."""
        path = tmp_path / "memo.pkl"
        MemoryStore[int]().save(path)
        loaded = MemoryStore[int].load(path, ttl=Duration(hours=1), maxsize=10)
        assert loaded.ttl == Duration(hours=1)
        assert loaded.maxsize == 10  # noqa: PLR2004

    def test_save_rejects_non_pkl_suffix(self, tmp_path: Path) -> None:
        """Saving to a non-``.pkl`` path raises :class:`ValueError`."""
        with pytest.raises(expected_exception=ValueError, match=r"\.pkl"):
            MemoryStore[int]().save(tmp_path / "memo.json")

    def test_load_rejects_non_pkl_suffix(self, tmp_path: Path) -> None:
        """Loading from a non-``.pkl`` path raises :class:`ValueError`."""
        with pytest.raises(expected_exception=ValueError, match=r"\.pkl"):
            MemoryStore[int].load(tmp_path / "memo.json")
