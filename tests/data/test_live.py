"""Tests for live data queries."""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
import pytest
from pendulum import Duration

from mayutils.data.live import StreamingQuery, WindowedQuery
from mayutils.objects.dataframes.backends import Backend, DataFrames
from mayutils.objects.datetime import UTC, DateTime
from mayutils.objects.types import SQL

# ------------------------------------------------------------------
# Test fixtures
# ------------------------------------------------------------------


class SequentialReader:
    """Return pre-loaded DataFrames in round-robin order."""

    def __init__(self, *frames: Any) -> None:  # noqa: ANN401
        """Store *frames* for sequential retrieval."""
        self._frames = list(frames)
        self._calls = 0

    def __call__(
        self,
        query: str,  # noqa: ARG002
        /,
        *,
        backend: Backend[Any] | None = None,  # noqa: ARG002
    ) -> Any:  # noqa: ANN401
        """
        Return the next frame and increment the call counter.

        Returns
        -------
            The next pre-loaded DataFrame in round-robin order.
        """
        frame = self._frames[self._calls % len(self._frames)]
        self._calls += 1
        return frame

    @property
    def call_count(self) -> int:
        """Return the number of times the reader was invoked."""
        return self._calls


class FailingReader:
    """Reader that succeeds a configurable number of times then raises."""

    def __init__(
        self,
        *,
        error: Exception | None = None,
        succeed_first: int = 0,
        fallback_frame: Any = None,  # noqa: ANN401
    ) -> None:
        """Configure the failure behaviour."""
        self._error = error or RuntimeError("reader failure")
        self._succeed_first = succeed_first
        self._fallback_frame = fallback_frame
        self._calls = 0

    def __call__(
        self,
        query: str,  # noqa: ARG002
        /,
        *,
        backend: Backend[Any] | None = None,  # noqa: ARG002
    ) -> Any:  # noqa: ANN401
        """
        Return the fallback frame or raise after *succeed_first* calls.

        Returns
        -------
            The fallback DataFrame if within the success window.
        """
        self._calls += 1
        if self._calls <= self._succeed_first:
            return self._fallback_frame
        raise self._error

    @property
    def call_count(self) -> int:
        """Return the number of times the reader was invoked."""
        return self._calls


# ------------------------------------------------------------------
# StreamingQuery
# ------------------------------------------------------------------


def _make_streaming(
    *frames: pd.DataFrame,
    initial_cursor: object = 0,
    cursor_column: str = "id",
    max_rows: int | None = None,
    max_age: Duration | None = None,
    backend: Backend[pd.DataFrame] | None = None,
) -> StreamingQuery[pd.DataFrame]:
    return StreamingQuery(
        SQL("SELECT * FROM t WHERE id > {{ cursor }}"),
        cursor_column=cursor_column,
        initial_cursor=initial_cursor,
        reader=SequentialReader(*frames),
        max_rows=max_rows,
        max_age=max_age,
        backend=backend,
    )


class TestStreamingInitialFetch:
    """Verify first fetch populates data and sets cursor state."""

    def test_populates_data(self) -> None:
        """Initial fetch stores all returned rows."""
        df = pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})
        view = _make_streaming(df)
        assert len(view.data) == 3  # noqa: PLR2004

    def test_infers_numeric_dtype(self) -> None:
        """Numeric cursor column is not flagged as datetime."""
        df = pd.DataFrame({"id": [1, 2, 3]})
        view = _make_streaming(df)
        assert view.cursor_is_datetime is False

    def test_infers_datetime_dtype(self) -> None:
        """Datetime initial cursor is detected automatically."""
        df = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01", "2026-01-02"])})
        view = _make_streaming(
            df,
            cursor_column="ts",
            initial_cursor=pd.Timestamp("2020-01-01"),
        )
        assert view.cursor_is_datetime is True

    def test_cursor_set_to_max(self) -> None:
        """Cursor advances to the maximum value in the cursor column."""
        df = pd.DataFrame({"id": [1, 5, 3]})
        view = _make_streaming(df)
        assert view.cursor_value == 5  # noqa: PLR2004

    def test_empty_initial_fetch(self) -> None:
        """Empty result leaves data empty and cursor unchanged."""
        df = pd.DataFrame({"id": pd.Series([], dtype=int)})
        view = _make_streaming(df)
        assert view.data.empty


