"""Tests for ``mayutils.objects.datetime``.

Requires the ``datetime`` (for ``pendulum``) and ``numerics`` (for
``numpy``) extras; the module is skipped at collection time otherwise.
"""

from __future__ import annotations

from datetime import date as stdlib_date
from datetime import datetime as stdlib_datetime
from datetime import time as stdlib_time

import pytest

np = pytest.importorskip("numpy")
pendulum = pytest.importorskip("pendulum")

from mayutils.objects.datetime import (  # noqa: E402
    UTC,
    Date,
    DateNumericMixin,
    DateTime,
    Interval,
    Intervals,
    Time,
    Tz,
    parse,
)


class TestDateConstructors:
    """Tests for :class:`Date` factory and conversion helpers."""

    def test_from_pendulum(self) -> None:
        """``from_pendulum`` wraps a pendulum ``Date``."""
        result = Date.from_pendulum(pendulum.date(2025, 1, 15))
        assert isinstance(result, Date)
        assert (result.year, result.month, result.day) == (2025, 1, 15)

    def test_from_base(self) -> None:
        """``from_base`` wraps a stdlib ``date``."""
        result = Date.from_base(stdlib_date(2025, 1, 15))
        assert isinstance(result, Date)
        assert (result.year, result.month, result.day) == (2025, 1, 15)

    def test_as_pendulum_returns_plain_pendulum(self) -> None:
        """``as_pendulum`` is a plain :class:`pendulum.Date`, not our subclass."""
        result = Date(2025, 1, 15).as_pendulum
        assert type(result) is pendulum.Date

    def test_as_base_returns_stdlib(self) -> None:
        """``as_base`` is a plain :class:`datetime.date`."""
        result = Date(2025, 1, 15).as_base
        assert type(result) is stdlib_date
        assert result == stdlib_date(2025, 1, 15)

    def test_parse_from_string(self) -> None:
        """String parsing produces a :class:`Date` (not a :class:`DateTime`)."""
        result = Date.parse("2025-01-15")
        assert type(result) is Date
        assert (result.year, result.month, result.day) == (2025, 1, 15)

    def test_parse_invalid_raises(self) -> None:
        """Unparseable input raises :class:`TypeError` / :class:`ValueError`."""
        with pytest.raises((TypeError, ValueError)):
            Date.parse("not-a-date")

    def test_coerce_from_string(self) -> None:
        """Strings are parsed via :meth:`Date.parse`."""
        assert Date.coerce("2025-01-15") == Date(2025, 1, 15)

    def test_coerce_from_datetime_narrows(self) -> None:
        """A :class:`DateTime` is narrowed to its :class:`Date` part."""
        result = Date.coerce(DateTime(2025, 1, 15, 10, 30))
        assert type(result) is Date
        assert result == Date(2025, 1, 15)

    def test_coerce_from_pendulum_date(self) -> None:
        """A pendulum ``Date`` round-trips through :meth:`Date.from_pendulum`."""
        result = Date.coerce(pendulum.date(2025, 1, 15))
        assert type(result) is Date

    def test_coerce_from_stdlib_date(self) -> None:
        """A stdlib ``date`` round-trips through :meth:`Date.from_base`."""
        result = Date.coerce(stdlib_date(2025, 1, 15))
        assert type(result) is Date

    def test_to_datetime_midnight_utc(self) -> None:
        """``to_datetime`` defaults to midnight in UTC."""
        dt = Date(2025, 1, 15).to_datetime()
        assert dt == DateTime.create(year=2025, month=1, day=15, tz=UTC)


