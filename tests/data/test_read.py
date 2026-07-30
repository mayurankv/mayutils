"""Tests for ``mayutils.data.read``."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pandas as pd
import pytest
from jinja2.exceptions import UndefinedError
from pendulum import Duration

from mayutils.data.read import (
    QueryInputWarning,
    looks_like_sql_path,
    read_query,
    render_query,
    stream_query,
)
from mayutils.environment.memoisation.clearing import clear_cache
from mayutils.environment.memoisation.files import make_cache_stem
from mayutils.objects.dataframes.backends import DataFrames
from mayutils.objects.types import SQL

if TYPE_CHECKING:
    from collections.abc import Iterator

    from mayutils.objects.dataframes.backends import Backend


class TestRenderQuery:
    """Tests for :func:`render_query`."""

    def test_inline_sql_with_template_kwargs(self) -> None:
        """Jinja kwargs are interpolated into the inline SQL template."""
        result = render_query(SQL("SELECT * FROM {{ table }}"), template_kwargs={"table": "loans"})
        assert result == "SELECT * FROM loans"

    def test_inline_sql_no_kwargs(self) -> None:
        """An inline SQL string without placeholders is returned verbatim."""
        result = render_query(SQL("SELECT 1"))
        assert result == "SELECT 1"

    def test_path_dispatches_to_format_query(self) -> None:
        """A Path argument is resolved via format_query, not inline rendering."""
        with patch("mayutils.data.read.format_query", return_value="mocked") as mock:
            result = render_query(Path("loans_summary"))
        mock.assert_called_once()
        assert result == "mocked"

    def test_missing_variable_raises_undefined_error(self) -> None:
        """A template variable absent from template_kwargs raises UndefinedError."""
        with pytest.raises(UndefinedError):
            render_query(SQL("SELECT * FROM {{ table }}"))

    def test_inline_for_loop_expansion(self) -> None:
        """A Jinja for loop in an inline template expands to the exact SQL string."""
        result = render_query(
            SQL("SELECT {% for col in cols %}{{ col }}{% if not loop.last %}, {% endif %}{% endfor %} FROM loans"),
            template_kwargs={"cols": ("loan_id", "amount")},
        )
        assert result == "SELECT loan_id, amount FROM loans"


class TestQueryInputWarning:
    """Tests for the heuristic warning in :func:`render_query`."""

    def test_warns_on_sql_suffix(self) -> None:
        """A string ending in ``.sql`` warns and dispatches to format_query."""
        with (
            patch("mayutils.data.read.format_query", return_value="resolved") as mock,
            warnings.catch_warnings(record=True) as w,
        ):
            warnings.simplefilter("always")
            result = render_query(SQL("my_query.sql"))
        assert len(w) == 1
        assert issubclass(w[0].category, QueryInputWarning)
        mock.assert_called_once()
        assert result == "resolved"

    def test_warns_on_path_separators(self) -> None:
        """A string with path separators and no SQL keywords warns and dispatches."""
        with (
            patch("mayutils.data.read.format_query", return_value="resolved") as mock,
            warnings.catch_warnings(record=True) as w,
        ):
            warnings.simplefilter("always")
            result = render_query(SQL("queries/revenue"))
        assert len(w) == 1
        assert issubclass(w[0].category, QueryInputWarning)
        mock.assert_called_once()
        assert result == "resolved"

    def test_no_warning_on_valid_sql(self) -> None:
        """A string containing SQL keywords does not trigger a warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            render_query(SQL("SELECT * FROM t"))
        assert len(w) == 0

    def test_no_warning_on_path_like_with_keyword(self) -> None:
        """A string with path separators but also SQL keywords does not warn."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            render_query(SQL("SELECT * FROM schema/table"))
        assert len(w) == 0

    def test_warns_when_file_exists_and_resolves(self, tmp_path: Path) -> None:
        """A string matching an existing query file warns, then resolves it."""
        query_file = tmp_path / "revenue.sql"
        query_file.write_text("SELECT 1")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = render_query(SQL("revenue"), queries_folders=(tmp_path,))
        assert len(w) == 1
        assert issubclass(w[0].category, QueryInputWarning)
        assert "revenue.sql" in str(w[0].message)
        assert result == "SELECT 1"

    def test_warning_stacklevel(self) -> None:
        """The warning points at the caller, not at render_query internals."""
        with (
            patch("mayutils.data.read.format_query", return_value="resolved"),
            warnings.catch_warnings(record=True) as w,
        ):
            warnings.simplefilter("always")
            render_query(SQL("my_query.sql"))
        assert len(w) == 1
        assert w[0].filename == __file__

    def test_warns_but_format_query_raises_propagates(self) -> None:
        """If the heuristic fires but format_query can't find the file, the error propagates."""
        with pytest.warns(QueryInputWarning), pytest.raises(ValueError, match="No query"):
            render_query(SQL("nonexistent.sql"))