class TestStreamingUpdate:
    """Verify incremental updates append rows and advance the cursor."""

    def test_appends_rows(self) -> None:
        """Delta rows are concatenated to existing data."""
        initial = pd.DataFrame({"id": [1, 2, 3], "v": [10, 20, 30]})
        delta = pd.DataFrame({"id": [4, 5], "v": [40, 50]})
        view = _make_streaming(initial, delta)
        view.update(force=True)
        assert len(view.data) == 5  # noqa: PLR2004

    def test_cursor_advances(self) -> None:
        """Cursor moves to the max of the newly fetched rows."""
        initial = pd.DataFrame({"id": [1, 2, 3]})
        delta = pd.DataFrame({"id": [4, 5]})
        view = _make_streaming(initial, delta)
        assert view.cursor_value == 3  # noqa: PLR2004
        view.update(force=True)
        assert view.cursor_value == 5  # noqa: PLR2004

    def test_empty_delta_unchanged(self) -> None:
        """Empty delta leaves data and cursor unchanged."""
        initial = pd.DataFrame({"id": [1, 2, 3]})
        empty = pd.DataFrame({"id": pd.Series([], dtype=int)})
        view = _make_streaming(initial, empty)
        view.update(force=True)
        assert len(view.data) == 3  # noqa: PLR2004


class TestStreamingRetention:
    """Verify max_rows and max_age retention policies."""

    def test_max_rows(self) -> None:
        """Excess rows are trimmed from the head after update."""
        initial = pd.DataFrame({"id": [1, 2, 3]})
        delta = pd.DataFrame({"id": [4, 5, 6]})
        view = _make_streaming(initial, delta, max_rows=4)
        view.update(force=True)
        assert len(view.data) == 4  # noqa: PLR2004
        np.testing.assert_array_equal(view.data["id"].values, [3, 4, 5, 6])

    def test_max_age(self) -> None:
        """Rows older than max_age are dropped after update."""
        initial = pd.DataFrame(
            {"ts": pd.to_datetime(["2026-01-01", "2026-01-10", "2026-01-20"]), "v": [1, 2, 3]},
        )
        delta = pd.DataFrame({"ts": pd.to_datetime(["2026-01-25"]), "v": [4]})
        view = _make_streaming(
            initial,
            delta,
            cursor_column="ts",
            initial_cursor=pd.Timestamp("2020-01-01"),
            max_age=Duration(days=10),
        )
        view.update(force=True)
        assert all(view.data["ts"] >= pd.Timestamp("2026-01-15"))

    def test_max_age_ignored_for_numeric(self) -> None:
        """Numeric cursors without strftime skip age-based retention."""
        initial = pd.DataFrame({"id": [1, 2, 3]})
        delta = pd.DataFrame({"id": [4, 5]})
        view = _make_streaming(initial, delta, max_age=Duration(hours=1))
        view.update(force=True)
        assert len(view.data) == 5  # noqa: PLR2004

    def test_invalid_max_rows(self) -> None:
        """Zero max_rows raises ValueError at init."""
        with pytest.raises(ValueError, match="max_rows must be positive"):
            _make_streaming(pd.DataFrame({"id": [1]}), max_rows=0)

    def test_invalid_max_age(self) -> None:
        """Negative max_age raises ValueError at init."""
        with pytest.raises(ValueError, match="max_age must be positive"):
            _make_streaming(pd.DataFrame({"id": [1]}), max_age=Duration(hours=-1))


