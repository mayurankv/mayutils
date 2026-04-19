"""Pendulum-backed date, time and datetime wrappers with a unified parsing helper.

This module layers thin subclasses on top of :mod:`pendulum`'s concrete
:class:`~pendulum.Date`, :class:`~pendulum.Time` and :class:`~pendulum.DateTime`
types so the rest of ``mayutils`` can exchange timezone-aware values that
round-trip cleanly between pendulum, the standard library and NumPy. The
subclasses share numeric/calendar helpers via :class:`DateNumericMixin`, expose
``from_pendulum`` / ``from_base`` / ``as_pendulum`` / ``as_base`` bridges for
interoperation, and add convenience constructors such as
:meth:`DateTime.today`, :meth:`DateTime.tomorrow`, :meth:`DateTime.yesterday`,
:meth:`DateTime.local` and :meth:`DateTime.without_timezone`. The module-level
:func:`parse` dispatches a permissive input (string or already-parsed pendulum
value) to the correct subclass, and a SQLite adapter is registered so
:class:`DateTime` instances serialise to ISO-formatted strings when bound to
parameters.
"""

from __future__ import annotations

from datetime import date as BaseDate  # noqa: N812
from datetime import datetime as BaseDateTime  # noqa: N812
from datetime import time as BaseTime  # noqa: N812
from datetime import tzinfo as BaseTzinfo  # noqa: N812
from sqlite3 import register_adapter
from typing import TYPE_CHECKING, Self

import numpy as np

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from pendulum import (
        Date as PendulumDate,
    )
    from pendulum import (
        DateTime as PendulumDateTime,
    )
    from pendulum import (
        FixedTimezone,
        local_timezone,
    )
    from pendulum import (
        Time as PendulumTime,
    )
    from pendulum import (
        parse as pendulum_parse,
    )

from mayutils.objects.datetime.constants import DAY_SECONDS, FORMATTER
from mayutils.objects.datetime.timezone import UTC, Tz

if TYPE_CHECKING:
    from pendulum import Duration


class DateNumericMixin(PendulumDate):
    """Shared calendar helpers mixed into :class:`Date` and :class:`DateTime`.

    The mixin inherits from :class:`pendulum.Date` purely to satisfy static type
    checkers (so references to ``day_of_week``, ``format`` and ``year`` resolve
    against pendulum's surface). It is not intended to be instantiated directly;
    concrete subclasses supply the actual construction semantics while reusing
    the helpers below for weekend detection, human-readable month names and
    NumPy interop.
    """

    def is_weekend(
        self,
    ) -> bool:
        """Check whether the current date falls on a Saturday or Sunday.

        Returns
        -------
        bool
            ``True`` when pendulum's ``day_of_week`` (ISO weekday minus one) is
            either ``5`` (Saturday) or ``6`` (Sunday), otherwise ``False``.
        """
        return self.day_of_week in (5, 6)

    def to_month(
        self,
        *,
        long: bool = True,
    ) -> str:
        """Render the month as a locale-aware human-readable name.

        Parameters
        ----------
        long : bool, default True
            When ``True`` the full month name is returned using pendulum's
            ``MMMM`` token (e.g. ``"January"``); when ``False`` the abbreviated
            three-letter form is returned via ``MMM`` (e.g. ``"Jan"``).

        Returns
        -------
        str
            Month name formatted in the selected long or short style.
        """
        return self.format(fmt="MMMM" if long else "MMM")

    def to_numpy(
        self,
    ) -> np.datetime64:
        """Convert the value to a :class:`numpy.datetime64` scalar.

        Returns
        -------
        numpy.datetime64
            NumPy scalar with precision inferred from this instance, suitable
            for placement inside NumPy arrays or pandas datetime columns.
        """
        return np.datetime64(self)


