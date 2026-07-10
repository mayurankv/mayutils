"""
Regression tests for three ``read_query``-path caching/parsing bugs.

- Bug A: ``cache(persist=False)`` / ``read_query(persist=False)`` did not memoise
  across calls (each call built a fresh per-instance ``MemoryStore``).
- Bug B: ``make_cache_stem`` embedded every template kwarg in the filename, so a long
  value (e.g. ``source_sql``) blew past the filesystem name limit (``OSError 63``).
- Bug C: ``parse_temporal_columns`` crashed on duplicate column labels because
  ``frame[label]`` returns a DataFrame, not a Series.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pandas as pd

from mayutils.data.read import read_query
from mayutils.environment.memoisation import (
    SHARED_STORES,
    cache,
    clear_shared_stores,
    get_shared_store,
)
from mayutils.environment.memoisation.files import make_cache_stem
from mayutils.objects.dataframes.pandas.dataframes import parse_temporal_columns
from mayutils.objects.types import SQL

if TYPE_CHECKING:
    from mayutils.data.read import QueryReader
    from mayutils.objects.dataframes.backends import Backend, DataFrames


class _Counter:
    """Records how many times its callable was actually invoked."""

    def __init__(self) -> None:
        self.calls = 0

    def double(self, value: int) -> int:
        self.calls += 1
        return value * 2


class TestSharedCache:
    """Bug A: opt-in shared in-memory store on ``cache``."""

    def test_shared_memoises_across_instances(self) -> None:
        """Two independent ``cache(shared=True)`` wrappers share one store."""
        clear_shared_stores()
        counter = _Counter()

        cache(shared=True)(counter.double)(3)
        cache(shared=True)(counter.double)(3)

        assert counter.calls == 1

    def test_default_is_isolated(self) -> None:
        """Default ``cache()`` keeps a private store per decoration."""
        counter = _Counter()

        cache(counter.double)(3)
        cache(counter.double)(3)

        assert counter.calls == 2  # noqa: PLR2004


class TestSharedStores:
    """Bug A: the process-global shared-store registry."""

    def test_same_namespace_returns_same_store(self) -> None:
        """One namespace resolves to a single shared store instance."""
        clear_shared_stores()
        assert get_shared_store("ns") is get_shared_store("ns")

    def test_distinct_namespaces_are_separate(self) -> None:
        """Different namespaces resolve to different stores."""
        clear_shared_stores()
        assert get_shared_store("a") is not get_shared_store("b")

    def test_clear_empties_registry(self) -> None:
        """``clear_shared_stores`` drops every registered store."""
        get_shared_store("ns")
        assert SHARED_STORES
        clear_shared_stores()
        assert not SHARED_STORES


class TestReadQueryMemoisation:
    """Bug A: ``read_query(persist=False)`` memoises across calls."""

    @staticmethod
    def _counting_reader(counter: dict[str, int]) -> QueryReader:
        def reader[DataFrameType: DataFrames = pd.DataFrame](
            query: str,  # noqa: ARG001
            /,
            *,
            backend: Backend[DataFrameType] | None = None,  # noqa: ARG001
        ) -> DataFrameType:
            counter["n"] += 1
            return cast("DataFrameType", pd.DataFrame({"x": [1]}))

        return reader

    def test_persist_false_memoises_across_calls(self) -> None:
        """Three identical ``persist=False`` calls hit the reader once."""
        clear_shared_stores()
        counter = {"n": 0}
        reader = self._counting_reader(counter)
        for _ in range(3):
            read_query(SQL("SELECT 1 AS one"), reader=reader, persist=False, parse_temporal=False)
        assert counter["n"] == 1

    def test_distinct_queries_miss(self) -> None:
        """Different queries do not share a cache entry."""
        clear_shared_stores()
        counter = {"n": 0}
        reader = self._counting_reader(counter)
        read_query(SQL("SELECT 1 AS one"), reader=reader, persist=False, parse_temporal=False)
        read_query(SQL("SELECT 2 AS two"), reader=reader, persist=False, parse_temporal=False)
        assert counter["n"] == 2  # noqa: PLR2004

    def test_persist_none_bypasses_cache(self) -> None:
        """``persist=None`` executes the reader on every call."""
        counter = {"n": 0}
        reader = self._counting_reader(counter)
        for _ in range(3):
            read_query(SQL("SELECT 1 AS one"), reader=reader, persist=None, parse_temporal=False)
        assert counter["n"] == 3  # noqa: PLR2004


class TestMakeCacheStemLength:
    """Bug B: ``make_cache_stem`` stays within filesystem name limits."""

    @staticmethod
    def _stem(template_kwargs: dict[str, object], *, key: str = "", cache_description: str | None = None) -> str:
        return make_cache_stem(
            SQL("SELECT * FROM funnel"),
            cache_description=cache_description,
            ttl=None,
            template_kwargs=template_kwargs,
            cache_extra=None,
            key=key,
        )

    def test_long_kwargs_are_bounded(self) -> None:
        """A huge template-kwarg value cannot blow the stem length."""
        long_value = ",".join(f"'source_{index}'" for index in range(500))
        assert len(self._stem({"source_sql": long_value})) <= 150  # noqa: PLR2004

    def test_is_deterministic(self) -> None:
        """The same inputs always produce the same stem."""
        kwargs: dict[str, object] = {"source_sql": ",".join(f"'s{index}'" for index in range(500))}
        assert self._stem(kwargs) == self._stem(kwargs)

    def test_key_preserved_when_truncating(self) -> None:
        """A non-empty key survives at the tail even with an oversized prefix."""
        key = "0" * 64
        stem = self._stem({}, key=key, cache_description="x" * 400)
        assert stem.endswith(key)
        assert len(stem) <= 150  # noqa: PLR2004


class TestParseTemporalColumnsDuplicates:
    """Bug C: ``parse_temporal_columns`` tolerates duplicate column labels."""

    def test_duplicate_labels_do_not_crash(self) -> None:
        """Duplicate labels parse without raising and keep their structure."""
        frame = pd.DataFrame(
            [[1, "2026-01-01", 2], [3, "2026-02-01", 4]],
            columns=["id", "enquiry_created", "id"],
            index=[10, 20],
        )

        result = parse_temporal_columns(frame)

        assert result.shape == (2, 3)
        assert list(result.columns).count("id") == 2  # noqa: PLR2004
        assert pd.api.types.is_datetime64_any_dtype(result["enquiry_created"])
        assert list(result.index) == [10, 20]
        # input is not mutated
        assert frame["enquiry_created"].dtype == object