class TestStreamingErrorHandling:
    """Verify data is preserved when the reader raises."""

    def test_logs_and_skips(self) -> None:
        """Failed fetch restores previous data snapshot."""
        initial = pd.DataFrame({"id": [1, 2, 3]})
        reader = FailingReader(succeed_first=1, fallback_frame=initial)
        view = StreamingQuery(
            SQL("SELECT * FROM t WHERE id > {{ cursor }}"),
            cursor_column="id",
            initial_cursor=0,
            reader=reader,
        )
        view.update(force=True)
        assert len(view.data) == 3  # noqa: PLR2004


class TestStreamingRateLimiting:
    """Verify update_frequency throttling."""

    def test_skips_when_too_frequent(self) -> None:
        """Update is skipped when called before update_frequency elapses."""
        initial = pd.DataFrame({"id": [1, 2]})
        delta = pd.DataFrame({"id": [3]})
        reader = SequentialReader(initial, delta)
        view = StreamingQuery(
            SQL("SELECT * FROM t WHERE id > {{ cursor }}"),
            cursor_column="id",
            initial_cursor=0,
            reader=reader,
            update_frequency=Duration(hours=1),
        )
        view.update()
        assert reader.call_count == 1

    def test_force_overrides(self) -> None:
        """Force bypasses the update_frequency throttle."""
        initial = pd.DataFrame({"id": [1, 2]})
        delta = pd.DataFrame({"id": [3]})
        reader = SequentialReader(initial, delta)
        view = StreamingQuery(
            SQL("SELECT * FROM t WHERE id > {{ cursor }}"),
            cursor_column="id",
            initial_cursor=0,
            reader=reader,
            update_frequency=Duration(hours=1),
        )
        view.update(force=True)
        assert reader.call_count == 2  # noqa: PLR2004


class TestStreamingReset:
    """Verify reset replaces data with a fresh fetch."""

    def test_resets_data(self) -> None:
        """Reset discards appended rows and re-fetches."""
        initial = pd.DataFrame({"id": [1, 2, 3]})
        delta = pd.DataFrame({"id": [4, 5]})
        view = _make_streaming(initial, delta, initial)
        view.update(force=True)
        assert len(view.data) == 5  # noqa: PLR2004
        view.reset()
        assert len(view.data) == 3  # noqa: PLR2004


class TestStreamingPolars:
    """Verify StreamingQuery works with the polars backend."""

    def test_full_lifecycle(self) -> None:
        """Init, update, and cursor advance work end-to-end with polars."""
        initial = pl.DataFrame({"id": [1, 2, 3], "v": [10, 20, 30]})
        delta = pl.DataFrame({"id": [4, 5], "v": [40, 50]})
        view = StreamingQuery(
            SQL("SELECT * FROM t WHERE id > {{ cursor }}"),
            cursor_column="id",
            initial_cursor=0,
            reader=SequentialReader(initial, delta),
            backend=Backend(pl.DataFrame),
        )
        assert view.data.height == 3  # noqa: PLR2004
        assert view.cursor_value == 3  # noqa: PLR2004
        view.update(force=True)
        assert view.data.height == 5  # noqa: PLR2004
        assert view.cursor_value == 5  # noqa: PLR2004


class TestStreamingJinjaKwargsMerge:
    """Verify that fetch injects ``cursor`` and overrides any stored value."""

    def test_cursor_key_wins_over_stored_value(self) -> None:
        """Internal cursor injection overrides a ``cursor`` key in jinja_kwargs."""
        df = pd.DataFrame({"id": [1, 2, 3]})
        rendered_queries: list[str] = []
        original_reader = SequentialReader(df)

        def capturing_reader(
            query: str,
            /,
            *,
            backend: Any = None,  # noqa: ANN401, ARG001
        ) -> Any:  # noqa: ANN401
            rendered_queries.append(query)
            return original_reader(query)

        StreamingQuery(
            SQL("SELECT * FROM {{ table }} WHERE id > {{ cursor }}"),
            cursor_column="id",
            initial_cursor=0,
            reader=capturing_reader,
            jinja_kwargs={"table": "loans", "cursor": "SHADOWED"},
        )

        assert len(rendered_queries) == 1
        assert "FROM loans" in rendered_queries[0]
        assert "SHADOWED" not in rendered_queries[0]