class Time(PendulumTime):
    """Pendulum :class:`~pendulum.Time` subclass with date-combination helpers.

    Extends pendulum's time type with ergonomic constructors for converting
    from pendulum or the standard library, lossless bridges back to those
    representations, string parsing via the module-level :func:`parse`, and
    helpers for placing the time on a specific date (:meth:`on`), today
    (:meth:`today`) or expressing it as a fraction of the day
    (:attr:`fractional_completion`).
    """

    @classmethod
    def from_pendulum(
        cls,
        base: PendulumTime,
        /,
    ) -> Time:
        """Wrap a pendulum :class:`~pendulum.Time` in this subclass.

        Parameters
        ----------
        base : pendulum.Time
            Source pendulum time whose hour, minute, second, microsecond and
            ``tzinfo`` are copied verbatim into the new instance.

        Returns
        -------
        Time
            New :class:`Time` mirroring ``base`` so mayutils helpers become
            available on the value.
        """
        return cls(
            hour=base.hour,
            minute=base.minute,
            second=base.second,
            microsecond=base.microsecond,
            tzinfo=base.tzinfo,
        )

    @classmethod
    def from_base(
        cls,
        base: BaseTime,
        /,
        *,
        tz: str | Tz | FixedTimezone | BaseTzinfo | None = UTC,
    ) -> Time:
        """Construct a :class:`Time` from a stdlib :class:`datetime.time`.

        Parameters
        ----------
        base : datetime.time
            Standard-library time value to convert; its clock components are
            preserved while timezone information is (re)applied from ``tz``.
        tz : str, Tz, FixedTimezone, BaseTzinfo or None, default UTC
            Timezone to attach to the result. Any value accepted by
            :meth:`pendulum.Time.instance` is valid; pass ``None`` to produce
            a naive time.

        Returns
        -------
        Time
            mayutils :class:`Time` equivalent of ``base`` localised to ``tz``.
        """
        return cls.instance(
            t=base,
            tz=tz,
        )

    @property
    def as_pendulum(
        self,
    ) -> PendulumTime:
        """Expose the value as a plain pendulum :class:`~pendulum.Time`.

        Returns
        -------
        pendulum.Time
            Fresh pendulum time with identical components, for passing to APIs
            that perform ``type(x) is pendulum.Time`` style checks.
        """
        return PendulumTime(
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microsecond,
            tzinfo=self.tzinfo,
        )

    @property
    def as_base(
        self,
    ) -> BaseTime:
        """Expose the value as a stdlib :class:`datetime.time`.

        Returns
        -------
        datetime.time
            Standard-library time with matching clock components. Note that
            ``tzinfo`` is intentionally dropped because the stdlib constructor
            used here does not propagate it.
        """
        return BaseTime(
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microsecond,
        )

    @classmethod
    def parse(
        cls,
        dt: str,
        /,
    ) -> Time:
        """Parse a string representation into a :class:`Time`.

        Parameters
        ----------
        dt : str
            ISO-8601 or pendulum-compatible textual representation of a time
            (or datetime, in which case the time portion is extracted).

        Returns
        -------
        Time
            Parsed time value.

        Raises
        ------
        ValueError
            If :func:`parse` returned a :class:`Date` or other value that
            cannot be reduced to a time component.
        """
        output = parse(dt)

        if isinstance(output, cls):
            return output

        if isinstance(output, DateTime):
            return output.time()

        msg = "Could not parse to time"
        raise ValueError(msg)

    @staticmethod
    def now() -> Time:
        """Return the current wall-clock time in the system's default timezone.

        Returns
        -------
        Time
            Time portion of :meth:`DateTime.now`, using pendulum's default
            timezone resolution.
        """
        return DateTime.now().time()

    def today(
        self,
    ) -> DateTime:
        """Place this time on today's date in its own timezone.

        Returns
        -------
        DateTime
            Datetime whose date portion is today (resolved in the current
            instance's ``tzinfo``) and whose clock components mirror ``self``.
        """
        return DateTime.now(
            tz=self.tzinfo,
        ).at(
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microsecond,
        )

    def on(
        self,
        date: Date,
        /,
    ) -> DateTime:
        """Combine this time with an explicit date into a :class:`DateTime`.

        Parameters
        ----------
        date : Date
            Calendar date supplying the year, month and day portions of the
            resulting datetime.

        Returns
        -------
        DateTime
            Datetime with the date components taken from ``date`` and the
            clock/tz components taken from ``self``.
        """
        return DateTime(
            year=date.year,
            month=date.month,
            day=date.day,
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microsecond,
            tzinfo=self.tzinfo,
        )

    @property
    def fractional_completion(
        self,
    ) -> float:
        """Fraction of the day that has elapsed at this time.

        Returns
        -------
        float
            Value in ``[0.0, 1.0)`` computed as ``seconds since midnight /
            seconds in a day``, where ``0.0`` is midnight and values approach
            ``1.0`` as the end of the civil day is reached.
        """
        return (self.hour * 3600 + self.minute * 60 + self.second + self.microsecond * 1e-6) / DAY_SECONDS