class TestTimeConstructors:
    """Tests for :class:`Time` factory and conversion helpers."""

    def test_from_pendulum(self) -> None:
        """``from_pendulum`` wraps a pendulum ``Time``."""
        result = Time.from_pendulum(pendulum.time(10, 30))
        assert type(result) is Time
        assert (result.hour, result.minute) == (10, 30)

    def test_from_base(self) -> None:
        """``from_base`` wraps a stdlib ``time``."""
        result = Time.from_base(stdlib_time(10, 30))
        assert type(result) is Time

    def test_as_base_returns_stdlib(self) -> None:
        """``as_base`` is a plain :class:`datetime.time`."""
        result = Time(10, 30).as_base
        assert type(result) is stdlib_time
        assert result == stdlib_time(10, 30)

    def test_as_pendulum_returns_plain_pendulum(self) -> None:
        """``as_pendulum`` is a plain :class:`pendulum.Time`."""
        result = Time(10, 30).as_pendulum
        assert type(result) is pendulum.Time

    def test_on_combines_with_date(self) -> None:
        """``on(date)`` produces a :class:`DateTime` combining the two."""
        result = Time(10, 30).on(Date(2025, 1, 15))
        assert type(result) is DateTime
        assert (result.year, result.month, result.day, result.hour, result.minute) == (2025, 1, 15, 10, 30)

    def test_fractional_completion_midnight(self) -> None:
        """Midnight is fractional completion 0."""
        assert Time(0, 0, 0).fractional_completion == 0.0

    def test_fractional_completion_noon(self) -> None:
        """Noon is exactly half the day."""
        assert np.isclose(Time(12, 0, 0).fractional_completion, 0.5)


class TestDateTimeConstructors:
    """Tests for :class:`DateTime` factory and conversion helpers."""

    def test_from_pendulum(self) -> None:
        """``from_pendulum`` wraps a pendulum ``DateTime`` preserving tzinfo."""
        source = pendulum.datetime(2025, 1, 15, 10, 30, tz="UTC")
        result = DateTime.from_pendulum(source)
        assert type(result) is DateTime
        assert result == source

    def test_from_base(self) -> None:
        """``from_base`` wraps a stdlib ``datetime``."""
        source = stdlib_datetime(2025, 1, 15, 10, 30, tzinfo=pendulum.timezone("UTC"))
        result = DateTime.from_base(source)
        assert type(result) is DateTime
        assert (result.year, result.hour, result.minute) == (2025, 10, 30)

    def test_as_base_returns_stdlib(self) -> None:
        """``as_base`` is a plain :class:`datetime.datetime`."""
        result = DateTime(2025, 1, 15, 10, 30).as_base
        assert type(result) is stdlib_datetime

    def test_as_pendulum_returns_plain_pendulum(self) -> None:
        """``as_pendulum`` is a plain :class:`pendulum.DateTime`."""
        result = DateTime(2025, 1, 15, 10, 30).as_pendulum
        assert type(result) is pendulum.DateTime

    def test_parse_string_with_utc(self) -> None:
        """Naked date strings parse to midnight UTC."""
        result = DateTime.parse("2025-01-15")
        assert result == DateTime.create(year=2025, month=1, day=15, tz=UTC)

    def test_date_returns_date_part(self) -> None:
        """``DateTime.date()`` produces a :class:`Date` of the same day."""
        result = DateTime(2025, 1, 15, 10, 30).date()
        assert type(result) is Date
        assert result == Date(2025, 1, 15)

    def test_time_returns_time_part(self) -> None:
        """``DateTime.time()`` produces a :class:`Time` of the same clock."""
        result = DateTime(2025, 1, 15, 10, 30).time()
        assert type(result) is Time

    def test_without_timezone(self) -> None:
        """``without_timezone`` constructs a naive :class:`DateTime`."""
        naive = DateTime.without_timezone(year=2025, month=1, day=15, hour=10)
        assert naive.tzinfo is None

    def test_today_midnight(self) -> None:
        """``today`` returns a tz-aware datetime anchored at start of day."""
        today = DateTime.today(tz=UTC)
        assert (today.hour, today.minute, today.second, today.microsecond) == (0, 0, 0, 0)

    def test_tomorrow_is_next_day(self) -> None:
        """``tomorrow`` differs from ``today`` by exactly one day."""
        assert (DateTime.tomorrow(tz=UTC) - DateTime.today(tz=UTC)).in_days() == 1

    def test_yesterday_is_previous_day(self) -> None:
        """``yesterday`` differs from ``today`` by exactly one day."""
        assert (DateTime.today(tz=UTC) - DateTime.yesterday(tz=UTC)).in_days() == 1