class TestLooksLikeSqlPath:
    """Tests for :func:`looks_like_sql_path`."""

    def test_returns_none_for_sql(self) -> None:
        """Strings containing SQL keywords are not flagged."""
        assert looks_like_sql_path("SELECT 1", queries_folders=()) is None

    def test_detects_sql_suffix(self) -> None:
        """Strings ending in ``.sql`` are flagged."""
        result = looks_like_sql_path("my_query.sql", queries_folders=())
        assert result is not None
        assert ".sql" in result

    def test_sql_suffix_takes_priority_over_keyword(self) -> None:
        """A ``.sql`` suffix is flagged even when the string contains a SQL keyword."""
        result = looks_like_sql_path("SELECT foo.sql", queries_folders=())
        assert result is not None

    def test_detects_path_separators(self) -> None:
        """Strings with path separators and no spaces are flagged."""
        result = looks_like_sql_path("queries/revenue", queries_folders=())
        assert result is not None

    def test_ignores_path_separator_with_spaces(self) -> None:
        """Strings with path separators but also spaces are not flagged."""
        assert looks_like_sql_path("a / b", queries_folders=()) is None

    def test_case_insensitive_keyword_match(self) -> None:
        """SQL keyword detection is case-insensitive."""
        assert looks_like_sql_path("select 1", queries_folders=()) is None

    def test_detects_existing_file(self, tmp_path: Path) -> None:
        """Strings matching an existing query file in queries_folders are flagged."""
        query_file = tmp_path / "revenue.sql"
        query_file.write_text("SELECT 1")
        result = looks_like_sql_path("revenue", queries_folders=(tmp_path,))
        assert result is not None
        assert str(query_file) in result

    def test_no_match_returns_none(self) -> None:
        """A bare name with no SQL keywords and no matching file returns None."""
        assert looks_like_sql_path("revenue", queries_folders=()) is None


class TestMakeCacheStem:
    """Tests for :func:`_make_cache_stem`."""

    def test_inline_sql_uses_first_three_words(self) -> None:
        """Inline SQL stems contain the first three words slugified."""
        stem = make_cache_stem(
            SQL("SELECT * FROM loans WHERE x = 1"),
            cache_description=None,
            ttl=None,
            template_kwargs={},
            cache_extra=None,
            key="abcdef123456789",
        )
        assert stem.startswith("select_from--abcdef123456")

    def test_path_uses_stem_and_kwargs(self) -> None:
        """Path queries include the file stem and format kwargs."""
        stem = make_cache_stem(
            Path("loans/by_region"),
            cache_description=None,
            ttl=None,
            template_kwargs={"region": "London"},
            cache_extra=None,
            key="abcdef123456789",
        )
        assert "by_region" in stem
        assert "region_london" in stem

    def test_cache_description_overrides(self) -> None:
        """An explicit cache_description replaces the auto-generated one."""
        stem = make_cache_stem(
            SQL("SELECT 1"),
            cache_description="daily volume snapshot",
            ttl=None,
            template_kwargs={},
            cache_extra=None,
            key="abcdef123456789",
        )
        assert stem.startswith("daily_volume_snapshot--abcdef123456")

    def test_ttl_hours(self) -> None:
        """TTL in hours is appended as ``ttl_Nh``."""
        stem = make_cache_stem(
            SQL("SELECT 1"),
            cache_description=None,
            ttl=Duration(hours=6),
            template_kwargs={},
            cache_extra=None,
            key="abcdef123456789",
        )
        assert "ttl_6h" in stem

    def test_ttl_minutes(self) -> None:
        """TTL in minutes is appended as ``ttl_Nm``."""
        stem = make_cache_stem(
            SQL("SELECT 1"),
            cache_description=None,
            ttl=Duration(minutes=30),
            template_kwargs={},
            cache_extra=None,
            key="abcdef123456789",
        )
        assert "ttl_30m" in stem

    def test_ttl_days(self) -> None:
        """TTL in days is appended as ``ttl_Nd``."""
        stem = make_cache_stem(
            SQL("SELECT 1"),
            cache_description=None,
            ttl=Duration(days=2),
            template_kwargs={},
            cache_extra=None,
            key="abcdef123456789",
        )
        assert "ttl_2d" in stem

    def test_cache_extra_included(self) -> None:
        """Cache extra kwargs appear in the stem for inline SQL."""
        stem = make_cache_stem(
            SQL("SELECT 1"),
            cache_description=None,
            ttl=None,
            template_kwargs={},
            cache_extra={"warehouse": "analytics_m"},
            key="abcdef123456789",
        )
        assert "warehouse_analytics_m" in stem

    def test_full_hash_preserved(self) -> None:
        """The full hash is preserved in the stem to avoid collisions."""
        key = "abcdef1234567890extra"
        stem = make_cache_stem(
            SQL("SELECT 1"),
            cache_description=None,
            ttl=None,
            template_kwargs={},
            cache_extra=None,
            key=key,
        )
        assert stem.endswith(key)


