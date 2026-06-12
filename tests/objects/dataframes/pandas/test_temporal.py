"""Tests for the pandas temporal parsing implementation."""

import datetime

import pandas as pd

from mayutils.objects.dataframes.pandas.dataframes import parse_temporal_columns


def test_parses_date_datetime_time_and_leaves_others() -> None:
    """String temporal columns convert; labels and numerics are untouched."""
    frame = pd.DataFrame(
        {
            "d": ["2026-01-01", "2026-06-11"],
            "ts": ["2026-01-01 10:00:00", "2026-06-11 23:59:59"],
            "t": ["09:30:00", "17:00:00"],
            "label": ["a", "b"],
            "n": [1, 2],
        }
    )
    parsed = parse_temporal_columns(frame)

    assert parsed["d"].dtype == "datetime64[ns]"
    assert parsed["ts"].dtype == "datetime64[ns]"
    assert parsed["t"].tolist() == [datetime.time(9, 30), datetime.time(17, 0)]
    assert parsed["label"].tolist() == ["a", "b"]
    assert parsed["n"].dtype == frame["n"].dtype
    assert frame["d"].dtype == object  # input not mutated


def test_parses_date_object_columns() -> None:
    """Object columns of datetime.date (Snowflake DATE shape) convert to datetime64."""
    frame = pd.DataFrame({"d": [datetime.date(2026, 1, 1), datetime.date(2026, 6, 11)]})
    parsed = parse_temporal_columns(frame)
    assert parsed["d"].dtype == "datetime64[ns]"


def test_leaves_unconvertible_columns() -> None:
    """A column whose tail breaks conversion is left unchanged, not nulled."""
    values = ["2026-01-01"] * 150
    values[120] = "not a date"
    frame = pd.DataFrame({"d": values})
    parsed = parse_temporal_columns(frame)
    assert parsed["d"].dtype == object


def test_idempotent() -> None:
    """Re-parsing an already-parsed frame is a no-op."""
    once = parse_temporal_columns(pd.DataFrame({"d": ["2026-01-01"]}))
    twice = parse_temporal_columns(once)
    pd.testing.assert_frame_equal(once, twice)


def test_empty_and_all_null_columns_skipped() -> None:
    """Empty and all-null columns pass through unchanged."""
    frame = pd.DataFrame({"d": pd.Series([None, None], dtype=object)})
    parsed = parse_temporal_columns(frame)
    assert parsed["d"].dtype == object