# ------------------------------------------------------------------
# WindowedQuery
# ------------------------------------------------------------------


def _make_windowed(
    *frames: pd.DataFrame,
    rolling: bool = False,
    start_timestamp: DateTime | None = None,
    deduplicate: bool = False,
    max_rows: int | None = None,
    max_age: Duration | None = None,
) -> WindowedQuery[pd.DataFrame]:
    return WindowedQuery(
        SQL("SELECT * FROM t WHERE ts BETWEEN '{{ start_timestamp }}' AND '{{ end_timestamp }}'"),
        index_column="ts",
        start_timestamp=start_timestamp or DateTime(2026, 1, 1, tzinfo=UTC),
        reader=SequentialReader(*frames),
        rolling=rolling,
        deduplicate=deduplicate,
        max_rows=max_rows,
        max_age=max_age,
    )


class TestWindowedInitialFetch:
    """Verify first fetch populates data and sets interval."""

    def test_populates_data(self) -> None:
        """Initial fetch stores all returned rows."""
        df = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01", "2026-01-02"]), "count": [100, 200]})
        view = _make_windowed(df)
        assert len(view.data) == 2  # noqa: PLR2004

    def test_interval_set(self) -> None:
        """Interval start matches the configured start_timestamp."""
        df = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01"]), "count": [100]})
        view = _make_windowed(df)
        assert view.interval.start == DateTime(2026, 1, 1, tzinfo=UTC)

    def test_empty_initial(self) -> None:
        """Empty result leaves data empty."""
        df = pd.DataFrame(
            {"ts": pd.Series([], dtype="datetime64[ns]"), "count": pd.Series([], dtype=int)},
        )
        view = _make_windowed(df)
        assert view.data.empty


class TestWindowedExpandingUpdate:
    """Verify non-rolling (expanding) window updates."""

    def test_appends_delta(self) -> None:
        """Delta rows are concatenated to existing data."""
        initial = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01", "2026-01-02"]), "count": [100, 200]})
        delta = pd.DataFrame({"ts": pd.to_datetime(["2026-01-03"]), "count": [150]})
        view = _make_windowed(initial, delta, rolling=False)
        view.update(force=True)
        assert len(view.data) == 3  # noqa: PLR2004

    def test_window_start_unchanged(self) -> None:
        """Expanding window keeps the original start timestamp."""
        initial = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01"]), "c": [1]})
        delta = pd.DataFrame({"ts": pd.to_datetime(["2026-01-02"]), "c": [2]})
        start = DateTime(2026, 1, 1, tzinfo=UTC)
        view = _make_windowed(initial, delta, rolling=False, start_timestamp=start)
        view.update(force=True)
        assert view.interval.start == start


class TestWindowedRollingUpdate:
    """Verify rolling window slides forward on update."""

    def test_slides_window(self) -> None:
        """Rolling update advances the window start."""
        initial = pd.DataFrame(
            {"ts": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]), "count": [1, 2, 3]},
        )
        delta = pd.DataFrame({"ts": pd.to_datetime(["2026-01-04"]), "count": [4]})
        view = _make_windowed(initial, delta, rolling=True)
        original_start = view.interval.start
        view.update(force=True)
        assert view.interval.start > original_start

    def test_empty_delta_still_updates_interval(self) -> None:
        """Interval advances even when the delta is empty."""
        initial = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01"]), "c": [1]})
        empty = pd.DataFrame({"ts": pd.Series([], dtype="datetime64[ns]"), "c": pd.Series([], dtype=int)})
        view = _make_windowed(initial, empty, rolling=True)
        old_end = view.interval.end
        view.update(force=True)
        assert view.interval.end > old_end