class TestDateNumericMixin:
    """Tests for helpers shared by :class:`Date` and :class:`DateTime`."""

    def test_is_weekend_on_saturday(self) -> None:
        """A Saturday is recognised as a weekend day."""
        assert Date(2025, 1, 18).is_weekend() is True

    def test_is_weekend_on_sunday(self) -> None:
        """A Sunday is recognised as a weekend day."""
        assert Date(2025, 1, 19).is_weekend() is True

    def test_is_weekend_on_weekday(self) -> None:
        """A Wednesday is not a weekend day."""
        assert Date(2025, 1, 15).is_weekend() is False

    def test_to_month_long(self) -> None:
        """Long form returns the full English month name."""
        assert Date(2025, 1, 15).to_month() == "January"

    def test_to_month_short(self) -> None:
        """Short form returns the abbreviated month name."""
        assert Date(2025, 1, 15).to_month(long=False) == "Jan"

    def test_to_numpy_date(self) -> None:
        """``to_numpy`` returns a ``numpy.datetime64`` from a :class:`Date`."""
        result = Date(2025, 1, 15).to_numpy()
        assert isinstance(result, np.datetime64)

    def test_mixin_is_public(self) -> None:
        """The mixin class is importable from the package root."""
        assert issubclass(Date, DateNumericMixin)
        assert issubclass(DateTime, DateNumericMixin)


class TestDateTimeHierarchy:
    """Tests for the cross-class type hierarchy after the flatten refactor."""

    def test_datetime_not_subclass_of_date(self) -> None:
        """Our ``DateTime`` is no longer a subclass of our ``Date``."""
        assert not issubclass(DateTime, Date)

    def test_datetime_still_subclass_of_pendulum_date(self) -> None:
        """Pendulum's own hierarchy still treats a ``DateTime`` as a date."""
        assert isinstance(DateTime(2025, 1, 15), pendulum.Date)


class TestTz:
    """Tests for :class:`Tz` — pendulum timezone wrapper."""

    def test_utc_is_tz_instance(self) -> None:
        """The module-level ``UTC`` is a :class:`Tz`."""
        assert isinstance(UTC, Tz)

    def test_spawn_from_name(self) -> None:
        """``Tz.spawn`` builds a ``Tz`` from an IANA name."""
        assert isinstance(Tz.spawn(name="Europe/London"), Tz)

    def test_spawn_utc_normalises_casing(self) -> None:
        """Any casing of ``"utc"`` maps to the canonical ``UTC`` zone."""
        assert str(Tz.spawn(name="utc")) == "UTC"

    def test_list_contains_utc(self) -> None:
        """The IANA zone list includes ``UTC``."""
        assert "UTC" in Tz.list()


class TestParse:
    """Tests for the module-level :func:`parse` dispatcher."""

    def test_parses_iso_date(self) -> None:
        """Date-only ISO strings return a ``DateTime`` at midnight UTC."""
        result = parse("2025-01-15")
        assert isinstance(result, DateTime)

    def test_parses_iso_datetime(self) -> None:
        """A full ISO datetime string returns a ``DateTime``."""
        result = parse("2025-01-15T10:30:00")
        assert isinstance(result, DateTime)

    def test_passes_through_non_string(self) -> None:
        """Pre-parsed datetime values round-trip to an equal :class:`DateTime`."""
        dt = DateTime(2025, 1, 15, 10, 30)
        result = parse(dt)
        assert isinstance(result, DateTime)
        assert result == dt


