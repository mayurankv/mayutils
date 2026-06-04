"""Tests for ``mayutils.objects.datetime.interval``.

Requires the ``datetime`` (for ``pendulum``) and ``numerics`` (for ``numpy``)
extras; the module is skipped at collection time otherwise.

Basic construction/coercion of :class:`Interval` and the container behaviour of
:class:`Intervals` are already exercised in ``tests/objects/test_datetime.py``;
this module concentrates on containment, duration, conversion, ordering edge
cases, deep copying and the :func:`get_intervals` factory.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date as stdlib_date
from itertools import pairwise

import pytest

np = pytest.importorskip("numpy")
pendulum = pytest.importorskip("pendulum")

from mayutils.objects.datetime import (  # noqa: E402
    Date,
    DateTime,
    Interval,
    Intervals,
)
from mayutils.objects.datetime.interval import get_intervals  # noqa: E402
from mayutils.objects.datetime.traveller import traveller  # noqa: E402


class TestOrdering:
    """Tests for endpoint ordering and the ``absolute`` flag."""

    def test_forward_interval_not_inverted(self) -> None:
        """A start-before-end interval is stored without inversion."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 31))
        assert iv.inverted is False
        assert iv.absolute is False
        assert iv.start <= iv.end

    def test_absolute_swaps_reversed_endpoints(self) -> None:
        """With ``absolute=True`` a reversed pair is swapped to be non-negative."""
        iv = Interval(start=Date(2025, 1, 31), end=Date(2025, 1, 1), absolute=True)
        assert iv.absolute is True
        assert iv.inverted is True
        assert iv.start == Date(2025, 1, 1)
        assert iv.end == Date(2025, 1, 31)
        assert iv.days == 30  # noqa: PLR2004

    def test_reversed_without_absolute_is_negative(self) -> None:
        """Without ``absolute`` a reversed pair keeps a negative span."""
        iv = Interval(start=Date(2025, 1, 31), end=Date(2025, 1, 1))
        assert iv.absolute is False
        assert iv.days == -30  # noqa: PLR2004
        assert iv.start == Date(2025, 1, 31)
        assert iv.end == Date(2025, 1, 1)


class TestContainment:
    """Tests for membership and overlap of :class:`Interval`."""

    def test_contains_interior_point(self) -> None:
        """A date strictly inside the span is contained."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 31))
        assert Date(2025, 1, 15) in iv

    @pytest.mark.parametrize("day", [1, 31])
    def test_contains_boundary(self, day: int) -> None:
        """Both inclusive endpoints are members of the closed interval."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 31))
        assert Date(2025, 1, day) in iv

    @pytest.mark.parametrize(
        "point",
        [Date(2024, 12, 31), Date(2025, 2, 1)],
    )
    def test_excludes_points_outside(self, point: Date) -> None:
        """Dates before the start or after the end are not contained."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 31))
        assert point not in iv


class TestDuration:
    """Tests for length/duration accessors inherited from pendulum."""

    def test_days_inclusive_span(self) -> None:
        """``days`` reports the calendar-day span between endpoints."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 31))
        assert iv.days == 30  # noqa: PLR2004

    def test_in_weeks(self) -> None:
        """A 30-day span rounds down to four whole weeks."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 31))
        assert iv.in_weeks() == 4  # noqa: PLR2004

    def test_half_day_in_hours(self) -> None:
        """A noon-to-midnight datetime interval is twelve hours long."""
        iv = Interval.coercing_datetime(start="2025-01-01T00:00:00", end="2025-01-01T12:00:00")
        assert iv.in_hours() == 12  # noqa: PLR2004

    def test_half_day_total_seconds(self) -> None:
        """``total_seconds`` of a half day is 43200 seconds."""
        iv = Interval.coercing_datetime(start="2025-01-01T00:00:00", end="2025-01-01T12:00:00")
        assert np.isclose(iv.total_seconds(), 43200.0)


class TestZeroLength:
    """Tests for degenerate, zero-length intervals."""

    def test_zero_length_days(self) -> None:
        """An interval with equal endpoints spans zero days."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 1))
        assert iv.days == 0

    def test_zero_length_contains_its_point(self) -> None:
        """The single shared endpoint is contained in the interval."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 1))
        assert Date(2025, 1, 1) in iv

    def test_zero_length_counts_single_day(self) -> None:
        """Day iteration is inclusive, so a zero-length span counts one day."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 1))
        weekdays, weekends = iv.count_weekdays()
        assert (weekdays, weekends) == (1, 0)


