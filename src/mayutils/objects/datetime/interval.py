"""
Provide generic interval types backed by pendulum.

This module offers an :class:`Interval` class generic over :class:`Date` and
:class:`DateTime` endpoints, together with a lightweight :class:`Intervals`
container that holds an ordered, sortable collection of such intervals. The
types wrap pendulum's :class:`pendulum.Interval` to yield endpoints as the
project's own :class:`Date` / :class:`DateTime` wrappers, expose convenience
properties for slicing into pandas structures, counting weekdays/weekends, and
coercing between date-only and datetime-backed representations. A module-level
helper :func:`get_intervals` builds a rolling set of month-long intervals
anchored on a chosen day of the month.

See Also
--------
Interval : Wrapper around :class:`pendulum.Interval` with richer endpoints.
Intervals : Sorted collection of :class:`Interval` instances.
get_intervals : Build a rolling sequence of month-long intervals.
pendulum.Interval : Underlying pendulum interval that this module extends.

Examples
--------
>>> from mayutils.objects.datetime.datetime import Date
>>> from mayutils.objects.datetime.interval import Interval
>>> interval = Interval.coercing_date(start="2024-01-01", end="2024-01-31")
>>> isinstance(interval.start, Date)
True
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Self, cast, overload

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from pendulum import Interval as PendulumInterval

from mayutils.objects.datetime.datetime import Date, DateTime

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from pendulum import Date as PendulumDate
    from pendulum import DateTime as PendulumDateTime


class Interval[IntervalType: (Date, DateTime)](PendulumInterval[IntervalType]):
    """
    Represent an interval between two :class:`Date` or :class:`DateTime` endpoints.

    A pendulum-backed interval generic in its endpoint type ``T``, which must
    be either :class:`Date` or :class:`DateTime`. Wraps
    :class:`pendulum.Interval` so that endpoint access returns the project's
    richer wrapper types, and adds coercion constructors, slice conversion,
    deep-copy semantics, and weekday/weekend accounting. The closed interval
    [start, end] is retained as stored; orientation may be optionally inverted
    when the caller opts into absolute (non-negative) form.

    Parameters
    ----------
    start
        Lower (inclusive) endpoint of the interval; its concrete type
        determines the generic parameter ``T`` of the resulting instance.
    end
        Upper (inclusive) endpoint of the interval, which must share its type
        with ``start`` for the generic parameter to be consistent.
    absolute
        When ``True`` the interval is coerced to a non-negative span, so that
        ``end`` precedes ``start`` it is silently swapped and the original
        orientation recorded via an internal inversion flag.

    See Also
    --------
    Intervals : Sorted collection of :class:`Interval` instances.
    pendulum.Interval : The underlying pendulum interval class being extended.
    Interval.coercing_date : Construct a :class:`Date`-valued interval.
    Interval.coercing_datetime : Construct a :class:`DateTime`-valued interval.

    Notes
    -----
    Instances are constructed via keyword arguments; the ``absolute`` flag, if
    set, guarantees a non-negative interval by internally tracking an
    ``_invert`` marker that is re-applied when converting back to a plain
    pendulum interval or a ``slice``.

    Examples
    --------
    >>> from mayutils.objects.datetime.datetime import Date
    >>> from mayutils.objects.datetime.interval import Interval
    >>> interval = Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31))
    >>> str(interval)
    '2024-01-01 to 2024-01-31'
    """

    def __new__(
        cls,
        *,
        start: IntervalType,
        end: IntervalType,
        absolute: bool = False,
    ) -> Self:
        """
        Allocate a new interval instance via the pendulum base constructor.

        Delegates to :meth:`PendulumInterval.__new__` with the supplied
        endpoints and orientation flag so the base class performs its own
        duration computation and inversion bookkeeping. The returned instance
        is subsequently initialised through :meth:`__init__`.

        Parameters
        ----------
        start
            Lower endpoint of the interval. Its concrete type determines the
            generic parameter ``T`` of the resulting instance.
        end
            Upper endpoint of the interval. Must share its type with ``start``
            for the generic parameter to be consistent.
        absolute
            When ``True`` the interval is coerced to a non-negative span,
            inverting the ordering internally if ``end`` precedes ``start``.

        Returns
        -------
            Freshly allocated interval instance with the provided endpoints
            and orientation.

        See Also
        --------
        Interval.__init__ : Companion initialiser invoked after allocation.
        pendulum.Interval.__new__ : Underlying pendulum allocator delegated to.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31)).days
        30
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
        start: IntervalType,
        end: IntervalType,
        absolute: bool = False,
    ) -> None:
        """
        Initialise the interval by delegating to the pendulum base class.

        Forwards the endpoint pair and absolute flag to
        :meth:`PendulumInterval.__init__` so that pendulum populates its
        internal duration cache and inversion metadata. No additional
        instance state is introduced by this wrapper.

        Parameters
        ----------
        start
            Lower endpoint of the interval, used to seed the underlying
            pendulum interval state.
        end
            Upper endpoint of the interval, used to seed the underlying
            pendulum interval state.
        absolute
            When ``True`` the interval is stored in absolute form so that its
            length is non-negative regardless of endpoint order.

        See Also
        --------
        Interval.__new__ : Allocator paired with this initialiser.
        pendulum.Interval.__init__ : Underlying pendulum initialiser delegated to.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> interval = Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31))
        >>> interval.absolute
        False
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
        """
        Build a :class:`DateTime`-valued interval, coercing string endpoints.

        Strings are routed through :meth:`DateTime.coerce`, which uses
        pendulum's parser (optionally guided by ``fmt``) to produce
        timezone-aware datetimes at the project's preferred resolution. This
        keeps callers free to pass ISO-8601 literals or pre-built
        :class:`DateTime` values interchangeably.

        Parameters
        ----------
        start
            Lower endpoint; if given as a string it is parsed into a
            :class:`DateTime` using ``fmt`` when supplied, otherwise by
            pendulum's default parsing rules.
        end
            Upper endpoint; parsed identically to ``start`` when string-valued
            so that both endpoints share the same resolution.
        absolute
            When ``True`` the resulting interval is stored in absolute form so
            the span is non-negative irrespective of endpoint order.
        fmt
            Pendulum format string controlling how string endpoints are
            parsed; ``None`` falls back to pendulum's automatic parser.

        Returns
        -------
            Interval whose endpoints are guaranteed :class:`DateTime`
            instances, ready for datetime-resolution arithmetic and slicing.

        See Also
        --------
        Interval.coercing_date : Date-resolution counterpart of this helper.
        DateTime.coerce : Coercion utility used on string endpoints.
        Interval.to_datetime_interval : Lift an existing interval to datetime.

        Examples
        --------
        >>> from mayutils.objects.datetime.interval import Interval
        >>> interval = Interval.coercing_datetime(
        ...     start="2024-01-01T00:00:00",
        ...     end="2024-01-31T00:00:00",
        ... )
        >>> interval.days
        30
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
        """
        Build a :class:`Date`-valued interval, coercing string endpoints.

        Strings are parsed via :meth:`Date.coerce`, which truncates any
        intraday component so the resulting interval operates purely at
        calendar-day resolution. Already-parsed :class:`Date` values pass
        through unchanged, preserving identity where useful.

        Parameters
        ----------
        start
            Lower endpoint; strings are parsed into a :class:`Date` via the
            wrapper's standard coercion rules, while :class:`Date` inputs are
            passed through unchanged.
        end
            Upper endpoint; parsed identically to ``start`` so that both
            endpoints are aligned at day resolution.
        absolute
            When ``True`` the resulting interval is stored in absolute form so
            that its length is non-negative regardless of endpoint order.

        Returns
        -------
            Interval whose endpoints are guaranteed :class:`Date` instances,
            dropping any intraday resolution from the inputs.

        See Also
        --------
        Interval.coercing_datetime : Datetime-resolution counterpart.
        Date.coerce : Coercion utility used on string endpoints.
        Interval.to_date_interval : Project an existing interval to dates.

        Examples
        --------
        >>> from mayutils.objects.datetime.interval import Interval
        >>> interval = Interval.coercing_date(start="2024-01-01", end="2024-01-31")
        >>> interval.days
        30
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
    ) -> IntervalType:
        """
        Promote a pendulum or wrapper instance to the project's wrapper type.

        Dispatches on the runtime type of the input so that bare pendulum
        values are lifted through :meth:`DateTime.from_pendulum` or
        :meth:`Date.from_pendulum`, while inputs that are already project
        wrappers are returned unchanged. This enables the interval properties
        to present consistent wrapper-typed endpoints regardless of how the
        base :class:`pendulum.Interval` stored them.

        Parameters
        ----------
        instance
            Endpoint value to be normalised; already-wrapped inputs are
            returned unchanged while bare pendulum values are lifted into the
            matching :class:`Date` or :class:`DateTime` wrapper.

        Returns
        -------
            The endpoint re-expressed as the project's wrapper type,
            preserving the resolution (date vs datetime) of the input.

        See Also
        --------
        Date.from_pendulum : Lift a :class:`pendulum.Date` into the wrapper.
        DateTime.from_pendulum : Lift a :class:`pendulum.DateTime` into the wrapper.
        Interval.from_pendulum : Whole-interval counterpart of this helper.

        Examples
        --------
        >>> from pendulum import Date as PendulumDate
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> promoted = Interval.promote_pendulum(PendulumDate(2024, 1, 1))
        >>> isinstance(promoted, Date)
        True
        """
        with may_require_extras():
            from pendulum import DateTime as PendulumDateTime

        if isinstance(instance, DateTime):
            return cast("IntervalType", instance)
        if isinstance(instance, PendulumDateTime):
            return cast("IntervalType", DateTime.from_pendulum(instance))
        if isinstance(instance, Date):
            return cast("IntervalType", instance)

        return cast("IntervalType", Date.from_pendulum(instance))

    @classmethod
    def from_pendulum(
        cls,
        base: PendulumInterval[IntervalType],
        /,
    ) -> Self:
        """
        Construct a wrapped interval from a plain pendulum interval.

        Reads pendulum's internal ``_invert`` and ``_absolute`` flags so that
        the resulting wrapper preserves both the original endpoint ordering
        and the absolute-form behaviour. Endpoints are promoted via
        :meth:`promote_pendulum` so the wrapper surface is consistent with
        intervals created directly from :class:`Date` or :class:`DateTime`.

        Parameters
        ----------
        base
            Source pendulum interval whose endpoints and orientation are
            mirrored; its internal inversion and absolute flags are honoured
            so that the resulting interval preserves the same directionality.

        Returns
        -------
            New wrapped interval with endpoints promoted to the project's
            wrapper types and ordering consistent with ``base``.

        See Also
        --------
        Interval.promote_pendulum : Endpoint-level promotion helper used here.
        Interval.as_pendulum : Inverse conversion back to a pendulum interval.
        pendulum.Interval : Source type accepted by this constructor.

        Examples
        --------
        >>> from pendulum import Date as PendulumDate
        >>> from pendulum import Interval as PendulumInterval
        >>> from mayutils.objects.datetime.interval import Interval
        >>> base = PendulumInterval(start=PendulumDate(2024, 1, 1), end=PendulumDate(2024, 1, 31))
        >>> Interval.from_pendulum(base).days
        30
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
    ) -> IntervalType:
        """
        Return the start endpoint using the project's wrapper types.

        Delegates to the base-class ``start`` attribute and promotes the
        resulting value via :meth:`promote_pendulum`. This keeps the public
        property aligned with wrapper types even when the underlying pendulum
        storage holds raw :class:`pendulum.Date` or :class:`pendulum.DateTime`
        instances.

        Returns
        -------
            The interval's lower endpoint promoted to a :class:`Date` or
            :class:`DateTime` instance as appropriate.

        See Also
        --------
        Interval.end : Companion property yielding the upper endpoint.
        Interval.promote_pendulum : Helper performing the wrapper promotion.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> interval = Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31))
        >>> interval.start == Date(2024, 1, 1)
        True
        """
        return self.__class__.promote_pendulum(super().start)

    @property
    def end(
        self,
    ) -> IntervalType:
        """
        Return the end endpoint using the project's wrapper types.

        Delegates to the base-class ``end`` attribute and promotes the
        returned value through :meth:`promote_pendulum` so the property
        always yields the project's wrapper types regardless of how pendulum
        stored the underlying endpoint.

        Returns
        -------
            The interval's upper endpoint promoted to a :class:`Date` or
            :class:`DateTime` instance as appropriate.

        See Also
        --------
        Interval.start : Companion property yielding the lower endpoint.
        Interval.promote_pendulum : Helper performing the wrapper promotion.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> interval = Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31))
        >>> interval.end == Date(2024, 1, 31)
        True
        """
        return self.__class__.promote_pendulum(super().end)

    @property
    def absolute(
        self,
    ) -> bool:
        """
        Indicate whether the interval is stored in absolute form.

        Surfaces pendulum's private ``_absolute`` attribute as a read-only
        property so callers can inspect whether the interval was constructed
        with ``absolute=True``. Absolute intervals guarantee a non-negative
        duration at the cost of losing the original orientation.

        Returns
        -------
            ``True`` when the interval was constructed with ``absolute=True``
            and therefore guarantees a non-negative span; ``False`` otherwise.

        See Also
        --------
        Interval.inverted : Companion flag indicating if endpoints were swapped.
        Interval.__new__ : Constructor accepting the ``absolute`` keyword.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31), absolute=True).absolute
        True
        """
        return self._absolute

    @property
    def inverted(
        self,
    ) -> bool:
        """
        Indicate whether the stored endpoint order was inverted.

        Exposes pendulum's private ``_invert`` flag so callers can detect
        whether the underlying interval silently swapped ``start`` and
        ``end``. This is only meaningful when ``absolute=True`` was used at
        construction time.

        Returns
        -------
            ``True`` when the underlying pendulum interval swapped the
            original ``start`` and ``end`` to satisfy ``absolute=True``;
            ``False`` when the endpoints are in their supplied order.

        See Also
        --------
        Interval.absolute : Indicates whether absolute form was requested.
        Interval.as_slice : Uses the inverted flag to reorder slice bounds.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> interval = Interval(start=Date(2024, 1, 31), end=Date(2024, 1, 1), absolute=True)
        >>> interval.inverted
        True
        """
        return self._invert or False

    def __deepcopy__(
        self,
        memo: Mapping[int, object],
    ) -> Self:
        """
        Produce a deep copy of the interval, duplicating both endpoints.

        Forwards the memoisation mapping to :func:`copy.deepcopy` for each
        endpoint so cyclic references inside custom wrappers are handled
        correctly. The returned interval carries over the absolute flag from
        the original so the directionality semantics are preserved.

        Parameters
        ----------
        memo
            Memoisation mapping supplied by :func:`copy.deepcopy` to track
            already-copied objects and break cycles; forwarded verbatim to
            each endpoint's deep copy.

        Returns
        -------
            Independent interval whose endpoints are deep copies of the
            originals while retaining the same absolute/inverted semantics.

        See Also
        --------
        copy.deepcopy : Standard-library entry point that invokes this hook.
        Interval.__new__ : Constructor used to rebuild the copied instance.

        Examples
        --------
        >>> from copy import deepcopy
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> original = Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31))
        >>> deepcopy(original).days
        30
        """
        start = deepcopy(x=self.start, memo=dict(memo))
        end = deepcopy(x=self.end, memo=dict(memo))

        return self.__class__(
            start=start if not self._invert else end,
            end=end if not self._invert else start,
            absolute=self._absolute,
        )

    def __hash__(
        self,
    ) -> int:
        """
        Hash the interval using the endpoint type name and both endpoint values.

        Constructs a key tuple of ``(type(self.start).__name__, self.start,
        self.end)`` and forwards it to the builtin :func:`hash`. Including the
        runtime class name of the start endpoint ensures that date-backed and
        datetime-backed intervals with otherwise identical boundary values do not
        collide in hash tables.

        Returns
        -------
            Integer hash derived from the start-type name and both endpoints.

        See Also
        --------
        Interval.__eq__ : Equality check whose contract is paired with this hash.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> interval = Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31))
        >>> isinstance(hash(interval), int)
        True
        """
        return hash((type(self.start).__name__, self.start, self.end))

    def __eq__(
        self,
        other: object,
    ) -> bool:
        """
        Test structural equality between two intervals of the same type.

        Compares the runtime class name of the start endpoint together with both
        ``start`` and ``end`` values so that a date-backed interval never
        compares equal to a datetime-backed interval with the same calendar
        boundaries. Returns :data:`NotImplemented` when ``other`` is not an
        instance of the same concrete type, delegating further comparison to the
        opposite operand.

        Parameters
        ----------
        other
            Object to compare against; equality is only evaluated when ``other``
            is an instance of the exact same runtime type as ``self``.

        Returns
        -------
            ``True`` when ``other`` is the same type and has identical ``start``
            and ``end`` values at the same resolution; ``False`` otherwise.

        See Also
        --------
        Interval.__hash__ : Hash function whose contract is paired with this method.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> a = Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31))
        >>> b = Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31))
        >>> a == b
        True
        """
        if not isinstance(other, type(self)):
            return NotImplemented

        return (type(self.start).__name__, self.start, self.end) == (type(other.start).__name__, other.start, other.end)

    def count_weekdays(
        self,
    ) -> tuple[int, int]:
        """
        Count the weekday and weekend days spanned by the interval.

        Iterates day-by-day across the interval and classifies each date as a
        weekend (Saturday/Sunday) or weekday according to pendulum's
        ``is_weekend`` semantics. The walk uses ``self.range(unit="days")``
        so both endpoints are treated inclusively at calendar-day resolution.

        Returns
        -------
            Pair ``(weekdays, weekends)`` giving the number of Monday-to-Friday
            days and the number of Saturday/Sunday days contained in the
            interval respectively.

        See Also
        --------
        Interval.weekdays : Convenience property returning just the weekday count.
        Interval.weekends : Convenience property returning just the weekend count.
        pendulum.Date.is_weekend : Predicate used to classify each day.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> weekdays, weekends = Interval(
        ...     start=Date(2024, 1, 1),
        ...     end=Date(2024, 1, 7),
        ... ).count_weekdays()
        >>> (weekdays, weekends)
        (5, 2)
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
        """
        Report the number of weekend days contained in the interval.

        Delegates to :meth:`count_weekdays` and discards the weekday
        component, providing a cheap named accessor for the common case of
        only needing the weekend total. The count is inclusive of both
        endpoints.

        Returns
        -------
            Count of Saturday and Sunday days spanned by the interval, as
            determined by :meth:`count_weekdays`.

        See Also
        --------
        Interval.weekdays : Symmetric property returning the weekday count.
        Interval.count_weekdays : Underlying helper computing both totals.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 7)).weekends
        2
        """
        _, weekends = self.count_weekdays()

        return weekends

    @property
    def weekdays(
        self,
    ) -> int:
        """
        Report the number of weekdays contained in the interval.

        Delegates to :meth:`count_weekdays` and discards the weekend
        component so callers who only need the Monday-to-Friday total can
        avoid an explicit tuple unpack. The count is inclusive of both
        endpoints.

        Returns
        -------
            Count of Monday-to-Friday days spanned by the interval, as
            determined by :meth:`count_weekdays`.

        See Also
        --------
        Interval.weekends : Symmetric property returning the weekend count.
        Interval.count_weekdays : Underlying helper computing both totals.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 7)).weekdays
        5
        """
        weekdays, _ = self.count_weekdays()

        return weekdays

    def to_date_interval(
        self,
    ) -> Interval[Date]:
        """
        Project the interval onto :class:`Date` endpoints.

        Datetime-valued endpoints are truncated to their calendar date via
        :meth:`DateTime.date`, while already-date endpoints are re-used as-is
        through an explicit cast. The absolute-form flag is carried over
        unchanged so downstream directionality semantics are preserved.

        Returns
        -------
            Interval whose endpoints share the same calendar dates as the
            original but discard any intraday component.

        See Also
        --------
        Interval.to_datetime_interval : Counterpart promoting to datetime endpoints.
        Interval.coercing_date : Low-level constructor used internally.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> from mayutils.objects.datetime.interval import Interval
        >>> datetime_interval = Interval.coercing_datetime(
        ...     start="2024-01-01T12:00:00",
        ...     end="2024-01-31T12:00:00",
        ... )
        >>> datetime_interval.to_date_interval().days
        30
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
        """
        Lift the interval onto :class:`DateTime` endpoints.

        Already-datetime endpoints are reused unchanged, while date-valued
        endpoints are promoted to datetimes via :meth:`Date.to_datetime`,
        which attaches the project's default timezone at midnight. The
        absolute-form flag is preserved so orientation semantics survive the
        conversion.

        Returns
        -------
            Interval whose endpoints are full :class:`DateTime` instances,
            suitable for arithmetic and slicing at sub-daily resolution.

        See Also
        --------
        Interval.to_date_interval : Counterpart projecting to date endpoints.
        Interval.coercing_datetime : Low-level constructor used internally.

        Examples
        --------
        >>> from mayutils.objects.datetime.interval import Interval
        >>> date_interval = Interval.coercing_date(start="2024-01-01", end="2024-01-31")
        >>> date_interval.to_datetime_interval().days
        30
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
        """
        Return a plain pendulum interval mirroring this wrapped instance.

        Both endpoints are unwrapped back to their underlying pendulum types
        through ``as_pendulum`` and the absolute-form flag is propagated so
        downstream pendulum code observes the same orientation. Use this when
        interoperating with libraries that type-check against
        :class:`pendulum.Interval` directly.

        Returns
        -------
            Pendulum-native interval equivalent to ``self``, stripped of the
            project's wrapper types.

        See Also
        --------
        Interval.from_pendulum : Inverse constructor lifting a pendulum interval.
        Interval.as_slice : Alternative projection for pandas label indexing.

        Examples
        --------
        >>> from pendulum import Interval as PendulumInterval
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> interval = Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31))
        >>> isinstance(interval.as_pendulum, PendulumInterval)
        True
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
        """
        Return a builtin ``slice`` spanning the interval for pandas indexing.

        The slice uses the plain-python base representation of each endpoint
        (``start.as_base`` / ``end.as_base``) so that it can be passed to
        ``pandas`` label-based indexing such as ``.loc``. If the interval is
        internally inverted, the slice bounds are swapped so that the
        resulting slice always runs from earlier to later in storage order.

        Returns
        -------
            Slice object whose start and stop are the interval's endpoints in
            their native (non-wrapper) representation.

        See Also
        --------
        Interval.as_pendulum : Alternative unwrapping returning a pendulum interval.
        pandas.DataFrame.loc : Typical consumer of the returned slice.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> interval = Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31))
        >>> isinstance(interval.as_slice, slice)
        True
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
        """
        Render the interval as a human-readable ``"start to end"`` string.

        Uses each endpoint's own ``__str__`` so the resulting string inherits
        whatever formatting (ISO for plain dates, ISO-with-timezone for
        datetimes) the wrapper types apply. Primarily intended for logging
        and debugging output.

        Returns
        -------
            Readable string combining the start and end endpoints using their
            own string representations separated by ``" to "``.

        See Also
        --------
        Intervals.__repr__ : Collection-level representation that nests these strings.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval
        >>> str(Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31)))
        '2024-01-01 to 2024-01-31'
        """
        return f"{self.start} to {self.end}"


class Intervals[IntervalType: (Date, DateTime)]:
    """
    Store an ordered collection of :class:`Interval` values sharing an endpoint type.

    Stores any number of :class:`Interval` instances in a tuple that is kept
    sorted by ``(start, end)``. Supports iteration, ``len``, and integer or
    slice indexing; indexing with a slice yields another :class:`Intervals`
    instance while integer indexing yields the underlying interval. The
    collection is immutable from the outside apart from :meth:`sort`.

    Parameters
    ----------
    *intervals
        Intervals to store in the collection; all must share the same endpoint
        type ``T`` and are passed variadically so call sites read naturally.

    See Also
    --------
    Interval : Individual interval element stored in this container.
    get_intervals : Factory returning a pre-populated :class:`Intervals`.

    Examples
    --------
    >>> from mayutils.objects.datetime.datetime import Date
    >>> from mayutils.objects.datetime.interval import Interval, Intervals
    >>> collection = Intervals(
    ...     Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31)),
    ...     Interval(start=Date(2024, 2, 1), end=Date(2024, 2, 29)),
    ... )
    >>> len(collection)
    2
    """

    def __init__(
        self,
        *intervals: Interval[IntervalType],
    ) -> None:
        """
        Initialise the collection with a variadic tuple of intervals.

        Stores the supplied intervals in a tuple and immediately calls
        :meth:`sort` so the canonical ordering (by ``(start, end)``) is
        established before any indexing or iteration occurs. Callers may
        therefore pass intervals in any order.

        Parameters
        ----------
        *intervals
            Intervals to store; all must share the same endpoint type ``T``.
            The supplied ordering is not preserved as the constructor
            immediately calls :meth:`sort` to canonicalise the layout.

        See Also
        --------
        Intervals.sort : Helper that establishes the canonical ordering.
        Interval : Element type accepted by this constructor.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval, Intervals
        >>> collection = Intervals(Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31)))
        >>> len(collection)
        1
        """
        self.intervals = intervals
        self.sort()

    def sort(
        self,
    ) -> Self:
        """
        Sort the contained intervals in place by their endpoints.

        Intervals are ordered lexicographically by the tuple
        ``(interval.start, interval.end)``, so that earlier starts come first
        and ties are broken by the earlier end. The sort is stable and
        operates on the internal tuple in place, returning ``self`` to
        support fluent chaining.

        Returns
        -------
            The same :class:`Intervals` instance (now holding a reordered
            tuple) to enable method chaining.

        See Also
        --------
        Intervals.__init__ : Constructor that calls this helper automatically.
        sorted : Builtin function used to perform the underlying sort.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval, Intervals
        >>> collection = Intervals(
        ...     Interval(start=Date(2024, 2, 1), end=Date(2024, 2, 29)),
        ...     Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31)),
        ... )
        >>> collection[0].start == Date(2024, 1, 1)
        True
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
        r"""
        Render a multiline debug representation listing each interval.

        Joins the ``repr`` of every contained interval on its own
        tab-indented line, producing a compact yet readable dump for
        debugging sessions where inspecting the full sorted collection is
        useful. The leading and trailing newlines keep the wrapping
        ``Intervals(...)`` tokens visually separated from their contents.

        Returns
        -------
        str
            String of the form ``"Intervals(\\n\\t<repr1>\\n\\t<repr2>...\\n)"``
            combining the ``repr`` of each contained interval on its own
            indented line for readable inspection.

        See Also
        --------
        Interval.__str__ : Element-level counterpart used for string rendering.
        Intervals.__iter__ : Iterator yielding the intervals this output lists.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval, Intervals
        >>> collection = Intervals(Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31)))
        >>> repr(collection).startswith("Intervals(")
        True
        """
        return f"Intervals(\n\t{'\n\t'.join([repr(interval) for interval in self.intervals])}\n)"

    def __eq__(
        self,
        other: object,
    ) -> bool:
        """
        Test structural equality between two interval collections.

        Delegates to tuple equality on the underlying ``intervals`` attribute so
        that two collections are equal only when they contain the same intervals
        in the same order. Returns :data:`NotImplemented` when ``other`` is not
        an instance of the same concrete type so the reflected operator on
        ``other`` gets a chance to respond.

        Parameters
        ----------
        other
            Object to compare against; equality is only evaluated when ``other``
            is the same runtime type as ``self``.

        Returns
        -------
            ``True`` when both collections hold equal intervals in the same
            sorted order; ``False`` otherwise.

        See Also
        --------
        Intervals.__hash__ : Hash function whose contract is paired with this method.
        Intervals.sort : Establishes the canonical ordering compared here.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval, Intervals
        >>> a = Intervals(Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31)))
        >>> b = Intervals(Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31)))
        >>> a == b
        True
        """
        if not isinstance(other, type(self)):
            return NotImplemented

        return self.intervals == other.intervals

    def __hash__(
        self,
    ) -> int:
        """
        Hash the collection using its underlying sorted interval tuple.

        Forwards the internal ``intervals`` tuple directly to the builtin
        :func:`hash`. Because the tuple is canonical after each :meth:`sort`
        call, equal collections always produce the same hash, satisfying the
        hash-equality contract.

        Returns
        -------
            Integer hash of the sorted interval tuple.

        See Also
        --------
        Intervals.__eq__ : Equality check whose contract is paired with this hash.
        Intervals.sort : Ensures the tuple is canonical before hashing.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval, Intervals
        >>> collection = Intervals(Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31)))
        >>> isinstance(hash(collection), int)
        True
        """
        return hash(self.intervals)

    def __iter__(
        self,
    ) -> Iterator[Interval[IntervalType]]:
        """
        Iterate over the contained intervals in stored (sorted) order.

        Yields the canonical view established by :meth:`sort` so downstream
        code can rely on earlier-starting intervals appearing first. Each
        call returns a fresh iterator so the collection can be iterated
        multiple times without resetting state.

        Returns
        -------
        Iterator[Interval[IntervalType]]
            Fresh iterator yielding each :class:`Interval` in ``(start, end)``
            order as previously canonicalised by :meth:`sort`.

        See Also
        --------
        Intervals.__len__ : Report the number of intervals iterated.
        Intervals.sort : Establishes the ordering consumed by this iterator.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval, Intervals
        >>> collection = Intervals(Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31)))
        >>> [interval.days for interval in collection]
        [30]
        """
        return iter(self.intervals)

    def __len__(
        self,
    ) -> int:
        """
        Return the number of intervals stored in the collection.

        Delegates to the underlying tuple's ``len`` so the reported count is
        always in sync with the internal storage and unaffected by whether
        the tuple has been sorted. This lets the collection participate in
        ``len()`` calls and truthiness checks transparently.

        Returns
        -------
        int
            Count of :class:`Interval` instances currently held.

        See Also
        --------
        Intervals.__iter__ : Yields the intervals that this count refers to.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval, Intervals
        >>> len(Intervals(Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31))))
        1
        """
        return len(self.intervals)

    @overload
    def __getitem__(  # numpydoc ignore=GL08
        self,
        key: int,
    ) -> Interval[IntervalType]: ...

    @overload
    def __getitem__(  # numpydoc ignore=GL08
        self,
        key: slice,
    ) -> Intervals[IntervalType]: ...

    def __getitem__(
        self,
        key: int | slice,
    ) -> Intervals[IntervalType] | Interval[IntervalType]:
        """
        Index into the sorted collection by integer position or slice.

        Dispatches on the runtime type of ``key`` so a plain integer returns
        the underlying :class:`Interval`, while a :class:`slice` wraps the
        resulting subsequence into a new :class:`Intervals` instance. This
        keeps slicing composable with the rest of the API.

        Parameters
        ----------
        key
            Integer position selecting a single :class:`Interval` from the
            underlying sorted tuple, or a slice selecting a contiguous run
            and producing a new :class:`Intervals` wrapper around the result.

        Returns
        -------
        Interval[IntervalType] or Intervals[IntervalType]
            The single :class:`Interval` at ``key`` for integer indexing, or a
            new :class:`Intervals` instance holding the sliced subset when
            ``key`` is a :class:`slice`.

        See Also
        --------
        Intervals.__iter__ : Alternative traversal path for the same elements.
        Intervals.__len__ : Bounds check reference for valid integer indices.

        Examples
        --------
        >>> from mayutils.objects.datetime.datetime import Date
        >>> from mayutils.objects.datetime.interval import Interval, Intervals
        >>> collection = Intervals(
        ...     Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 31)),
        ...     Interval(start=Date(2024, 2, 1), end=Date(2024, 2, 29)),
        ... )
        >>> collection[0].days
        30
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
    """
    Build a rolling set of month-long intervals anchored on a day of month.

    Each returned interval starts on ``day`` of some month and ends on
    ``day`` of the following month; the sequence ends at the interval
    covering the month immediately preceding ``dt`` and extends
    ``num_periods`` steps back in time. The resulting :class:`Intervals`
    is sorted automatically so the earliest interval is at index ``0``.

    Parameters
    ----------
    dt
        Reference datetime marking the upper edge of the most recent
        interval. When ``None`` the function substitutes :meth:`DateTime.today`
        so callers can omit an explicit anchor.
    num_periods
        Number of consecutive month-long intervals to generate, counted back
        from the reference; controls the total historical span covered.
    day
        Day-of-month used to anchor each interval boundary. ``None`` falls
        back to ``dt.day`` so the window preserves the reference's own day.
    absolute_interval
        Forwarded to each :class:`Interval` constructor; when ``True`` each
        generated interval is stored in absolute (non-negative) form.

    Returns
    -------
    Intervals[DateTime]
        Sorted collection of ``num_periods`` consecutive month-long
        :class:`DateTime`-valued intervals ending at the month containing
        ``dt``.

    See Also
    --------
    Interval : Element type produced inside the returned collection.
    Intervals : Container wrapping the generated intervals.
    DateTime.today : Fallback anchor used when ``dt`` is ``None``.

    Examples
    --------
    >>> from mayutils.objects.datetime.datetime import DateTime
    >>> from mayutils.objects.datetime.interval import get_intervals
    >>> anchor = DateTime(2024, 7, 1)
    >>> collection = get_intervals(anchor, num_periods=3)
    >>> len(collection)
    3
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
