"""Tests for ``mayutils.objects.dataframes.pandas.series``.

Covers the Series-level helpers on :class:`SeriesUtilsAccessor`:
``slice_interval`` (datetime/date index dispatch and the non-temporal error
path), ``ground`` (mean rebasing over a window, ``None`` passthrough) and the
always-raising ``save`` placeholder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    import pandas as pd
else:
    pd = pytest.importorskip("pandas")

from mayutils.objects.dataframes.pandas.series import SeriesUtilsAccessor
from mayutils.objects.datetime import Date, DateTime, Interval


def datetime_index(*days: int) -> pd.Index:
    """Return an object-dtype index of January-2024 timestamps.

    An object dtype keeps ``inferred_type`` as ``"datetime"`` so the accessor
    dispatches into its datetime branch.

    Parameters
    ----------
    days
        Day-of-month values for the timestamps.

    Returns
    -------
        An object-dtype index of timestamps.
    """
    return pd.Index([DateTime(2024, 1, day) for day in days], dtype=object)


def date_index(*days: int) -> pd.Index:
    """Return an object-dtype index of January-2024 dates.

    Parameters
    ----------
    days
        Day-of-month values for the dates.

    Returns
    -------
        An object-dtype index whose ``inferred_type`` is ``"date"``.
    """
    return pd.Index([Date(2024, 1, day) for day in days], dtype=object)


class TestInit:
    """Tests for :meth:`SeriesUtilsAccessor.__init__`."""

    def test_binds_series_by_reference(self) -> None:
        """The supplied series is stored verbatim."""
        series = pd.Series([1.0, 2.0, 3.0])
        assert SeriesUtilsAccessor(series=series).series is series


class TestSliceInterval:
    """Tests for :meth:`SeriesUtilsAccessor.slice_interval` — index-window slicing."""

    def test_datetime_index(self) -> None:
        """A datetime-indexed series keeps only entries inside the window."""
        series = pd.Series([1.0, 2.0, 3.0], index=datetime_index(1, 2, 3))
        window = Interval[DateTime](start=DateTime(2024, 1, 1), end=DateTime(2024, 1, 2))
        assert SeriesUtilsAccessor(series=series).slice_interval(window).tolist() == [1.0, 2.0]

    def test_date_index(self) -> None:
        """A date-indexed series slices via the date-narrowed interval."""
        series = pd.Series([1.0, 2.0, 3.0], index=date_index(1, 2, 3))
        window = Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 2))
        assert SeriesUtilsAccessor(series=series).slice_interval(window).tolist() == [1.0, 2.0]

    def test_full_window_keeps_all(self) -> None:
        """A window spanning the index keeps every entry."""
        series = pd.Series([1.0, 2.0, 3.0], index=datetime_index(1, 2, 3))
        window = Interval[DateTime](start=DateTime(2024, 1, 1), end=DateTime(2024, 1, 3))
        assert SeriesUtilsAccessor(series=series).slice_interval(window).tolist() == [1.0, 2.0, 3.0]

    def test_preserves_na(self) -> None:
        """NA entries inside the window are preserved by the label slice."""
        series = pd.Series([1.0, np.nan, 3.0], index=datetime_index(1, 2, 3))
        window = Interval[DateTime](start=DateTime(2024, 1, 1), end=DateTime(2024, 1, 2))
        result = SeriesUtilsAccessor(series=series).slice_interval(window)
        assert result.iloc[0] == 1.0
        assert bool(np.isnan(result.iloc[1]))

    def test_native_datetimeindex_slices(self) -> None:
        """A native ``DatetimeIndex`` (``inferred_type`` ``datetime64``) slices like a datetime index."""
        series = pd.Series([1.0, 2.0, 3.0], index=pd.date_range("2024-01-01", periods=3, freq="D"))
        window = Interval[DateTime](start=DateTime(2024, 1, 1), end=DateTime(2024, 1, 2))
        assert SeriesUtilsAccessor(series=series).slice_interval(window).tolist() == [1.0, 2.0]

    def test_non_temporal_index_raises(self) -> None:
        """An integer index cannot be interval-sliced and raises ``TypeError``."""
        series = pd.Series([1.0, 2.0, 3.0])
        window = Interval[DateTime](start=DateTime(2024, 1, 1), end=DateTime(2024, 1, 2))
        with pytest.raises(expected_exception=TypeError, match="must be datetime or date type"):
            SeriesUtilsAccessor(series=series).slice_interval(window)


class TestGround:
    """Tests for :meth:`SeriesUtilsAccessor.ground` — rebasing against a window mean."""

    def test_none_returns_series_unchanged(self) -> None:
        """A ``None`` interval returns the original series."""
        series = pd.Series([10.0, 20.0, 30.0], index=datetime_index(1, 2, 3))
        assert SeriesUtilsAccessor(series=series).ground(None).equals(series)

    def test_divides_by_window_mean(self) -> None:
        """The series is divided by the mean over the supplied window."""
        series = pd.Series([10.0, 20.0, 30.0], index=datetime_index(1, 2, 3))
        window = Interval[DateTime](start=DateTime(2024, 1, 1), end=DateTime(2024, 1, 2))
        result = SeriesUtilsAccessor(series=series).ground(window)
        assert np.allclose(result.to_numpy(), np.array([10.0, 20.0, 30.0]) / 15.0)

    def test_grounded_window_mean_is_one(self) -> None:
        """The grounded series averages to one over the reference window."""
        series = pd.Series([10.0, 20.0, 30.0], index=datetime_index(1, 2, 3))
        window = Interval[DateTime](start=DateTime(2024, 1, 1), end=DateTime(2024, 1, 2))
        result = SeriesUtilsAccessor(series=series).ground(window)
        assert np.isclose(result.iloc[0:2].mean(), 1.0)

    def test_integer_series_promoted_to_float(self) -> None:
        """Division promotes an integer series to floating point."""
        series = pd.Series([2, 4, 6], index=datetime_index(1, 2, 3))
        window = Interval[DateTime](start=DateTime(2024, 1, 1), end=DateTime(2024, 1, 1))
        result = SeriesUtilsAccessor(series=series).ground(window)
        assert result.dtype == np.dtype("float64")
        assert np.allclose(result.to_numpy(), [1.0, 2.0, 3.0])


class TestSave:
    """Tests for :meth:`SeriesUtilsAccessor.save` — the always-raising placeholder."""

    def test_always_raises(self) -> None:
        """Series persistence is unimplemented and unconditionally raises."""
        accessor = SeriesUtilsAccessor(series=pd.Series([1.0, 2.0]))
        with pytest.raises(expected_exception=NotImplementedError, match="Not implemented for series"):
            accessor.save(path="out.parquet")