class TestIteration:
    """Tests for day-by-day iteration via ``range``."""

    def test_range_is_inclusive(self) -> None:
        """A one-week span yields eight inclusive days."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 8))
        days = list(iv.range(unit="days"))
        assert len(days) == 8  # noqa: PLR2004
        assert days[0] == Date(2025, 1, 1)
        assert days[-1] == Date(2025, 1, 8)

    def test_count_weekdays_one_week(self) -> None:
        """A Wed-to-Tue week has five weekdays and two weekend days."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 7))
        assert iv.count_weekdays() == (5, 2)

    def test_weekdays_and_weekends_properties_agree(self) -> None:
        """The named properties match the tuple from :meth:`count_weekdays`."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 7))
        weekdays, weekends = iv.count_weekdays()
        assert iv.weekdays == weekdays
        assert iv.weekends == weekends


class TestConversions:
    """Tests for date/datetime resolution conversions."""

    def test_to_date_interval_from_datetime(self) -> None:
        """Datetime endpoints are truncated to their calendar date."""
        iv = Interval.coercing_datetime(start="2025-01-01T12:00:00", end="2025-01-31T12:00:00")
        result = iv.to_date_interval()
        assert type(result.start) is Date
        assert type(result.end) is Date
        assert result.days == 30  # noqa: PLR2004

    def test_to_date_interval_from_date_is_idempotent(self) -> None:
        """Date endpoints survive a date projection unchanged."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 31))
        result = iv.to_date_interval()
        assert type(result.start) is Date
        assert result.start == Date(2025, 1, 1)
        assert result.end == Date(2025, 1, 31)

    def test_to_datetime_interval_from_date(self) -> None:
        """Date endpoints are promoted to midnight datetimes."""
        iv = Interval.coercing_date(start="2025-01-01", end="2025-01-31")
        result = iv.to_datetime_interval()
        assert type(result.start) is DateTime
        assert type(result.end) is DateTime
        assert result.days == 30  # noqa: PLR2004

    def test_to_datetime_interval_from_datetime_is_idempotent(self) -> None:
        """Datetime endpoints survive a datetime lift unchanged."""
        iv = Interval.coercing_datetime(start="2025-01-01T06:00:00", end="2025-01-02T06:00:00")
        result = iv.to_datetime_interval()
        assert type(result.start) is DateTime
        assert result.in_hours() == 24  # noqa: PLR2004


class TestAsSlice:
    """Tests for the :attr:`Interval.as_slice` pandas-indexing helper."""

    def test_forward_slice_bounds(self) -> None:
        """A forward interval yields ``start``-then-``stop`` stdlib bounds."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 31))
        sl = iv.as_slice
        assert sl.start == stdlib_date(2025, 1, 1)
        assert sl.stop == stdlib_date(2025, 1, 31)

    def test_inverted_slice_bounds_are_swapped(self) -> None:
        """An inverted interval swaps the slice bounds back to storage order."""
        iv = Interval(start=Date(2025, 1, 31), end=Date(2025, 1, 1), absolute=True)
        sl = iv.as_slice
        assert sl.start == stdlib_date(2025, 1, 31)
        assert sl.stop == stdlib_date(2025, 1, 1)


class TestDeepCopy:
    """Tests for deep-copy semantics."""

    def test_deepcopy_is_independent_copy(self) -> None:
        """A deep copy is equal but holds distinct endpoint objects."""
        original = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 31))
        clone = deepcopy(original)
        assert clone.start == original.start
        assert clone.start is not original.start
        assert clone.days == original.days

    def test_deepcopy_preserves_absolute(self) -> None:
        """The absolute flag, endpoints and span are carried over to the copy."""
        original = Interval(start=Date(2025, 1, 31), end=Date(2025, 1, 1), absolute=True)
        clone = deepcopy(original)
        assert clone.absolute is True
        assert clone.start == original.start
        assert clone.end == original.end
        assert clone.days == original.days

    def test_deepcopy_preserves_inverted_flag(self) -> None:
        """Deep copying an inverted interval preserves ``inverted`` and slice order."""
        original = Interval(start=Date(2025, 1, 31), end=Date(2025, 1, 1), absolute=True)
        assert original.inverted is True
        clone = deepcopy(original)
        assert clone.inverted is True
        assert clone.as_slice == original.as_slice


class TestStr:
    """Tests for the human-readable ``__str__`` rendering."""

    def test_str_date_interval(self) -> None:
        """A date interval renders as ``"start to end"``."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 31))
        assert str(iv) == "2025-01-01 to 2025-01-31"