class Date(DateNumericMixin):
    """Pendulum :class:`~pendulum.Date` subclass with parsing and interop helpers.

    Augments pendulum's calendar date with consistent conversion helpers to and
    from pendulum/stdlib equivalents, permissive :meth:`parse` and
    :meth:`coerce` factories, and a :meth:`to_datetime` lift that anchors the
    date at midnight in a chosen timezone.
    """

    @classmethod
    def from_pendulum(
        cls,
        base: PendulumDate,
        /,
    ) -> Self:
        """Wrap a pendulum :class:`~pendulum.Date` in this subclass.

        Parameters
        ----------
        base : pendulum.Date
            Source pendulum date whose year, month and day are copied into the
            new instance.

        Returns
        -------
        Self
            mayutils :class:`Date` with calendar components matching ``base``.
        """
        return cls(
            year=base.year,
            month=base.month,
            day=base.day,
        )

    @classmethod
    def from_base(
        cls,
        base: BaseDate,
        /,
    ) -> Self:
        """Construct a :class:`Date` from a stdlib :class:`datetime.date`.

        Parameters
        ----------
        base : datetime.date
            Standard-library date whose calendar components are lifted into a
            new instance of this class.

        Returns
        -------
        Self
            mayutils :class:`Date` equivalent of ``base``.
        """
        return cls(
            year=base.year,
            month=base.month,
            day=base.day,
        )

    @property
    def as_pendulum(
        self,
    ) -> PendulumDate:
        """Expose the value as a plain pendulum :class:`~pendulum.Date`.

        Returns
        -------
        pendulum.Date
            Pendulum date with the same calendar components, suitable for
            handing to APIs that type-check against pendulum's own class.
        """
        return PendulumDate(
            year=self.year,
            month=self.month,
            day=self.day,
        )

    @property
    def as_base(
        self,
    ) -> BaseDate:
        """Expose the value as a stdlib :class:`datetime.date`.

        Returns
        -------
        datetime.date
            Standard-library date with matching year/month/day.
        """
        return BaseDate(
            year=self.year,
            month=self.month,
            day=self.day,
        )

    @classmethod
    def parse(
        cls,
        dt: str,
        /,
    ) -> Date:
        """Parse a textual date (or datetime) into a :class:`Date`.

        Parameters
        ----------
        dt : str
            ISO-8601 or pendulum-compatible date/datetime string. Datetime
            inputs are accepted and reduced to their date portion.

        Returns
        -------
        Date
            Parsed date value.

        Raises
        ------
        TypeError
            If :func:`parse` yielded a value that is neither a :class:`Date`
            nor convertible from a :class:`DateTime`.
        """
        output = parse(dt)

        if isinstance(output, DateTime):
            return output.date()

        if isinstance(output, cls):
            return output

        msg = "Could not parse to date"
        raise TypeError(msg)

    @classmethod
    def coerce(
        cls,
        dt: str | Date | PendulumDate | BaseDate,
        /,
        *,
        fmt: str | None = None,
    ) -> Date:
        """Coerce heterogeneous date-like inputs into a :class:`Date`.

        Parameters
        ----------
        dt : str, Date, pendulum.Date or datetime.date
            Value to normalise. Strings are parsed via :meth:`parse` (or via
            :meth:`DateTime.from_format` when ``fmt`` is supplied); pendulum
            and stdlib dates are lifted via :meth:`from_pendulum` /
            :meth:`from_base`; already-``Date`` inputs are returned unchanged.
        fmt : str or None, default None
            Optional pendulum format string. When provided and ``dt`` is a
            string, parsing is strict against this format rather than using
            pendulum's permissive ISO parser.

        Returns
        -------
        Date
            Normalised :class:`Date` equivalent of ``dt``.
        """
        if isinstance(dt, str):
            if fmt is not None:
                return DateTime.from_format(dt, fmt=fmt).date()

            return cls.parse(dt)

        if isinstance(dt, DateTime):
            return dt.date()

        if isinstance(dt, cls):
            return dt

        if isinstance(dt, PendulumDate):
            return cls.from_pendulum(dt)

        return cls.from_base(dt)

    def to_datetime(
        self,
        *,
        tz: str | Tz = UTC,
    ) -> DateTime:
        """Lift the date to a :class:`DateTime` anchored at midnight.

        Parameters
        ----------
        tz : str or Tz, default UTC
            Timezone in which the resulting datetime's midnight is expressed.
            Accepts any value understood by :meth:`DateTime.create`.

        Returns
        -------
        DateTime
            Datetime at ``00:00:00.000000`` on this date in ``tz``.
        """
        return DateTime.create(
            year=self.year,
            month=self.month,
            day=self.day,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            tz=tz,
        )