class TestInterval:
    """Tests for :class:`Interval` — generic interval over Date/DateTime."""

    def test_strict_init_with_dates(self) -> None:
        """The default constructor accepts two :class:`Date` endpoints."""
        iv: Interval[Date] = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 31))
        assert iv.start == Date(2025, 1, 1)
        assert iv.end == Date(2025, 1, 31)
        assert type(iv.start) is Date

    def test_strict_init_with_datetimes(self) -> None:
        """The default constructor accepts two :class:`DateTime` endpoints."""
        iv = Interval(start=DateTime(2025, 1, 1), end=DateTime(2025, 1, 31))
        assert type(iv.start) is DateTime

    def test_coercing_date_from_strings(self) -> None:
        """``coercing_date`` parses string endpoints into :class:`Date`."""
        iv = Interval.coercing_date(start="2025-01-01", end="2025-01-31")
        assert type(iv.start) is Date
        assert type(iv.end) is Date

    def test_coercing_datetime_from_strings(self) -> None:
        """``coercing_datetime`` parses string endpoints into :class:`DateTime`."""
        iv = Interval.coercing_datetime(start="2025-01-01", end="2025-01-31")
        assert type(iv.start) is DateTime
        assert type(iv.end) is DateTime

    def test_coercing_datetime_with_fmt(self) -> None:
        """``fmt`` is forwarded to :meth:`DateTime.parse` for custom formats."""
        iv = Interval.coercing_datetime(start="15/01/2025", end="31/01/2025", fmt="DD/MM/YYYY")
        assert iv.start == DateTime.create(year=2025, month=1, day=15, tz=UTC)

    def test_promote_pendulum_date(self) -> None:
        """A raw pendulum ``Date`` is promoted to our ``Date``."""
        result = Interval[Date].promote_pendulum(pendulum.date(2025, 1, 15))
        assert type(result) is Date

    def test_promote_pendulum_datetime(self) -> None:
        """A raw pendulum ``DateTime`` is promoted to our ``DateTime``."""
        result = Interval[DateTime].promote_pendulum(pendulum.datetime(2025, 1, 15))
        assert type(result) is DateTime

    def test_as_pendulum_returns_plain_pendulum(self) -> None:
        """``as_pendulum`` returns a plain :class:`pendulum.Interval`."""
        iv = Interval.coercing_date(start="2025-01-01", end="2025-01-31")
        assert type(iv.as_pendulum) is pendulum.Interval

    def test_as_slice_uses_stdlib(self) -> None:
        """``as_slice`` exposes stdlib start/stop bounds for pandas indexing."""
        iv = Interval.coercing_date(start="2025-01-01", end="2025-01-31")
        sl = iv.as_slice
        assert sl.start == stdlib_date(2025, 1, 1)
        assert sl.stop == stdlib_date(2025, 1, 31)

    def test_count_weekdays_january_2025(self) -> None:
        """January 2025 has 23 weekdays and 8 weekend days."""
        iv = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 31))
        weekdays, weekends = iv.count_weekdays()
        assert (weekdays, weekends) == (23, 8)


class TestIntervals:
    """Tests for :class:`Intervals` — ordered container of intervals."""

    def test_empty_length(self) -> None:
        """An empty ``Intervals`` has length zero."""
        assert len(Intervals[Date]()) == 0

    def test_sorts_on_construction(self) -> None:
        """Intervals are sorted by ``(start, end)`` on construction."""
        later = Interval(start=Date(2025, 2, 1), end=Date(2025, 2, 28))
        earlier = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 31))
        ordered = Intervals(later, earlier)
        assert list(ordered) == [earlier, later]

    def test_slicing_returns_intervals(self) -> None:
        """Slicing returns a new ``Intervals`` container."""
        a = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 31))
        b = Interval(start=Date(2025, 2, 1), end=Date(2025, 2, 28))
        c = Interval(start=Date(2025, 3, 1), end=Date(2025, 3, 31))
        result = Intervals(a, b, c)[1:]
        assert isinstance(result, Intervals)
        assert list(result) == [b, c]

    def test_integer_index_returns_interval(self) -> None:
        """Integer indexing returns a single :class:`Interval`."""
        a = Interval(start=Date(2025, 1, 1), end=Date(2025, 1, 31))
        assert Intervals(a)[0] is a
