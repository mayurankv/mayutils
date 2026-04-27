"""
Provide pendulum-backed date, time and datetime wrappers with a unified parser.

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

See Also
--------
mayutils.objects.datetime.constants : Shared datetime constants and formatter.
mayutils.objects.datetime.timezone : Timezone helpers consumed by these classes.
mayutils.objects.datetime.interval : Interval helpers built on top of :class:`DateTime`.
pendulum.DateTime : Upstream pendulum datetime type being subclassed.
datetime.datetime : Standard-library datetime type bridged via ``as_base``.

Examples
--------
>>> from mayutils.objects.datetime.datetime import DateTime, parse
>>> dt = DateTime.parse("2026-04-22T09:30:00+00:00")
>>> dt.year, dt.month, dt.day
(2026, 4, 22)
>>> isinstance(parse("2026-04-22"), DateTime)
True
"""

from __future__ import annotations

from datetime import date as BaseDate  # noqa: N812
from datetime import datetime as BaseDateTime  # noqa: N812
from datetime import time as BaseTime  # noqa: N812
from datetime import tzinfo as BaseTzinfo  # noqa: N812
from sqlite3 import register_adapter
from typing import TYPE_CHECKING, Self

from mayutils.core.extras import may_require_extras

with may_require_extras():
    import numpy as np
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
    """
    Share calendar helpers across :class:`Date` and :class:`DateTime`.

    The mixin inherits from :class:`pendulum.Date` purely to satisfy static type
    checkers, so references to ``day_of_week``, ``format`` and ``year`` resolve
    against pendulum's surface without triggering attribute-access warnings. It
    is not intended to be instantiated directly; concrete subclasses supply the
    actual construction semantics while reusing the helpers below for weekend
    detection, human-readable month names, and NumPy interop via
    :class:`numpy.datetime64`.

    See Also
    --------
    mayutils.objects.datetime.datetime.Date : Concrete date subclass reusing this mixin.
    mayutils.objects.datetime.datetime.DateTime : Concrete datetime subclass reusing this mixin.
    pendulum.Date : Upstream pendulum type providing inherited calendar machinery.

    Examples
    --------
    >>> from mayutils.objects.datetime.datetime import Date
    >>> issubclass(Date, DateNumericMixin)
    True
    """

    def is_weekend(
        self,
    ) -> bool:
        """
        Check whether the current date falls on a Saturday or Sunday.

        Uses pendulum's ``day_of_week`` property, which numbers the ISO week
        starting at Monday=0, so Saturday and Sunday correspond to the values
        ``5`` and ``6``. The check is purely calendrical and does not factor
        in regional working-week conventions.

        Returns
        -------
            ``True`` when pendulum's ``day_of_week`` is either ``5`` (Saturday)
            or ``6`` (Sunday), otherwise ``False``.

        See Also
        --------
        pendulum.Date.day_of_week : Underlying weekday accessor used here.
        mayutils.objects.datetime.datetime.DateNumericMixin.to_month : Sibling helper on this mixin.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> Date(year=2026, month=4, day=25).is_weekend()
        True
        >>> Date(year=2026, month=4, day=22).is_weekend()
        False
        """
        return self.day_of_week in (5, 6)

    def to_month(
        self,
        *,
        long: bool = True,
    ) -> str:
        """
        Render the month as a locale-aware human-readable name.

        Delegates to pendulum's ``format`` method using the ``MMMM`` or ``MMM``
        tokens, which respect pendulum's configured locale. The helper provides
        a terse toggle between full and abbreviated forms without callers
        having to remember the token syntax.

        Parameters
        ----------
        long
            When ``True`` the full month name is returned using pendulum's
            ``MMMM`` token (e.g. ``"January"``); when ``False`` the abbreviated
            three-letter form is returned via ``MMM`` (e.g. ``"Jan"``).

        Returns
        -------
            Month name formatted in the selected long or short style.

        See Also
        --------
        pendulum.Date.format : Underlying formatter driving this method.
        mayutils.objects.datetime.datetime.DateNumericMixin.is_weekend : Sibling helper on this mixin.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> Date(year=2026, month=4, day=22).to_month()
        'April'
        >>> Date(year=2026, month=4, day=22).to_month(long=False)
        'Apr'
        """
        return self.format(fmt="MMMM" if long else "MMM")

    def to_numpy(
        self,
    ) -> np.datetime64:
        """
        Convert the value to a :class:`numpy.datetime64` scalar.

        Provides a NumPy-native representation suitable for placement inside
        NumPy arrays or pandas datetime columns. Precision is inferred from
        the instance itself, preserving sub-second components when present.

        Returns
        -------
            NumPy scalar with precision inferred from this instance, suitable
            for placement inside NumPy arrays or pandas datetime columns.

        See Also
        --------
        numpy.datetime64 : Target NumPy scalar type.
        mayutils.objects.datetime.datetime.DateNumericMixin.to_month : Sibling helper on this mixin.

        Examples
        --------
        >>> import numpy as np
        >>> from mayutils.objects.datetime.datetime import Date
        >>> isinstance(Date(year=2026, month=4, day=22).to_numpy(), np.datetime64)
        True
        """
        return np.datetime64(self)


