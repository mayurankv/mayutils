"""Generic interval types backed by pendulum.

This module provides an :class:`Interval` class generic over :class:`Date` and
:class:`DateTime` endpoints, together with a lightweight :class:`Intervals`
container that holds an ordered, sortable collection of such intervals. The
types wrap pendulum's :class:`pendulum.Interval` to yield endpoints as the
project's own :class:`Date` / :class:`DateTime` wrappers, expose convenience
properties for slicing into pandas structures, counting weekdays/weekends, and
coercing between date-only and datetime-backed representations. A module-level
helper :func:`get_intervals` builds a rolling set of month-long intervals
anchored on a chosen day of the month.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Self, cast, overload

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from pendulum import (
        Date as PendulumDate,
    )
    from pendulum import (
        DateTime as PendulumDateTime,
    )
    from pendulum import (
        Interval as PendulumInterval,
    )

from mayutils.objects.datetime.datetime import Date, DateTime

if TYPE_CHECKING:
    from collections.abc import Iterator


class Interval[T: (Date, DateTime)](PendulumInterval[T]):
    """Interval between two :class:`Date` or :class:`DateTime` endpoints.

    A pendulum-backed interval generic in its endpoint type ``T``, which must
    be either :class:`Date` or :class:`DateTime`. Wraps
    :class:`pendulum.Interval` so that endpoint access returns the project's
    richer wrapper types, and adds coercion constructors, slice conversion,
    deep-copy semantics, and weekday/weekend accounting.

    Notes
    -----
    Instances are constructed via keyword arguments; the ``absolute`` flag, if
    set, guarantees a non-negative interval by internally tracking an
    ``_invert`` marker that is re-applied when converting back to a plain
    pendulum interval or a ``slice``.
    """

    def __new__(
        cls,
        *,
        start: T,
        end: T,
        absolute: bool = False,
    ) -> Self:
        """Allocate a new interval instance via the pendulum base constructor.

        Parameters
        ----------
        start : Date or DateTime
            Lower endpoint of the interval. Its concrete type determines the
            generic parameter ``T`` of the resulting instance.
        end : Date or DateTime
            Upper endpoint of the interval. Must share its type with ``start``
            for the generic parameter to be consistent.
        absolute : bool, default False
            When ``True`` the interval is coerced to a non-negative span,
            inverting the ordering internally if ``end`` precedes ``start``.

        Returns
        -------
        Self
            Freshly allocated interval instance with the provided endpoints
            and orientation.
        """
        return super().__new__(
            cls=cls,
            start=start,
            end=end,
            absolute=absolute,
        )

    def __init__(
        self,
        *,
        start: T,
        end: T,
        absolute: bool = False,
    ) -> None:
        """Initialise the interval by delegating to the pendulum base class.

        Parameters
        ----------
        start : Date or DateTime
            Lower endpoint of the interval, used to seed the underlying
            pendulum interval state.
        end : Date or DateTime
            Upper endpoint of the interval, used to seed the underlying
            pendulum interval state.
        absolute : bool, default False
            When ``True`` the interval is stored in absolute form so that its
            length is non-negative regardless of endpoint order.
        """
        super().__init__(
            start=start,
            end=end,
            absolute=absolute,
        )

    @classmethod
    def coercing_datetime(
        cls,
        *,
        start: DateTime | str,
        end: DateTime | str,
        absolute: bool = False,
        fmt: str | None = None,
    ) -> Interval[DateTime]:
        """Build a :class:`DateTime`-valued interval, coercing string endpoints.

        Parameters
        ----------
        start : DateTime or str
            Lower endpoint; if given as a string it is parsed into a
            :class:`DateTime` using ``fmt`` when supplied, otherwise by
            pendulum's default parsing rules.
        end : DateTime or str
            Upper endpoint; parsed identically to ``start`` when string-valued
            so that both endpoints share the same resolution.
        absolute : bool, default False
            When ``True`` the resulting interval is stored in absolute form so
            the span is non-negative irrespective of endpoint order.
        fmt : str or None, default None
            Pendulum format string controlling how string endpoints are
            parsed; ``None`` falls back to pendulum's automatic parser.

        Returns
        -------
        Interval[DateTime]
            Interval whose endpoints are guaranteed :class:`DateTime`
            instances, ready for datetime-resolution arithmetic and slicing.
        """
        return Interval[DateTime](
            start=DateTime.coerce(start, fmt=fmt),
            end=DateTime.coerce(end, fmt=fmt),
            absolute=absolute,
        )

    @classmethod
    def coercing_date(
        cls,
        *,
        start: Date | str,
        end: Date | str,
        absolute: bool = False,
    ) -> Interval[Date]:
        """Build a :class:`Date`-valued interval, coercing string endpoints.

        Parameters
        ----------
        start : Date or str
            Lower endpoint; strings are parsed into a :class:`Date` via the
            wrapper's standard coercion rules, while :class:`Date` inputs are
            passed through unchanged.
        end : Date or str
            Upper endpoint; parsed identically to ``start`` so that both
            endpoints are aligned at day resolution.
        absolute : bool, default False
            When ``True`` the resulting interval is stored in absolute form so
            that its length is non-negative regardless of endpoint order.

        Returns
        -------
        Interval[Date]
            Interval whose endpoints are guaranteed :class:`Date` instances,
            dropping any intraday resolution from the inputs.
        """
        return Interval[Date](
            start=Date.coerce(start),
            end=Date.coerce(end),
            absolute=absolute,
        )

    @staticmethod
    def promote_pendulum(
        instance: PendulumDate | PendulumDateTime | Date | DateTime,
        /,
    ) -> T:
        """Promote a pendulum or wrapper instance to the project's wrapper type.

        Parameters
        ----------
        instance : PendulumDate, PendulumDateTime, Date, or DateTime
            Endpoint value to be normalised; already-wrapped inputs are
            returned unchanged while bare pendulum values are lifted into the
            matching :class:`Date` or :class:`DateTime` wrapper.

        Returns
        -------
        T
            The endpoint re-expressed as the project's wrapper type,
            preserving the resolution (date vs datetime) of the input.
        """
        if isinstance(instance, DateTime):
            return cast("T", instance)
        if isinstance(instance, PendulumDateTime):
            return cast("T", DateTime.from_pendulum(instance))
        if isinstance(instance, Date):
            return cast("T", instance)

        return cast("T", Date.from_pendulum(instance))

    @classmethod
    def from_pendulum(
        cls,
        base: PendulumInterval[T],
        /,
    ) -> Self:
        """Construct a wrapped interval from a plain pendulum interval.

        Parameters
        ----------
        base : PendulumInterval
            Source pendulum interval whose endpoints and orientation are
            mirrored; its internal inversion and absolute flags are honoured
            so that the resulting interval preserves the same directionality.

        Returns
        -------
        Self
            New wrapped interval with endpoints promoted to the project's
            wrapper types and ordering consistent with ``base``.
        """
        start = cls.promote_pendulum(base.start)
        end = cls.promote_pendulum(base.end)

        return cls(
            start=start if not base._invert else end,  # noqa: SLF001
            end=end if not base._invert else start,  # noqa: SLF001
            absolute=base._absolute,  # noqa: SLF001
        )

    @property
    def start(
        self,
    ) -> T:
        """Return the start endpoint using the project's wrapper types.

        Returns
        -------
        T
            The interval's lower endpoint promoted to a :class:`Date` or
            :class:`DateTime` instance as appropriate.
        """
        return self.__class__.promote_pendulum(super().start)

    @property
    def end(
        self,
    ) -> T:
        """Return the end endpoint using the project's wrapper types.

        Returns
        -------
        T
            The interval's upper endpoint promoted to a :class:`Date` or
            :class:`DateTime` instance as appropriate.
        """
        return self.__class__.promote_pendulum(super().end)

    @property
    def absolute(
        self,
    ) -> bool:
        """Indicate whether the interval is stored in absolute form.

        Returns
        -------
        bool
            ``True`` when the interval was constructed with ``absolute=True``
            and therefore guarantees a non-negative span; ``False`` otherwise.
        """
        return self._absolute

    @property
    def inverted(
        self,
    ) -> bool:
        """Indicate whether the stored endpoint order was inverted.

        Returns
        -------
        bool
            ``True`` when the underlying pendulum interval swapped the
            original ``start`` and ``end`` to satisfy ``absolute=True``;
            ``False`` when the endpoints are in their supplied order.
        """
        return self._invert or False

    def __deepcopy__(
        self,
        memo: dict[int, Any],
    ) -> Self:
        """Produce a deep copy of the interval, duplicating both endpoints.

        Parameters
        ----------
        memo : dict of int to Any
            Memoisation mapping supplied by :func:`copy.deepcopy` to track
            already-copied objects and break cycles; forwarded verbatim to
            each endpoint's deep copy.

        Returns
        -------
        Self
            Independent interval whose endpoints are deep copies of the
            originals while retaining the same absolute/inverted semantics.
        """
        return self.__class__(
            start=deepcopy(x=self.start, memo=memo),
            end=deepcopy(x=self.end, memo=memo),
            absolute=self._absolute,
        )

    def count_weekdays(
        self,
    ) -> tuple[int, int]:
        """Count the weekday and weekend days spanned by the interval.

        Iterates day-by-day across the interval and classifies each date as a
        weekend (Saturday/Sunday) or weekday according to pendulum's
        ``is_weekend`` semantics.

        Returns
        -------
        tuple of (int, int)
            Pair ``(weekdays, weekends)`` giving the number of Monday-to-Friday
            days and the number of Saturday/Sunday days contained in the
            interval respectively.
        """
        weekends = 0
        weekdays = 0

        for dt in self.range(unit="days"):
            if dt.is_weekend():
                weekends += 1
            else:
                weekdays += 1

        return weekdays, weekends

    @property
    def weekends(
        self,
    ) -> int:
        """Report the number of weekend days contained in the interval.

        Returns
        -------
        int
            Count of Saturday and Sunday days spanned by the interval, as
            determined by :meth:`count_weekdays`.
        """
        _, weekends = self.count_weekdays()

        return weekends

    @property
    def weekdays(
        self,
    ) -> int:
        """Report the number of weekdays contained in the interval.

        Returns
        -------
        int
            Count of Monday-to-Friday days spanned by the interval, as
            determined by :meth:`count_weekdays`.
        """
        weekdays, _ = self.count_weekdays()

        return weekdays

    def to_date_interval(
        self,
    ) -> Interval[Date]:
        """Project the interval onto :class:`Date` endpoints.

        Datetime-valued endpoints are truncated to their calendar date, while
        already-date endpoints are re-used as-is. The absolute-form flag is
        carried over unchanged.

        Returns
        -------
        Interval[Date]
            Interval whose endpoints share the same calendar dates as the
            original but discard any intraday component.
        """
        if isinstance(self.start, DateTime) and isinstance(self.end, DateTime):
            return Interval.coercing_date(
                start=self.start.date(),
                end=self.end.date(),
                absolute=self._absolute,
            )

        return Interval.coercing_date(
            start=cast("Date", self.start),
            end=cast("Date", self.end),
            absolute=self._absolute,
        )

    def to_datetime_interval(
        self,
    ) -> Interval[DateTime]:
        """Lift the interval onto :class:`DateTime` endpoints.

        Already-datetime endpoints are reused unchanged, while date-valued
        endpoints are promoted to datetimes via the wrapper's
        :meth:`Date.to_datetime`. The absolute-form flag is preserved.

        Returns
        -------
        Interval[DateTime]
            Interval whose endpoints are full :class:`DateTime` instances,
            suitable for arithmetic and slicing at sub-daily resolution.
        """
        if isinstance(self.start, DateTime) and isinstance(self.end, DateTime):
            return Interval.coercing_datetime(
                start=self.start,
                end=self.end,
                absolute=self._absolute,
            )

        return Interval.coercing_datetime(
            start=cast("Date", self.start).to_datetime(),
            end=cast("Date", self.end).to_datetime(),
            absolute=self._absolute,
        )

    @property
    def as_pendulum(
        self,
    ) -> PendulumInterval[PendulumDate]:
        """Return a plain pendulum interval mirroring this wrapped instance.

        Both endpoints are unwrapped back to their underlying pendulum types
        and the absolute-form flag is propagated so downstream pendulum code
        observes the same orientation.

        Returns
        -------
        PendulumInterval[T]
            Pendulum-native interval equivalent to ``self``, stripped of the
            project's wrapper types.
        """
        return PendulumInterval(
            start=self.start.as_pendulum,
            end=self.end.as_pendulum,
            absolute=self._absolute,
        )

    @property
    def as_slice(
        self,
    ) -> slice:
        """Return a builtin ``slice`` spanning the interval for pandas indexing.

        The slice uses the plain-python base representation of each endpoint
        (``start.as_base`` / ``end.as_base``) so that it can be passed to
        ``pandas`` label-based indexing such as ``.loc``. If the interval is
        internally inverted, the slice bounds are swapped so that the
        resulting slice always runs from earlier to later in storage order.

        Returns
        -------
        slice
            Slice object whose start and stop are the interval's endpoints in
            their native (non-wrapper) representation.
        """
        return (
            slice(
                self.start.as_base,
                self.end.as_base,
            )
            if not self._invert
            else slice(
                self.end.as_base,
                self.start.as_base,
            )
        )

    def __str__(
        self,
    ) -> str:
        """Render the interval as a human-readable ``"start to end"`` string.

        Returns
        -------
        str
            Readable string combining the start and end endpoints using their
            own string representations separated by ``" to "``.
        """
        return f"{self.start} to {self.end}"


class Intervals[T: (Date, DateTime)]:
    """Ordered collection of :class:`Interval` values sharing an endpoint type.

    Stores any number of :class:`Interval` instances in a tuple that is kept
    sorted by ``(start, end)``. Supports iteration, ``len``, and integer or
    slice indexing; indexing with a slice yields another :class:`Intervals`
    instance while integer indexing yields the underlying interval.
    """

    def __init__(
        self,
        *intervals: Interval[T],
    ) -> None:
        """Initialise the collection with a variadic tuple of intervals.

        Parameters
        ----------
        *intervals : Interval[T]
            Intervals to store; all must share the same endpoint type ``T``.
            The supplied ordering is not preserved as the constructor
            immediately calls :meth:`sort` to canonicalise the layout.
        """
        self.intervals = intervals
        self.sort()

    def sort(
        self,
    ) -> Self:
        """Sort the contained intervals in place by their endpoints.

        Intervals are ordered lexicographically by the tuple
        ``(interval.start, interval.end)``, so that earlier starts come first
        and ties are broken by the earlier end.

        Returns
        -------
        Self
            The same :class:`Intervals` instance (now holding a reordered
            tuple) to enable method chaining.
        """
        self.intervals = tuple(
            sorted(
                self.intervals,
                key=lambda interval: (
                    interval.start,
                    interval.end,
                ),
            ),
        )

        return self

    def __repr__(
        self,
    ) -> str:
        r"""Render a multiline debug representation listing each interval.

        Returns
        -------
        str
            String of the form ``"Intervals(\\n\\t<repr1>\\n\\t<repr2>...\\n)"``
            combining the ``repr`` of each contained interval on its own
            indented line for readable inspection.
        """
        return f"Intervals(\n\t{'\n\t'.join([repr(interval) for interval in self.intervals])}\n)"

    def __iter__(
        self,
    ) -> Iterator[Interval[T]]:
        """Iterate over the contained intervals in stored (sorted) order.

        Returns
        -------
        Iterator[Interval[T]]
            Fresh iterator yielding each :class:`Interval` in ``(start, end)``
            order as previously canonicalised by :meth:`sort`.
        """
        return iter(self.intervals)

    def __len__(
        self,
    ) -> int:
        """Return the number of intervals stored in the collection.

        Returns
        -------
        int
            Count of :class:`Interval` instances currently held.
        """
        return len(self.intervals)

    @overload
    def __getitem__(
        self,
        key: int,
    ) -> Interval[T]: ...

    @overload
    def __getitem__(
        self,
        key: slice,
    ) -> Intervals[T]: ...

    def __getitem__(
        self,
        key: int | slice,
    ) -> Intervals[T] | Interval[T]:
        """Index into the sorted collection by integer position or slice.

        Parameters
        ----------
        key : int or slice
            Integer position selecting a single :class:`Interval` from the
            underlying sorted tuple, or a slice selecting a contiguous run
            and producing a new :class:`Intervals` wrapper around the result.

        Returns
        -------
        Interval[T] or Intervals[T]
            The single :class:`Interval` at ``key`` for integer indexing, or a
            new :class:`Intervals` instance holding the sliced subset when
            ``key`` is a :class:`slice`.
        """
        if isinstance(key, slice):
            return Intervals(*self.intervals[key])

        return self.intervals[key]


def get_intervals(
    dt: DateTime | None,
    /,
    *,
    num_periods: int = 13,
    day: int | None = None,
    absolute_interval: bool = False,
) -> Intervals[DateTime]:
    """Build a rolling set of month-long intervals anchored on a day of month.

    Each returned interval starts on ``day`` of some month and ends on
    ``day`` of the following month; the sequence ends at the interval
    covering the month immediately preceding ``dt`` and extends
    ``num_periods`` steps back in time.

    Parameters
    ----------
    dt : DateTime or None
        Reference datetime marking the upper edge of the most recent
        interval. When ``None`` the function substitutes :meth:`DateTime.today`
        so callers can omit an explicit anchor.
    num_periods : int, default 13
        Number of consecutive month-long intervals to generate, counted back
        from the reference; controls the total historical span covered.
    day : int or None, default None
        Day-of-month used to anchor each interval boundary. ``None`` falls
        back to ``dt.day`` so the window preserves the reference's own day.
    absolute_interval : bool, default False
        Forwarded to each :class:`Interval` constructor; when ``True`` each
        generated interval is stored in absolute (non-negative) form.

    Returns
    -------
    Intervals[DateTime]
        Sorted collection of ``num_periods`` consecutive month-long
        :class:`DateTime`-valued intervals ending at the month containing
        ``dt``.
    """
    if dt is None:
        dt = DateTime.today()

    return Intervals(
        *[
            Interval(
                start=dt.subtract(months=idx).set(day=day if day is not None else dt.day),
                end=dt.subtract(months=idx - 1).set(day=day if day is not None else dt.day),
                absolute=absolute_interval,
            )
            for idx in range(num_periods, 0, -1)
        ]
    )