class TestWindowedDeduplication:
    """Verify deduplication on index_column after concat."""

    def test_deduplicate_removes_stale_buckets(self) -> None:
        """Duplicate index values keep only the last occurrence."""
        initial = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01", "2026-01-02"]), "total": [100, 200]})
        delta = pd.DataFrame({"ts": pd.to_datetime(["2026-01-02"]), "total": [250]})
        view = _make_windowed(initial, delta, rolling=False, deduplicate=True)
        view.update(force=True)
        assert len(view.data) == 2  # noqa: PLR2004
        assert view.data.loc[view.data["ts"] == pd.Timestamp("2026-01-02"), "total"].iloc[0] == 250  # noqa: PLR2004

    def test_no_dedup_by_default(self) -> None:
        """Without deduplicate, duplicate index values are preserved."""
        initial = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01"]), "total": [100]})
        delta = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01"]), "total": [150]})
        view = _make_windowed(initial, delta, rolling=False)
        view.update(force=True)
        assert len(view.data) == 2  # noqa: PLR2004


class TestWindowedRetention:
    """Verify max_rows and max_age retention policies."""

    def test_max_rows(self) -> None:
        """Excess rows are trimmed from the head after update."""
        initial = pd.DataFrame(
            {"ts": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]), "c": [1, 2, 3]},
        )
        delta = pd.DataFrame({"ts": pd.to_datetime(["2026-01-04", "2026-01-05"]), "c": [4, 5]})
        view = _make_windowed(initial, delta, max_rows=3)
        view.update(force=True)
        assert len(view.data) == 3  # noqa: PLR2004

    def test_max_age(self) -> None:
        """Rows older than max_age are dropped after update."""
        initial = pd.DataFrame(
            {"ts": pd.to_datetime(["2026-01-01", "2026-01-10", "2026-01-20"]), "c": [1, 2, 3]},
        )
        delta = pd.DataFrame({"ts": pd.to_datetime(["2026-01-25"]), "c": [4]})
        view = _make_windowed(initial, delta, max_age=Duration(days=10))
        view.update(force=True)
        assert all(view.data["ts"] >= pd.Timestamp("2026-01-15"))


class TestWindowedErrorHandling:
    """Verify data is preserved when the reader raises."""

    def test_logs_and_skips(self) -> None:
        """Failed fetch restores previous data and interval."""
        initial = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01"]), "c": [1]})
        reader = FailingReader(succeed_first=1, fallback_frame=initial)
        view = WindowedQuery(
            SQL("SELECT * FROM t WHERE ts BETWEEN '{{ start_timestamp }}' AND '{{ end_timestamp }}'"),
            index_column="ts",
            start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
            reader=reader,
        )
        view.update(force=True)
        assert len(view.data) == 1


class TestWindowedReset:
    """Verify reset re-initialises the window and data."""

    def test_reseeds(self) -> None:
        """Reset discards appended rows and re-fetches."""
        initial = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01"]), "c": [1]})
        delta = pd.DataFrame({"ts": pd.to_datetime(["2026-01-02"]), "c": [2]})
        view = _make_windowed(initial, delta, initial)
        view.update(force=True)
        assert len(view.data) == 2  # noqa: PLR2004
        view.reset()
        assert len(view.data) == 1

    def test_reset_with_new_start(self) -> None:
        """Reset with a new start_timestamp shifts the window."""
        initial = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01"]), "c": [1]})
        new_start = DateTime(2026, 2, 1, tzinfo=UTC)
        view = _make_windowed(initial, initial)
        view.reset(start_timestamp=new_start)
        assert view.interval.start == new_start