class Time(PendulumTime):
    """
    Subclass :class:`~pendulum.Time` with date-combination helpers.

    Extends pendulum's time type with ergonomic constructors for converting
    from pendulum or the standard library, lossless bridges back to those
    representations, string parsing via the module-level :func:`parse`, and
    helpers for placing the time on a specific date (:meth:`on`), today
    (:meth:`today`) or expressing it as a fraction of the day
    (:attr:`fractional_completion`).

    See Also
    --------
    mayutils.objects.datetime.datetime.Date : Calendar-date counterpart.
    mayutils.objects.datetime.datetime.DateTime : Combined date and time counterpart.
    pendulum.Time : Upstream pendulum time class being subclassed.
    datetime.time : Standard-library time type reachable via :attr:`as_base`.

    Examples
    --------
    >>> from mayutils.objects.datetime.datetime import Time
    >>> t = Time(hour=9, minute=30)
    >>> t.hour, t.minute
    (9, 30)
    """

    @classmethod
    def from_pendulum(
        cls,
        base: PendulumTime,
        /,
    ) -> Time:
        """
        Wrap a pendulum :class:`~pendulum.Time` in this subclass.

        The conversion copies the hour, minute, second, microsecond and
        ``tzinfo`` fields verbatim, so the resulting instance is indistinguishable
        from ``base`` with respect to equality and formatting. Use this after
        any pendulum call that returns plain :class:`pendulum.Time` so the
        mayutils helpers become available on the value.

        Parameters
        ----------
        base
            Source pendulum time whose hour, minute, second, microsecond and
            ``tzinfo`` are copied verbatim into the new instance.

        Returns
        -------
            New :class:`Time` mirroring ``base`` so mayutils helpers become
            available on the value.

        See Also
        --------
        mayutils.objects.datetime.datetime.Time.from_base : Stdlib-aware counterpart.
        mayutils.objects.datetime.datetime.Time.as_pendulum : Inverse conversion back to pendulum.

        Examples
        --------
        >>> from pendulum import Time as PendulumTime
        >>> from mayutils.objects.datetime.datetime import Time
        >>> base = PendulumTime(hour=9, minute=30)
        >>> Time.from_pendulum(base).hour
        9
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
        """
        Construct a :class:`Time` from a stdlib :class:`datetime.time`.

        The clock components of ``base`` are preserved while timezone
        information is (re)applied from ``tz``. This is the preferred bridge
        when receiving ``datetime.time`` values from stdlib-centric APIs such
        as the ``datetime`` module or database drivers that do not propagate
        timezone metadata.

        Parameters
        ----------
        base
            Standard-library time value to convert; its clock components are
            preserved while timezone information is (re)applied from ``tz``.
        tz
            Timezone to attach to the result. Any value accepted by
            :meth:`pendulum.Time.instance` is valid; pass ``None`` to produce
            a naive time with no attached offset.

        Returns
        -------
            Mayutils :class:`Time` equivalent of ``base`` localised to ``tz``.

        See Also
        --------
        mayutils.objects.datetime.datetime.Time.from_pendulum : Pendulum-aware counterpart.
        mayutils.objects.datetime.datetime.Time.as_base : Inverse conversion back to stdlib.

        Examples
        --------
        >>> from datetime import time as BaseTime
        >>> from mayutils.objects.datetime.datetime import Time
        >>> Time.from_base(BaseTime(9, 30)).hour
        9
        """
        return cls.instance(
            t=base,
            tz=tz,
        )

    @property
    def as_pendulum(
        self,
    ) -> PendulumTime:
        """
        Expose the value as a plain pendulum :class:`~pendulum.Time`.

        Constructs a fresh :class:`pendulum.Time` with identical components so
        that callers requiring strict pendulum type checks, such as ``type(x)
        is pendulum.Time``, receive a usable value. This is the inverse of
        :meth:`from_pendulum`.

        Returns
        -------
            Fresh pendulum time with identical components, for passing to APIs
            that perform ``type(x) is pendulum.Time`` style checks.

        See Also
        --------
        mayutils.objects.datetime.datetime.Time.as_base : Stdlib counterpart.
        mayutils.objects.datetime.datetime.Time.from_pendulum : Inverse bridging operation.

        Examples
        --------
        >>> from pendulum import Time as PendulumTime
        >>> from mayutils.objects.datetime.datetime import Time
        >>> isinstance(Time(hour=9, minute=30).as_pendulum, PendulumTime)
        True
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
        """
        Expose the value as a stdlib :class:`datetime.time`.

        Produces a standard-library :class:`datetime.time` with matching
        clock components for interop with libraries that do not accept
        pendulum instances. Note that ``tzinfo`` is intentionally dropped
        because the stdlib constructor used here does not propagate it.

        Returns
        -------
            Standard-library time with matching clock components. Note that
            ``tzinfo`` is intentionally dropped because the stdlib constructor
            used here does not propagate it.

        See Also
        --------
        mayutils.objects.datetime.datetime.Time.as_pendulum : Pendulum counterpart.
        mayutils.objects.datetime.datetime.Time.from_base : Inverse bridging operation.

        Examples
        --------
        >>> from datetime import time as BaseTime
        >>> from mayutils.objects.datetime.datetime import Time
        >>> isinstance(Time(hour=9, minute=30).as_base, BaseTime)
        True
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
        """
        Parse a string representation into a :class:`Time`.

        Delegates to the module-level :func:`parse` helper, which routes
        through :func:`pendulum.parse`. Datetime inputs are accepted and their
        time portion is extracted so callers can feed in ISO-8601 values that
        happen to include both the date and the time.

        Parameters
        ----------
        dt
            ISO-8601 or pendulum-compatible textual representation of a time
            (or datetime, in which case the time portion is extracted).

        Returns
        -------
            Parsed time value.

        Raises
        ------
        ValueError
            If :func:`parse` returned a :class:`Date` or other value that
            cannot be reduced to a time component.

        See Also
        --------
        mayutils.objects.datetime.datetime.parse : Module-level dispatch helper.
        mayutils.objects.datetime.datetime.DateTime.parse : Datetime-oriented counterpart.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Time
        >>> Time.parse("09:30:00").hour
        9
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
        """
        Return the current wall-clock time in the system's default timezone.

        Uses :meth:`DateTime.now` under the hood so the choice of timezone
        follows pendulum's standard resolution, which typically defaults to
        the host machine's local timezone. Only the time portion of the
        resulting datetime is returned.

        Returns
        -------
            Time portion of :meth:`DateTime.now`, using pendulum's default
            timezone resolution.

        See Also
        --------
        mayutils.objects.datetime.datetime.DateTime.now : Full datetime counterpart used internally.
        mayutils.objects.datetime.datetime.Time.today : Lifts the current time onto today's date.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Time
        >>> isinstance(Time.now(), Time)
        True
        """
        return DateTime.now().time()

    def today(
        self,
    ) -> DateTime:
        """
        Place this time on today's date in its own timezone.

        Combines the time components of ``self`` with the current calendar
        date in the instance's attached ``tzinfo`` to produce a new
        :class:`DateTime`. Useful when a time-of-day value needs to be
        promoted into a full datetime anchored to "now" for scheduling.

        Returns
        -------
            Datetime whose date portion is today (resolved in the current
            instance's ``tzinfo``) and whose clock components mirror ``self``.

        See Also
        --------
        mayutils.objects.datetime.datetime.Time.on : Place the time on an explicit date.
        mayutils.objects.datetime.datetime.DateTime.today : Class-level "today at midnight" helper.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Time
        >>> Time(hour=9, minute=30).today().hour
        9
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
        """
        Combine this time with an explicit date into a :class:`DateTime`.

        The year/month/day of the resulting datetime come from ``date`` while
        the hour/minute/second/microsecond/``tzinfo`` are taken from ``self``.
        This is the preferred bridging operation when you have a calendar
        date and a time-of-day separately and need to rejoin them.

        Parameters
        ----------
        date
            Calendar date supplying the year, month and day portions of the
            resulting datetime.

        Returns
        -------
            Datetime with the date components taken from ``date`` and the
            clock/tz components taken from ``self``.

        See Also
        --------
        mayutils.objects.datetime.datetime.Time.today : Combine with today's date automatically.
        mayutils.objects.datetime.datetime.Date.to_datetime : Inverse style bridge from date-first.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date, Time
        >>> combined = Time(hour=9, minute=30).on(Date(year=2026, month=4, day=22))
        >>> combined.year, combined.hour
        (2026, 9)
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
        """
        Compute the fraction of the day that has elapsed at this time.

        Converts the time into seconds since midnight (including microsecond
        precision) and divides by the total number of seconds in a civil day.
        Useful for plotting time-of-day along a ``[0, 1)`` axis or for
        proportional scheduling calculations.

        Returns
        -------
            Value in ``[0.0, 1.0)`` computed as ``seconds since midnight /
            seconds in a day``, where ``0.0`` is midnight and values approach
            ``1.0`` as the end of the civil day is reached.

        See Also
        --------
        mayutils.objects.datetime.constants.DAY_SECONDS : Divisor used by this property.
        mayutils.objects.datetime.datetime.Time.now : Construct a ``Time`` representing the current wall clock.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Time
        >>> Time(hour=12).fractional_completion
        0.5
        >>> Time(hour=0).fractional_completion
        0.0
        """
        return (self.hour * 3600 + self.minute * 60 + self.second + self.microsecond * 1e-6) / DAY_SECONDS