class DateTime(DateNumericMixin, PendulumDateTime):
    """Pendulum :class:`~pendulum.DateTime` subclass with rich constructors.

    Combines the calendar helpers from :class:`DateNumericMixin` with pendulum's
    timezone-aware datetime, layering on convenience classmethods for
    :meth:`today`, :meth:`tomorrow`, :meth:`yesterday`, the machine's local
    timezone (:meth:`local`), naive construction (:meth:`without_timezone`),
    strict format parsing (:meth:`from_format`) and POSIX timestamp conversion
    (:meth:`from_timestamp`). Bidirectional bridges to pendulum and the stdlib
    are provided alongside :meth:`date` / :meth:`time` decomposition.
    """

    @classmethod
    def from_pendulum(
        cls,
        base: PendulumDateTime,
        /,
    ) -> DateTime:
        """Wrap a pendulum :class:`~pendulum.DateTime` in this subclass.

        Parameters
        ----------
        base : pendulum.DateTime
            Source pendulum datetime whose full year/month/day/hour/minute/
            second/microsecond/``tzinfo`` tuple is copied verbatim.

        Returns
        -------
        DateTime
            mayutils :class:`DateTime` equivalent of ``base``.
        """
        return cls(
            year=base.year,
            month=base.month,
            day=base.day,
            hour=base.hour,
            minute=base.minute,
            second=base.second,
            microsecond=base.microsecond,
            tzinfo=base.tzinfo,
        )

    @classmethod
    def from_base(
        cls,
        base: BaseDateTime,
        /,
    ) -> DateTime:
        """Construct a :class:`DateTime` from a stdlib :class:`datetime.datetime`.

        Parameters
        ----------
        base : datetime.datetime
            Standard-library datetime whose components (including ``tzinfo``)
            are copied into the new instance.

        Returns
        -------
        DateTime
            mayutils :class:`DateTime` equivalent of ``base``, preserving any
            existing timezone awareness.
        """
        return cls(
            year=base.year,
            month=base.month,
            day=base.day,
            hour=base.hour,
            minute=base.minute,
            second=base.second,
            microsecond=base.microsecond,
            tzinfo=base.tzinfo,
        )

    @property
    def as_pendulum(
        self,
    ) -> PendulumDateTime:
        """Expose the value as a plain pendulum :class:`~pendulum.DateTime`.

        Returns
        -------
        pendulum.DateTime
            Pendulum datetime mirroring this instance, for interop with APIs
            that perform exact-class checks against pendulum's own type.
        """
        return PendulumDateTime(
            year=self.year,
            month=self.month,
            day=self.day,
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microsecond,
            tzinfo=self.tzinfo,
        )

    @property
    def as_base(
        self,
    ) -> BaseDateTime:
        """Expose the value as a stdlib :class:`datetime.datetime`.

        Returns
        -------
        datetime.datetime
            Standard-library datetime with identical year through microsecond
            components and preserved ``tzinfo`` for timezone-aware callers.
        """
        return BaseDateTime(
            year=self.year,
            month=self.month,
            day=self.day,
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microsecond,
            tzinfo=self.tzinfo,
        )

    @classmethod
    def parse(
        cls,
        dt: str,
        /,
        *,
        fmt: str | None = None,
        tz: Tz = UTC,
        locale: str | None = None,
    ) -> DateTime:
        """Parse a textual datetime into a :class:`DateTime`.

        Parameters
        ----------
        dt : str
            Input string. When ``fmt`` is omitted the value must be
            ISO-8601 / pendulum parseable; otherwise it is parsed strictly
            against ``fmt``.
        fmt : str or None, default None
            Optional pendulum format string forcing strict parsing via
            :meth:`from_format`. When ``None`` the permissive
            :func:`pendulum.parse` branch is used.
        tz : Tz, default UTC
            Timezone applied when ``fmt`` is supplied and the parsed value
            has no intrinsic offset. Ignored on the permissive parse path.
        locale : str or None, default None
            Optional locale forwarded to :meth:`from_format` so month and
            weekday names can be resolved in non-English locales.

        Returns
        -------
        DateTime
            Parsed datetime.

        Raises
        ------
        ValueError
            If the parsed output is not a :class:`DateTime` (e.g. the input
            was a bare date or time).
        """
        output = (
            parse(dt)
            if fmt is None
            else DateTime.from_format(
                dt,
                fmt=fmt,
                tz=tz,
                locale=locale,
            )
        )

        if isinstance(output, cls):
            return output

        msg = "Could not parse to datetime"
        raise ValueError(msg)

    @classmethod
    def coerce(
        cls,
        dt: str | DateTime | PendulumDateTime | BaseDateTime,
        /,
        *,
        fmt: str | None = None,
        tz: Tz = UTC,
        locale: str | None = None,
    ) -> DateTime:
        """Coerce heterogeneous datetime-like inputs into a :class:`DateTime`.

        Parameters
        ----------
        dt : str, DateTime, pendulum.DateTime or datetime.datetime
            Value to normalise. Strings are routed through :meth:`parse`;
            pendulum datetimes are lifted via :meth:`from_pendulum`; stdlib
            datetimes via :meth:`from_base`; existing :class:`DateTime`
            instances are returned unchanged.
        fmt : str or None, default None
            Optional strict format string used only when ``dt`` is a string;
            forwarded to :meth:`parse`.
        tz : Tz, default UTC
            Timezone used by the strict parser when ``fmt`` is provided.
        locale : str or None, default None
            Optional locale forwarded to the strict parser for locale-aware
            tokens such as month names.

        Returns
        -------
        DateTime
            Normalised :class:`DateTime` equivalent of ``dt``.
        """
        if isinstance(dt, str):
            return DateTime.parse(
                dt,
                fmt=fmt,
                tz=tz,
                locale=locale,
            )

        if isinstance(dt, cls):
            return dt

        if isinstance(dt, PendulumDateTime):
            return cls.from_pendulum(dt)

        return cls.from_base(dt)

    @classmethod
    def today(
        cls,
        *,
        tz: str | Tz = "local",
    ) -> DateTime:
        """Construct the datetime for midnight starting today.

        Parameters
        ----------
        tz : str or Tz, default 'local'
            Timezone in which "today" is resolved and the resulting midnight is
            expressed. ``'local'`` uses pendulum's local-timezone detection.

        Returns
        -------
        DateTime
            Current day truncated to ``00:00:00.000000`` in ``tz``.
        """
        return cls.now(
            tz=tz,
        ).start_of(
            unit="day",
        )

    @classmethod
    def tomorrow(
        cls,
        *,
        tz: str | Tz = "local",
    ) -> DateTime:
        """Construct the datetime for midnight starting tomorrow.

        Parameters
        ----------
        tz : str or Tz, default 'local'
            Timezone in which "tomorrow" is resolved; determines the offset
            applied to ``now``.

        Returns
        -------
        DateTime
            One calendar day after :meth:`today` in ``tz``.
        """
        return cls.today(
            tz=tz,
        ).add(
            days=1,
        )

    @classmethod
    def yesterday(
        cls,
        *,
        tz: str | Tz = "local",
    ) -> DateTime:
        """Construct the datetime for midnight starting yesterday.

        Parameters
        ----------
        tz : str or Tz, default 'local'
            Timezone used to resolve which day counts as "yesterday".

        Returns
        -------
        DateTime
            One calendar day before :meth:`today` in ``tz``.
        """
        return cls.today(
            tz=tz,
        ).subtract(
            days=1,
        )

    @classmethod
    def local(
        cls,
        *,
        year: int,
        month: int = 1,
        day: int = 1,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        microsecond: int = 0,
    ) -> DateTime:
        """Construct a datetime expressed in the host machine's local timezone.

        Parameters
        ----------
        year : int
            Calendar year of the resulting datetime.
        month : int, default 1
            Calendar month in ``[1, 12]``.
        day : int, default 1
            Day of the month; must be valid for ``year``/``month``.
        hour : int, default 0
            Hour component in ``[0, 23]``.
        minute : int, default 0
            Minute component in ``[0, 59]``.
        second : int, default 0
            Second component in ``[0, 59]``.
        microsecond : int, default 0
            Microsecond component in ``[0, 999_999]``.

        Returns
        -------
        DateTime
            Datetime with the given components anchored in the result of
            :func:`pendulum.local_timezone`, i.e. the system's current
            timezone.
        """
        return cls.create(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=second,
            microsecond=microsecond,
            tz=local_timezone(),
        )

    @classmethod
    def without_timezone(
        cls,
        *,
        year: int,
        month: int = 1,
        day: int = 1,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        microsecond: int = 0,
        fold: int = 1,
    ) -> DateTime:
        """Construct a naive (timezone-less) :class:`DateTime`.

        Parameters
        ----------
        year : int
            Calendar year.
        month : int, default 1
            Month in ``[1, 12]``.
        day : int, default 1
            Day of the month valid for ``year``/``month``.
        hour : int, default 0
            Hour component in ``[0, 23]``.
        minute : int, default 0
            Minute component in ``[0, 59]``.
        second : int, default 0
            Second component in ``[0, 59]``.
        microsecond : int, default 0
            Microsecond component in ``[0, 999_999]``.
        fold : int, default 1
            Disambiguates ambiguous local times during DST transitions: ``0``
            selects the earlier of two identical wall-clock values and ``1``
            the later.

        Returns
        -------
        DateTime
            Naive datetime with ``tzinfo`` left unset; pair with
            :meth:`pendulum.DateTime.in_timezone` or similar to localise.
        """
        return cls(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=second,
            microsecond=microsecond,
            fold=fold,
        )

    @classmethod
    def from_format(
        cls,
        string: str,
        /,
        *,
        fmt: str,
        tz: str | Tz = UTC,
        locale: str | None = None,
    ) -> DateTime:
        """Parse ``string`` strictly against a pendulum format pattern.

        Parameters
        ----------
        string : str
            Textual datetime to parse.
        fmt : str
            Pendulum format pattern (e.g. ``"YYYY-MM-DD HH:mm:ss"``) describing
            the exact layout of ``string``.
        tz : str or Tz, default UTC
            Fallback timezone applied when ``fmt`` does not capture timezone
            information and ``string`` therefore leaves it unresolved.
        locale : str or None, default None
            Optional locale enabling translation of locale-sensitive tokens
            such as month and weekday names.

        Returns
        -------
        DateTime
            Datetime produced by pendulum's formatter from the parsed fields.
        """
        parts = FORMATTER.parse(
            time=string,
            fmt=fmt,
            now=cls.now(tz=tz),
            locale=locale,
        )

        if parts["tz"] is None:
            parts["tz"] = tz

        return cls.create(**parts)

    @classmethod
    def from_timestamp(
        cls,
        timestamp: float,
        /,
        *,
        tz: str | Tz = UTC,
    ) -> DateTime:
        """Construct a :class:`DateTime` from a POSIX timestamp.

        Parameters
        ----------
        timestamp : float
            Seconds since the Unix epoch (``1970-01-01T00:00:00Z``); fractional
            seconds are preserved as microseconds.
        tz : str or Tz, default UTC
            Timezone in which the resulting datetime is expressed. The
            timestamp is interpreted in UTC first, then converted to ``tz``.

        Returns
        -------
        DateTime
            Datetime representing the same instant as ``timestamp``, expressed
            in ``tz``.
        """
        dt = BaseDateTime.fromtimestamp(
            timestamp=timestamp,
            tz=UTC,
        )

        dt = cls.create(
            year=dt.year,
            month=dt.month,
            day=dt.day,
            hour=dt.hour,
            minute=dt.minute,
            second=dt.second,
            microsecond=dt.microsecond,
        )

        if tz is not UTC or tz != "UTC":
            dt = dt.in_timezone(tz=tz)

        return dt

    def date(
        self,
    ) -> Date:
        """Extract the calendar date portion of this datetime.

        Returns
        -------
        Date
            mayutils :class:`Date` with the year, month and day of this
            instance; clock and timezone information are discarded.
        """
        return Date(
            year=self.year,
            month=self.month,
            day=self.day,
        )

    def time(
        self,
    ) -> Time:
        """Extract the wall-clock time portion of this datetime.

        Returns
        -------
        Time
            mayutils :class:`Time` with the hour, minute, second and
            microsecond of this instance; timezone information is dropped
            because the stdlib factory used here does not propagate ``tzinfo``.
        """
        return Time(
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microsecond,
        )