class TestClearCache:
    """Tests for :func:`clear_cache`."""

    def test_clears_memory_stores(self) -> None:
        """Cache registry stores passed to clear_cache are flushed."""
        from mayutils.environment.memoisation.memory import MemoryStore

        store: MemoryStore[int] = MemoryStore()
        store.put("test_key", value=42)
        clear_cache(stores=(store,), cache_folder=Path("/nonexistent"))
        assert store.cache_info().currsize == 0

    def test_deletes_all_files_when_no_ttl(self, tmp_path: Path) -> None:
        """All files are deleted when ttl is None."""
        (tmp_path / "a.parquet").write_bytes(b"data")
        (tmp_path / "b.csv").write_bytes(b"data")
        (tmp_path / ".gitkeep").touch()

        deleted = clear_cache(ttl=None, cache_folder=tmp_path)
        assert len(deleted) == 2  # noqa: PLR2004
        assert (tmp_path / ".gitkeep").exists()

    def test_preserves_fresh_files(self, tmp_path: Path) -> None:
        """Files newer than ttl are preserved."""
        (tmp_path / "fresh.parquet").write_bytes(b"data")

        deleted = clear_cache(ttl=Duration(hours=1), cache_folder=tmp_path)
        assert len(deleted) == 0
        assert (tmp_path / "fresh.parquet").exists()

    def test_returns_empty_for_missing_folder(self) -> None:
        """A non-existent cache folder returns an empty list."""
        deleted = clear_cache(cache_folder=Path("/nonexistent/path"))
        assert deleted == []

    def test_deletes_files_in_subdirectories(self, tmp_path: Path) -> None:
        """Files in subdirectories of the cache folder are also deleted."""
        sub = tmp_path / "read_query"
        sub.mkdir()
        (sub / "cached.parquet").write_bytes(b"data")

        deleted = clear_cache(ttl=None, cache_folder=tmp_path)
        assert len(deleted) == 1


class TestTemporalParsing:
    """Tests for automatic temporal parsing in :func:`read_query` and :func:`stream_query`."""

    def test_read_query_parses_temporal_columns(self) -> None:
        """String date columns from the reader come back as datetime64."""

        def reader[DataFrameType: DataFrames = pd.DataFrame](
            query: str,
            /,
            *,
            backend: Backend[DataFrameType] | None = None,
        ) -> DataFrameType:
            assert "SELECT" in query
            assert backend is not None
            return cast("DataFrameType", pd.DataFrame({"d": ["2026-01-01", "2026-06-11"]}))

        result = read_query(SQL("SELECT 1"), reader=reader, persist=None)
        assert result["d"].dtype == "datetime64[ns]"

    def test_read_query_parse_temporal_opt_out(self) -> None:
        """parse_temporal=False preserves raw string columns."""

        def reader[DataFrameType: DataFrames = pd.DataFrame](
            query: str,
            /,
            *,
            backend: Backend[DataFrameType] | None = None,
        ) -> DataFrameType:
            assert "SELECT" in query
            assert backend is not None
            return cast("DataFrameType", pd.DataFrame({"d": ["2026-01-01"]}))

        result = read_query(SQL("SELECT 1"), reader=reader, persist=None, parse_temporal=False)
        assert result["d"].dtype == object

    def test_read_query_parses_temporal_columns_with_cache(self) -> None:
        """The in-memory cached path also returns parsed frames."""

        def reader[DataFrameType: DataFrames = pd.DataFrame](
            query: str,
            /,
            *,
            backend: Backend[DataFrameType] | None = None,
        ) -> DataFrameType:
            assert "SELECT" in query
            assert backend is not None
            return cast("DataFrameType", pd.DataFrame({"d": ["2026-01-01", "2026-06-11"]}))

        first = read_query(SQL("SELECT 1 AS c1"), reader=reader, persist=False)
        second = read_query(SQL("SELECT 1 AS c1"), reader=reader, persist=False)
        assert first["d"].dtype == "datetime64[ns]"
        assert second["d"].dtype == "datetime64[ns]"

    def test_stream_query_parses_each_chunk(self) -> None:
        """Every streamed chunk is temporally parsed."""

        def streamer[DataFrameType: DataFrames = pd.DataFrame](
            query: str,
            /,
            *,
            backend: Backend[DataFrameType] | None = None,
        ) -> Iterator[DataFrameType]:
            assert "SELECT" in query
            assert backend is not None
            yield cast("DataFrameType", pd.DataFrame({"d": ["2026-01-01"]}))
            yield cast("DataFrameType", pd.DataFrame({"d": ["2026-06-11"]}))

        chunks = list(stream_query(SQL("SELECT 1"), streamer=streamer))
        assert all(chunk["d"].dtype == "datetime64[ns]" for chunk in chunks)