class TestErrorPaths:
    """Tests for invalid construction inputs."""

    def test_coercing_date_unparseable_raises(self) -> None:
        """An unparseable string endpoint surfaces a parse error."""
        with pytest.raises(expected_exception=(TypeError, ValueError)):
            Interval.coercing_date(start="not-a-date", end="2025-01-31")

    def test_coercing_datetime_unparseable_raises(self) -> None:
        """An unparseable datetime endpoint surfaces a parse error."""
        with pytest.raises(expected_exception=(TypeError, ValueError)):
            Interval.coercing_datetime(start="2025-01-01", end="nonsense")


class TestGetIntervals:
    """Tests for the :func:`get_intervals` rolling-window factory."""

    def test_produces_requested_count(self) -> None:
        """The factory returns exactly ``num_periods`` intervals."""
        result = get_intervals(DateTime(2024, 7, 1), num_periods=3)
        assert len(result) == 3  # noqa: PLR2004

    def test_returns_sorted_intervals_container(self) -> None:
        """The result is an :class:`Intervals` sorted earliest-first."""
        result = get_intervals(DateTime(2024, 7, 1), num_periods=3)
        assert isinstance(result, Intervals)
        starts = [iv.start for iv in result]
        assert starts == sorted(starts)

    def test_windows_are_contiguous_months(self) -> None:
        """Consecutive intervals tile months end-to-start without gaps."""
        result = list(get_intervals(DateTime(2024, 7, 1), num_periods=3))
        for earlier, later in pairwise(result):
            assert earlier.end == later.start

    def test_last_window_ends_at_anchor(self) -> None:
        """The most recent interval ends on the anchor instant."""
        anchor = DateTime(2024, 7, 1)
        result = list(get_intervals(anchor, num_periods=3))
        assert result[-1].end == anchor

    def test_first_window_steps_back_num_periods_months(self) -> None:
        """The earliest interval starts ``num_periods`` months before the anchor."""
        anchor = DateTime(2024, 7, 1)
        result = list(get_intervals(anchor, num_periods=3))
        assert result[0].start == anchor.subtract(months=3)

    def test_day_override_anchors_boundaries(self) -> None:
        """An explicit ``day`` anchors every interval boundary on that day."""
        result = list(get_intervals(DateTime(2024, 7, 10), num_periods=2, day=15))
        for iv in result:
            assert iv.start.day == 15  # noqa: PLR2004
            assert iv.end.day == 15  # noqa: PLR2004

    def test_absolute_interval_flag_forwarded(self) -> None:
        """``absolute_interval`` is forwarded to each generated interval."""
        result = get_intervals(DateTime(2024, 7, 1), num_periods=2, absolute_interval=True)
        assert all(iv.absolute for iv in result)

    def test_default_anchor_is_today(self) -> None:
        """A ``None`` anchor falls back to ``DateTime.today`` deterministically."""
        with traveller.travel_to(DateTime.parse("2024-07-01T00:00:00Z"), freeze=True):
            result = list(get_intervals(None, num_periods=2))
        assert result[-1].end.date() == Date(2024, 7, 1)