class TestWindowedRateLimiting:
    """Verify update_frequency throttling."""

    def test_skips_when_too_frequent(self) -> None:
        """Update is skipped when called before update_frequency elapses."""
        initial = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01"]), "c": [1]})
        delta = pd.DataFrame({"ts": pd.to_datetime(["2026-01-02"]), "c": [2]})
        reader = SequentialReader(initial, delta)
        view = WindowedQuery(
            SQL("SELECT * FROM t WHERE ts BETWEEN '{{ start_timestamp }}' AND '{{ end_timestamp }}'"),
            index_column="ts",
            start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
            reader=reader,
            update_frequency=Duration(hours=1),
        )
        view.update()
        assert reader.call_count == 1

    def test_force_overrides(self) -> None:
        """Force bypasses the update_frequency throttle."""
        initial = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01"]), "c": [1]})
        delta = pd.DataFrame({"ts": pd.to_datetime(["2026-01-02"]), "c": [2]})
        reader = SequentialReader(initial, delta)
        view = WindowedQuery(
            SQL("SELECT * FROM t WHERE ts BETWEEN '{{ start_timestamp }}' AND '{{ end_timestamp }}'"),
            index_column="ts",
            start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
            reader=reader,
            update_frequency=Duration(hours=1),
        )
        view.update(force=True)
        assert reader.call_count == 2  # noqa: PLR2004


class TestWindowedTimeFormat:
    """Verify custom time_format is applied to query rendering."""

    def test_format_applied(self) -> None:
        """Timestamps in the rendered query use the configured format."""
        df = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01"]), "c": [1]})
        queries: list[str] = []
        original_reader = SequentialReader(df, df)

        def capturing_reader[DataFrameType: DataFrames = pd.DataFrame](
            query: str,
            /,
            *,
            backend: Backend[DataFrameType] | None = None,  # noqa: ARG001
        ) -> DataFrameType:
            queries.append(query)
            return original_reader(query)

        WindowedQuery(
            SQL("SELECT * FROM t WHERE ts BETWEEN '{{ start_timestamp }}' AND '{{ end_timestamp }}'"),
            index_column="ts",
            start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
            reader=capturing_reader,
            time_format="%Y-%m-%d",
        )
        assert "2026-01-01" in queries[0]


class TestWindowedPolars:
    """Verify WindowedQuery works with the polars backend."""

    def test_full_lifecycle(self) -> None:
        """Init and update work end-to-end with polars DataFrames."""
        initial = pl.DataFrame(
            {
                "ts": [datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC), datetime.datetime(2026, 1, 2, tzinfo=datetime.UTC)],
                "count": [100, 200],
            },
        )
        delta = pl.DataFrame(
            {
                "ts": [datetime.datetime(2026, 1, 3, tzinfo=datetime.UTC)],
                "count": [150],
            },
        )
        view = WindowedQuery(
            SQL("SELECT * FROM t WHERE ts BETWEEN '{{ start_timestamp }}' AND '{{ end_timestamp }}'"),
            index_column="ts",
            start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
            reader=SequentialReader(initial, delta),
            backend=Backend(pl.DataFrame),
            rolling=False,
        )
        assert view.data.height == 2  # noqa: PLR2004
        view.update(force=True)
        assert view.data.height == 3  # noqa: PLR2004


class TestWindowedJinjaKwargsMerge:
    """Verify that fetch injects window boundaries and overrides stored values."""

    def test_timestamp_keys_win_over_stored_values(self) -> None:
        """Internal timestamp injection overrides shadowed keys in jinja_kwargs."""
        df = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01"]), "c": [1]})
        rendered_queries: list[str] = []
        original_reader = SequentialReader(df)

        def capturing_reader(
            query: str,
            /,
            *,
            backend: Any = None,  # noqa: ANN401, ARG001
        ) -> Any:  # noqa: ANN401
            rendered_queries.append(query)
            return original_reader(query)

        WindowedQuery(
            SQL("SELECT * FROM {{ table }} WHERE ts BETWEEN '{{ start_timestamp }}' AND '{{ end_timestamp }}'"),
            index_column="ts",
            start_timestamp=DateTime(2026, 1, 1, tzinfo=UTC),
            reader=capturing_reader,
            time_format="%Y-%m-%d",
            jinja_kwargs={"table": "loans", "start_timestamp": "SHADOWED"},
        )

        assert len(rendered_queries) == 1
        assert "FROM loans" in rendered_queries[0]
        assert "SHADOWED" not in rendered_queries[0]
        assert "2026-01-01" in rendered_queries[0]
