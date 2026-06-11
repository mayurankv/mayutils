"""Tests for the polars temporal parsing implementation."""

import polars as pl

from mayutils.objects.dataframes.polars.dataframes import parse_temporal_columns


def test_parses_date_datetime_time_and_leaves_others() -> None:
    """String temporal columns convert to Date/Datetime/Time; labels stay."""
    frame = pl.DataFrame(
        {
            "d": ["2026-01-01", "2026-06-11"],
            "ts": ["2026-01-01T10:00:00", "2026-06-11T23:59:59"],
            "t": ["09:30:00", "17:00:00"],
            "label": ["a", "b"],
        }
    )
    parsed = parse_temporal_columns(frame)

    assert parsed.schema["d"] == pl.Date
    assert isinstance(parsed.schema["ts"], pl.Datetime)
    assert parsed.schema["t"] == pl.Time
    assert parsed.schema["label"] == pl.String
    assert frame.schema["d"] == pl.String  # input not mutated


def test_leaves_unconvertible_columns() -> None:
    """A column whose tail breaks conversion is left unchanged, not nulled."""
    values = ["2026-01-01"] * 150
    values[120] = "not a date"
    frame = pl.DataFrame({"d": values})
    assert parse_temporal_columns(frame).schema["d"] == pl.String


def test_idempotent_and_null_safe() -> None:
    """Already-temporal and all-null columns pass through unchanged."""
    frame = pl.DataFrame({"d": pl.Series([None, None], dtype=pl.String)})
    assert parse_temporal_columns(frame).schema["d"] == pl.String
