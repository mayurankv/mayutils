"""Tests for automatic temporal column detection and dispatch."""

import pandas as pd
import polars as pl

from mayutils.objects.dataframes.backends import Backend
from mayutils.objects.dataframes.temporal import detect_temporal_kind, parse_temporal_columns


def test_detect_temporal_kind_dates() -> None:
    """ISO date strings are detected as dates."""
    assert detect_temporal_kind(("2026-01-01", "2026-06-11")) == "date"


def test_detect_temporal_kind_datetimes() -> None:
    """ISO datetimes with T or space separators and offsets are detected."""
    assert detect_temporal_kind(("2026-01-01T10:00:00", "2026-06-11 23:59:59.123+00:00")) == "datetime"


def test_detect_temporal_kind_times() -> None:
    """Bare clock times are detected as times."""
    assert detect_temporal_kind(("09:30", "23:59:59.5")) == "time"


def test_detect_temporal_kind_rejects_mixed_and_plain() -> None:
    """Mixed kinds or non-temporal strings yield None."""
    assert detect_temporal_kind(("2026-01-01", "10:00:00")) is None
    assert detect_temporal_kind(("hello", "world")) is None
    assert detect_temporal_kind(()) is None


def test_parse_temporal_columns_dispatches_pandas() -> None:
    """The dispatcher routes pandas frames to the pandas implementation."""
    frame = pd.DataFrame({"d": ["2026-01-01", "2026-06-11"]})
    parsed = parse_temporal_columns(frame, backend=Backend(pd.DataFrame))
    assert parsed["d"].dtype == "datetime64[ns]"


def test_parse_temporal_columns_dispatches_polars() -> None:
    """The dispatcher routes polars frames to the polars implementation."""
    frame = pl.DataFrame({"d": ["2026-01-01", "2026-06-11"]})
    parsed = parse_temporal_columns(frame, backend=Backend(pl.DataFrame))
    assert parsed.schema["d"] == pl.Date


def test_parse_temporal_columns_infers_backend() -> None:
    """Omitting *backend* infers it from the frame type."""
    parsed = parse_temporal_columns(pl.DataFrame({"d": ["2026-01-01"]}))
    assert parsed.schema["d"] == pl.Date