def parse(
    dt: str | Date | DateTime | Time | Duration,
    /,
) -> str | Date | DateTime | Time | Duration:
    """Dispatch a datetime-ish input to the matching mayutils wrapper.

    The helper accepts either a pendulum-parseable string or an already-parsed
    pendulum/``mayutils`` value. Strings are routed through
    :func:`pendulum.parse`; the result (or the passthrough input) is then
    re-typed into :class:`DateTime`, :class:`Date` or :class:`Time` where
    applicable so downstream code can rely on the mayutils helpers.

    Parameters
    ----------
    dt : str, Date, DateTime, Time or Duration
        Input value. Strings are parsed by pendulum; pendulum/mayutils dates,
        times and datetimes are rewrapped into this module's subclasses;
        :class:`pendulum.Duration` values are returned unchanged.

    Returns
    -------
    str, Date, DateTime, Time or Duration
        Re-typed mayutils wrapper for pendulum ``DateTime`` / ``Time`` /
        ``Date`` results; the original value is returned untouched when it is
        a :class:`pendulum.Duration` or any type pendulum yielded that does
        not fall into the three supported calendar categories.
    """
    output = pendulum_parse(text=dt) if isinstance(dt, str) else dt

    if isinstance(output, PendulumDateTime):
        return DateTime.from_pendulum(output)

    if isinstance(output, PendulumTime):
        return Time.from_pendulum(output)

    if isinstance(output, PendulumDate):
        return Date.from_pendulum(output)

    return output


register_adapter(DateTime, lambda val: val.isoformat(sep=" "))