class Date(DateNumericMixin):
    """
    Subclass :class:`~pendulum.Date` with parsing and interop helpers.

    Augments pendulum's calendar date with consistent conversion helpers to and
    from pendulum/stdlib equivalents, permissive :meth:`parse` and
    :meth:`coerce` factories, and a :meth:`to_datetime` lift that anchors the
    date at midnight in a chosen timezone. Numeric calendar helpers are
    inherited from :class:`DateNumericMixin`.

    See Also
    --------
    mayutils.objects.datetime.datetime.Time : Clock-only counterpart.
    mayutils.objects.datetime.datetime.DateTime : Combined date and time counterpart.
    mayutils.objects.datetime.datetime.DateNumericMixin : Source of shared calendar helpers.
    pendulum.Date : Upstream pendulum date type being subclassed.

    Examples
    --------
    >>> from mayutils.objects.datetime.datetime import Date
    >>> d = Date(year=2026, month=4, day=22)
    >>> d.year, d.month, d.day
    (2026, 4, 22)
    """

    @classmethod
    def from_pendulum(
        cls,
        base: PendulumDate,
        /,
    ) -> Self:
        """
        Wrap a pendulum :class:`~pendulum.Date` in this subclass.

        The calendar components of ``base`` are copied verbatim into a new
        instance, so equality and formatting remain stable while the mayutils
        helpers (``is_weekend``, ``to_month``, ``to_numpy`` and so on) become
        available on the value.

        Parameters
        ----------
        base
            Source pendulum date whose year, month and day are copied into the
            new instance.

        Returns
        -------
            Mayutils :class:`Date` with calendar components matching ``base``.

        See Also
        --------
        mayutils.objects.datetime.datetime.Date.from_base : Stdlib-aware counterpart.
        mayutils.objects.datetime.datetime.Date.as_pendulum : Inverse bridge back to pendulum.

        Examples
        --------
        >>> from pendulum import Date as PendulumDate
        >>> from mayutils.objects.datetime.datetime import Date
        >>> Date.from_pendulum(PendulumDate(2026, 4, 22)).month
        4
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
        """
        Construct a :class:`Date` from a stdlib :class:`datetime.date`.

        Lifts the ``year``/``month``/``day`` attributes of ``base`` into a
        fresh instance of this class. Useful when receiving plain
        :class:`datetime.date` values from stdlib-centric APIs or database
        drivers that do not return pendulum objects.

        Parameters
        ----------
        base
            Standard-library date whose calendar components are lifted into a
            new instance of this class.

        Returns
        -------
            Mayutils :class:`Date` equivalent of ``base``.

        See Also
        --------
        mayutils.objects.datetime.datetime.Date.from_pendulum : Pendulum-aware counterpart.
        mayutils.objects.datetime.datetime.Date.as_base : Inverse bridge back to stdlib.

        Examples
        --------
        >>> from datetime import date as BaseDate
        >>> from mayutils.objects.datetime.datetime import Date
        >>> Date.from_base(BaseDate(2026, 4, 22)).day
        22
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
        """
        Expose the value as a plain pendulum :class:`~pendulum.Date`.

        Returns a fresh :class:`pendulum.Date` whose calendar components match
        ``self``. The copy is necessary because callers using ``type(x) is
        pendulum.Date`` style checks will otherwise reject the subclass
        instance even though it is substitutable structurally.

        Returns
        -------
            Pendulum date with the same calendar components, suitable for
            handing to APIs that type-check against pendulum's own class.

        See Also
        --------
        mayutils.objects.datetime.datetime.Date.as_base : Stdlib counterpart.
        mayutils.objects.datetime.datetime.Date.from_pendulum : Inverse bridging operation.

        Examples
        --------
        >>> from pendulum import Date as PendulumDate
        >>> from mayutils.objects.datetime.datetime import Date
        >>> isinstance(Date(year=2026, month=4, day=22).as_pendulum, PendulumDate)
        True
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
        """
        Expose the value as a stdlib :class:`datetime.date`.

        Returns a standard-library :class:`datetime.date` with matching
        year/month/day components. Intended for interop with libraries that
        do not accept pendulum instances or perform nominal type checks
        against the stdlib class.

        Returns
        -------
            Standard-library date with matching year/month/day.

        See Also
        --------
        mayutils.objects.datetime.datetime.Date.as_pendulum : Pendulum counterpart.
        mayutils.objects.datetime.datetime.Date.from_base : Inverse bridging operation.

        Examples
        --------
        >>> from datetime import date as BaseDate
        >>> from mayutils.objects.datetime.datetime import Date
        >>> isinstance(Date(year=2026, month=4, day=22).as_base, BaseDate)
        True
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
        """
        Parse a textual date (or datetime) into a :class:`Date`.

        Delegates to the module-level :func:`parse` dispatcher and reduces
        datetime outputs via :meth:`DateTime.date` so that strings containing
        a full timestamp still yield a plain calendar date. Raises when the
        parsed value cannot be coerced to a date.

        Parameters
        ----------
        dt
            ISO-8601 or pendulum-compatible date/datetime string. Datetime
            inputs are accepted and reduced to their date portion.

        Returns
        -------
            Parsed date value.

        Raises
        ------
        TypeError
            If :func:`parse` yielded a value that is neither a :class:`Date`
            nor convertible from a :class:`DateTime`.

        See Also
        --------
        mayutils.objects.datetime.datetime.parse : Module-level dispatch helper.
        mayutils.objects.datetime.datetime.Date.coerce : Richer front-end accepting non-string inputs.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> Date.parse("2026-04-22").day
        22
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
        """
        Coerce heterogeneous date-like inputs into a :class:`Date`.

        Normalises the many ways a calendar date can arrive at the API
        boundary (string, pendulum value, stdlib value, or already a
        :class:`Date`) into a single consistent subclass instance. Strings are
        parsed via :meth:`parse` or :meth:`DateTime.from_format` depending on
        whether ``fmt`` is supplied.

        Parameters
        ----------
        dt
            Value to normalise. Strings are parsed via :meth:`parse` (or via
            :meth:`DateTime.from_format` when ``fmt`` is supplied); pendulum
            and stdlib dates are lifted via :meth:`from_pendulum` /
            :meth:`from_base`; already-``Date`` inputs are returned unchanged.
        fmt
            Optional pendulum format string. When provided and ``dt`` is a
            string, parsing is strict against this format rather than using
            pendulum's permissive ISO parser.

        Returns
        -------
            Normalised :class:`Date` equivalent of ``dt``.

        See Also
        --------
        mayutils.objects.datetime.datetime.Date.parse : String-only parsing path.
        mayutils.objects.datetime.datetime.DateTime.coerce : Datetime-oriented counterpart.

        Examples
        --------
        >>> from datetime import date as BaseDate
        >>> from mayutils.objects.datetime.datetime import Date
        >>> Date.coerce("2026-04-22").day
        22
        >>> Date.coerce(BaseDate(2026, 4, 22)).day
        22
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
        """
        Lift the date to a :class:`DateTime` anchored at midnight.

        Builds a new :class:`DateTime` whose calendar components match
        ``self`` and whose clock components are set to ``00:00:00.000000`` in
        the supplied timezone. Useful for widening a date into an
        interval-style timestamp without implicit DST surprises.

        Parameters
        ----------
        tz
            Timezone in which the resulting datetime's midnight is expressed.
            Accepts any value understood by :meth:`DateTime.create`.

        Returns
        -------
            Datetime at ``00:00:00.000000`` on this date in ``tz``.

        See Also
        --------
        mayutils.objects.datetime.datetime.Time.on : Inverse bridge combining time with a date.
        mayutils.objects.datetime.datetime.DateTime.today : Produces today's midnight directly.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> dt = Date(year=2026, month=4, day=22).to_datetime()
        >>> dt.hour, dt.minute
        (0, 0)
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
    """
    Subclass :class:`~pendulum.DateTime` with rich constructors.

    Combines the calendar helpers from :class:`DateNumericMixin` with pendulum's
    timezone-aware datetime, layering on convenience classmethods for
    :meth:`today`, :meth:`tomorrow`, :meth:`yesterday`, the machine's local
    timezone (:meth:`local`), naive construction (:meth:`without_timezone`),
    strict format parsing (:meth:`from_format`) and POSIX timestamp conversion
    (:meth:`from_timestamp`). Bidirectional bridges to pendulum and the stdlib
    are provided alongside :meth:`date` / :meth:`time` decomposition.

    See Also
    --------
    mayutils.objects.datetime.datetime.Date : Calendar-only counterpart.
    mayutils.objects.datetime.datetime.Time : Clock-only counterpart.
    mayutils.objects.datetime.datetime.DateNumericMixin : Source of shared calendar helpers.
    pendulum.DateTime : Upstream pendulum datetime type being subclassed.

    Examples
    --------
    >>> from mayutils.objects.datetime.datetime import DateTime
    >>> dt = DateTime.parse("2026-04-22T09:30:00+00:00")
    >>> dt.year, dt.hour
    (2026, 9)
    """

    @classmethod
    def from_pendulum(
        cls,
        base: PendulumDateTime,
        /,
    ) -> DateTime:
        """
        Wrap a pendulum :class:`~pendulum.DateTime` in this subclass.

        Copies every component of ``base`` (year through microsecond plus
        ``tzinfo``) into a new instance so that downstream mayutils helpers
        become available without altering the represented instant or its
        timezone awareness.

        Parameters
        ----------
        base
            Source pendulum datetime whose full year/month/day/hour/minute/
            second/microsecond/``tzinfo`` tuple is copied verbatim.

        Returns
        -------
            Mayutils :class:`DateTime` equivalent of ``base``.

        See Also
        --------
        mayutils.objects.datetime.datetime.DateTime.from_base : Stdlib-aware counterpart.
        mayutils.objects.datetime.datetime.DateTime.as_pendulum : Inverse bridge back to pendulum.

        Examples
        --------
        >>> from pendulum import DateTime as PendulumDateTime
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> DateTime.from_pendulum(PendulumDateTime(2026, 4, 22, 9, 30)).hour
        9
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
        """
        Construct a :class:`DateTime` from a stdlib :class:`datetime.datetime`.

        Copies every component of ``base``, including ``tzinfo``, into a new
        instance. Use this bridge when consuming values from stdlib-first APIs
        such as ``datetime.datetime.fromisoformat`` or database drivers that
        emit plain :class:`datetime.datetime` objects.

        Parameters
        ----------
        base
            Standard-library datetime whose components (including ``tzinfo``)
            are copied into the new instance.

        Returns
        -------
            Mayutils :class:`DateTime` equivalent of ``base``, preserving any
            existing timezone awareness.

        See Also
        --------
        mayutils.objects.datetime.datetime.DateTime.from_pendulum : Pendulum-aware counterpart.
        mayutils.objects.datetime.datetime.DateTime.as_base : Inverse bridge back to stdlib.

        Examples
        --------
        >>> from datetime import datetime as BaseDateTime, timezone
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> base = BaseDateTime(2026, 4, 22, 9, 30, tzinfo=timezone.utc)
        >>> DateTime.from_base(base).hour
        9
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
        """
        Expose the value as a plain pendulum :class:`~pendulum.DateTime`.

        Constructs a fresh :class:`pendulum.DateTime` with identical components
        so that callers using strict ``type(x) is pendulum.DateTime`` checks
        receive a usable value. This mirrors the behaviour of
        :attr:`Date.as_pendulum` and :attr:`Time.as_pendulum`.

        Returns
        -------
            Pendulum datetime mirroring this instance, for interop with APIs
            that perform exact-class checks against pendulum's own type.

        See Also
        --------
        mayutils.objects.datetime.datetime.DateTime.as_base : Stdlib counterpart.
        mayutils.objects.datetime.datetime.DateTime.from_pendulum : Inverse bridging operation.

        Examples
        --------
        >>> from pendulum import DateTime as PendulumDateTime
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> dt = DateTime(year=2026, month=4, day=22, hour=9, minute=30)
        >>> isinstance(dt.as_pendulum, PendulumDateTime)
        True
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
        """
        Expose the value as a stdlib :class:`datetime.datetime`.

        Produces a standard-library :class:`datetime.datetime` retaining the
        year-through-microsecond components and the attached ``tzinfo``, which
        makes this bridge the preferred round-trip for serialisation layers
        that require timezone awareness (unlike :attr:`Time.as_base`).

        Returns
        -------
            Standard-library datetime with identical year through microsecond
            components and preserved ``tzinfo`` for timezone-aware callers.

        See Also
        --------
        mayutils.objects.datetime.datetime.DateTime.as_pendulum : Pendulum counterpart.
        mayutils.objects.datetime.datetime.DateTime.from_base : Inverse bridging operation.

        Examples
        --------
        >>> from datetime import datetime as BaseDateTime
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> dt = DateTime(year=2026, month=4, day=22, hour=9, minute=30)
        >>> isinstance(dt.as_base, BaseDateTime)
        True
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
        """
        Parse a textual datetime into a :class:`DateTime`.

        Dispatches between two parsing strategies depending on whether a
        strict format is supplied: the permissive :func:`pendulum.parse`
        branch (accepts ISO-8601 and many common layouts) or the strict
        :meth:`from_format` branch, which forces the input to match ``fmt``
        token for token.

        Parameters
        ----------
        dt
            Input string. When ``fmt`` is omitted the value must be
            ISO-8601 / pendulum parseable; otherwise it is parsed strictly
            against ``fmt``.
        fmt
            Optional pendulum format string forcing strict parsing via
            :meth:`from_format`. When ``None`` the permissive
            :func:`pendulum.parse` branch is used.
        tz
            Timezone applied when ``fmt`` is supplied and the parsed value
            has no intrinsic offset. Ignored on the permissive parse path.
        locale
            Optional locale forwarded to :meth:`from_format` so month and
            weekday names can be resolved in non-English locales.

        Returns
        -------
            Parsed datetime.

        Raises
        ------
        ValueError
            If the parsed output is not a :class:`DateTime` (e.g. the input
            was a bare date or time).

        See Also
        --------
        mayutils.objects.datetime.datetime.parse : Module-level dispatch helper.
        mayutils.objects.datetime.datetime.DateTime.from_format : Strict parsing backend.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> DateTime.parse("2026-04-22T09:30:00+00:00").hour
        9
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
        """
        Coerce heterogeneous datetime-like inputs into a :class:`DateTime`.

        Normalises incoming values into a single subclass instance by
        delegating to the appropriate bridging constructor. Strings go
        through :meth:`parse`, pendulum instances through
        :meth:`from_pendulum`, stdlib instances through :meth:`from_base`,
        and existing :class:`DateTime` instances are returned unchanged.

        Parameters
        ----------
        dt
            Value to normalise. Strings are routed through :meth:`parse`;
            pendulum datetimes are lifted via :meth:`from_pendulum`; stdlib
            datetimes via :meth:`from_base`; existing :class:`DateTime`
            instances are returned unchanged.
        fmt
            Optional strict format string used only when ``dt`` is a string;
            forwarded to :meth:`parse`.
        tz
            Timezone used by the strict parser when ``fmt`` is provided.
        locale
            Optional locale forwarded to the strict parser for locale-aware
            tokens such as month names.

        Returns
        -------
            Normalised :class:`DateTime` equivalent of ``dt``.

        See Also
        --------
        mayutils.objects.datetime.datetime.DateTime.parse : String-only parsing path.
        mayutils.objects.datetime.datetime.Date.coerce : Date-oriented counterpart.

        Examples
        --------
        >>> from datetime import datetime as BaseDateTime, timezone
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> DateTime.coerce("2026-04-22T09:30:00+00:00").hour
        9
        >>> DateTime.coerce(BaseDateTime(2026, 4, 22, 9, 30, tzinfo=timezone.utc)).hour
        9
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
        """
        Construct the datetime for midnight starting today.

        Resolves "today" in the supplied timezone by first taking
        :meth:`now` and then truncating to the start of the day. Unlike the
        stdlib ``date.today()`` this returns a full datetime rather than a
        calendar-only value.

        Parameters
        ----------
        tz
            Timezone in which "today" is resolved and the resulting midnight
            is expressed. ``'local'`` uses pendulum's local-timezone detection.

        Returns
        -------
            Current day truncated to ``00:00:00.000000`` in ``tz``.

        See Also
        --------
        mayutils.objects.datetime.datetime.DateTime.tomorrow : Same but for the following calendar day.
        mayutils.objects.datetime.datetime.DateTime.yesterday : Same but for the preceding calendar day.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> today = DateTime.today(tz="UTC")
        >>> today.hour, today.minute, today.second
        (0, 0, 0)
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
        """
        Construct the datetime for midnight starting tomorrow.

        Builds on :meth:`today` by adding a single calendar day. The result
        is anchored at midnight in ``tz`` so it is safe to use as the
        exclusive end of a day-long interval beginning at :meth:`today`.

        Parameters
        ----------
        tz
            Timezone in which "tomorrow" is resolved; determines the offset
            applied to ``now``.

        Returns
        -------
            One calendar day after :meth:`today` in ``tz``.

        See Also
        --------
        mayutils.objects.datetime.datetime.DateTime.today : Same day at midnight.
        mayutils.objects.datetime.datetime.DateTime.yesterday : Preceding day at midnight.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> (DateTime.tomorrow(tz="UTC") - DateTime.today(tz="UTC")).in_days()
        1
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
        """
        Construct the datetime for midnight starting yesterday.

        Builds on :meth:`today` by subtracting a single calendar day, yielding
        a midnight anchor in ``tz`` that pairs symmetrically with
        :meth:`today` as a day-length interval endpoint.

        Parameters
        ----------
        tz
            Timezone used to resolve which day counts as "yesterday".

        Returns
        -------
            One calendar day before :meth:`today` in ``tz``.

        See Also
        --------
        mayutils.objects.datetime.datetime.DateTime.today : Same day at midnight.
        mayutils.objects.datetime.datetime.DateTime.tomorrow : Following day at midnight.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> (DateTime.today(tz="UTC") - DateTime.yesterday(tz="UTC")).in_days()
        1
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
        """
        Construct a datetime expressed in the host machine's local timezone.

        Wraps :meth:`create` with the local timezone auto-detected via
        :func:`pendulum.local_timezone`. This saves callers from having to
        supply a timezone explicitly when the intended semantics are "build a
        datetime as though I typed it into a local clock".

        Parameters
        ----------
        year
            Calendar year of the resulting datetime.
        month
            Calendar month in ``[1, 12]``.
        day
            Day of the month; must be valid for ``year``/``month``.
        hour
            Hour component in ``[0, 23]``.
        minute
            Minute component in ``[0, 59]``.
        second
            Second component in ``[0, 59]``.
        microsecond
            Microsecond component in ``[0, 999_999]``.

        Returns
        -------
            Datetime with the given components anchored in the result of
            :func:`pendulum.local_timezone`, i.e. the system's current
            timezone.

        See Also
        --------
        mayutils.objects.datetime.datetime.DateTime.without_timezone : Same construction without any timezone.
        pendulum.local_timezone : Timezone resolver used under the hood.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> dt = DateTime.local(year=2026, month=4, day=22, hour=9, minute=30)
        >>> dt.year, dt.hour
        (2026, 9)
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
        """
        Construct a naive (timezone-less) :class:`DateTime`.

        Bypasses pendulum's usual timezone resolution and calls the direct
        constructor with no ``tzinfo``, producing a wall-clock-only value.
        This is useful when interacting with systems that insist on naive
        datetimes or when performing pure arithmetic on calendar components.

        Parameters
        ----------
        year
            Calendar year.
        month
            Month in ``[1, 12]``.
        day
            Day of the month valid for ``year``/``month``.
        hour
            Hour component in ``[0, 23]``.
        minute
            Minute component in ``[0, 59]``.
        second
            Second component in ``[0, 59]``.
        microsecond
            Microsecond component in ``[0, 999_999]``.
        fold
            Disambiguates ambiguous local times during DST transitions: ``0``
            selects the earlier of two identical wall-clock values and ``1``
            the later.

        Returns
        -------
            Naive datetime with ``tzinfo`` left unset; pair with
            :meth:`pendulum.DateTime.in_timezone` or similar to localise.

        See Also
        --------
        mayutils.objects.datetime.datetime.DateTime.local : Construct with the host's local timezone.
        mayutils.objects.datetime.datetime.DateTime.from_format : Parse naive strings via a format.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> naive = DateTime.without_timezone(year=2026, month=4, day=22, hour=9)
        >>> naive.tzinfo is None
        True
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
        """
        Parse ``string`` strictly against a pendulum format pattern.

        Uses the shared :data:`FORMATTER` instance to tokenise ``string``
        according to ``fmt`` and then hands the resulting parts to
        :meth:`create`. If ``fmt`` does not supply a timezone token the
        ``tz`` argument fills in the missing offset before construction.

        Parameters
        ----------
        string
            Textual datetime to parse.
        fmt
            Pendulum format pattern (e.g. ``"YYYY-MM-DD HH:mm:ss"``) describing
            the exact layout of ``string``.
        tz
            Fallback timezone applied when ``fmt`` does not capture timezone
            information and ``string`` therefore leaves it unresolved.
        locale
            Optional locale enabling translation of locale-sensitive tokens
            such as month and weekday names.

        Returns
        -------
            Datetime produced by pendulum's formatter from the parsed fields.

        See Also
        --------
        mayutils.objects.datetime.constants.FORMATTER : Formatter backing this method.
        mayutils.objects.datetime.datetime.DateTime.parse : Permissive parsing counterpart.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> dt = DateTime.from_format("2026-04-22 09:30:00", fmt="YYYY-MM-DD HH:mm:ss")
        >>> dt.hour
        9
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
        """
        Construct a :class:`DateTime` from a POSIX timestamp.

        Interprets ``timestamp`` as seconds since the Unix epoch in UTC,
        constructs a UTC datetime from its components, and then converts to
        ``tz`` if a non-UTC timezone is requested. Fractional seconds in the
        input are preserved as microsecond precision.

        Parameters
        ----------
        timestamp
            Seconds since the Unix epoch (``1970-01-01T00:00:00Z``); fractional
            seconds are preserved as microseconds.
        tz
            Timezone in which the resulting datetime is expressed. The
            timestamp is interpreted in UTC first, then converted to ``tz``.

        Returns
        -------
            Datetime representing the same instant as ``timestamp``, expressed
            in ``tz``.

        See Also
        --------
        datetime.datetime.fromtimestamp : Stdlib primitive consulted internally.
        mayutils.objects.datetime.datetime.DateTime.from_format : Alternative textual parsing path.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> DateTime.from_timestamp(0).year
        1970
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
        """
        Extract the calendar date portion of this datetime.

        Builds a new :class:`Date` with the year, month and day of ``self``;
        clock and timezone information are discarded. This overrides
        pendulum's same-named method so callers get a mayutils :class:`Date`
        rather than a plain pendulum value.

        Returns
        -------
            Mayutils :class:`Date` with the year, month and day of this
            instance; clock and timezone information are discarded.

        See Also
        --------
        mayutils.objects.datetime.datetime.DateTime.time : Sibling decomposition for the clock portion.
        mayutils.objects.datetime.datetime.Date.to_datetime : Inverse lift from date back to datetime.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> DateTime(year=2026, month=4, day=22, hour=9, minute=30).date().day
        22
        """
        return Date(
            year=self.year,
            month=self.month,
            day=self.day,
        )

    def time(
        self,
    ) -> Time:
        """
        Extract the wall-clock time portion of this datetime.

        Builds a new :class:`Time` with the hour, minute, second and
        microsecond components of ``self``. Timezone information is dropped
        because the stdlib factory used here does not propagate ``tzinfo``.

        Returns
        -------
            Mayutils :class:`Time` with the hour, minute, second and
            microsecond of this instance; timezone information is dropped
            because the stdlib factory used here does not propagate ``tzinfo``.

        See Also
        --------
        mayutils.objects.datetime.datetime.DateTime.date : Sibling decomposition for the calendar portion.
        mayutils.objects.datetime.datetime.Time.on : Inverse bridge combining time with a date.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> DateTime(year=2026, month=4, day=22, hour=9, minute=30).time().hour
        9
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
    """
    Dispatch a datetime-ish input to the matching mayutils wrapper.

    The helper accepts either a pendulum-parseable string or an already-parsed
    pendulum/``mayutils`` value. Strings are routed through
    :func:`pendulum.parse`; the result (or the passthrough input) is then
    re-typed into :class:`DateTime`, :class:`Date` or :class:`Time` where
    applicable so downstream code can rely on the mayutils helpers.

    Parameters
    ----------
    dt
        Input value. Strings are parsed by pendulum; pendulum/mayutils dates,
        times and datetimes are rewrapped into this module's subclasses;
        :class:`pendulum.Duration` values are returned unchanged.

    Returns
    -------
        Re-typed mayutils wrapper for pendulum ``DateTime`` / ``Time`` /
        ``Date`` results; the original value is returned untouched when it is
        a :class:`pendulum.Duration` or any type pendulum yielded that does
        not fall into the three supported calendar categories.

    See Also
    --------
    mayutils.objects.datetime.datetime.DateTime.parse : Datetime-specific parser.
    mayutils.objects.datetime.datetime.Date.parse : Date-specific parser.
    mayutils.objects.datetime.datetime.Time.parse : Time-specific parser.
    pendulum.parse : Upstream permissive parser invoked internally.

    Examples
    --------
    >>> from mayutils.objects.datetime.datetime import parse, DateTime
    >>> isinstance(parse("2026-04-22T09:30:00+00:00"), DateTime)
    True
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
