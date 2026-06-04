"""
Expose a time-travel helper backed by Pendulum's testing traveller.

Wires :class:`mayutils.objects.datetime.datetime.DateTime` into
Pendulum's built-in clock-mocking machinery so that deterministic tests
can freeze, advance, or relocate the current moment without leaking
stock Pendulum types into fixture assertions. Subclasses
``pendulum.testing.traveller.Traveller`` and binds its
``datetime_class`` hook to the project's ``DateTime`` subclass, which
means each ``travel_to`` call pushes a monkey-patched ``now()`` onto
Pendulum's internal stack that is automatically popped on exit. A
module-level ``traveller`` singleton is provided so callers can reach
for a ready-to-use instance without constructing their own.

See Also
--------
pendulum.testing.traveller.Traveller : Upstream clock-mocking machinery.
freezegun : Alternative freeze-time library with similar semantics.
mayutils.objects.datetime.datetime.DateTime : Project DateTime wrapper.

Examples
--------
>>> from mayutils.objects.datetime.traveller import traveller
>>> from mayutils.objects.datetime.datetime import DateTime
>>> with traveller.travel_to("2026-01-01T00:00:00Z", freeze=True):
...     pinned = DateTime.now("UTC")
>>> pinned.to_iso8601_string()
'2026-01-01T00:00:00Z'
>>> pinned.year
2026
"""

from __future__ import annotations

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from pendulum.testing.traveller import Traveller as PendulumTraveller

from mayutils.objects.datetime.datetime import DateTime


class Traveller(PendulumTraveller):  # ty:ignore[unsupported-base]
    """
    Bind Pendulum's time traveller to the project's ``DateTime`` class.

    Extends ``pendulum.testing.traveller.Traveller`` so that any frozen,
    advanced, or relocated "now" value is produced as an instance of
    :class:`mayutils.objects.datetime.datetime.DateTime` rather than the
    default Pendulum ``DateTime``. The subclass keeps Pendulum's
    context-manager semantics intact: entering a ``travel_to``/``travel``
    scope pins ``now()`` for its duration and exiting it restores the real
    clock. Reusing a single instance for *nested* scopes does not stack —
    exiting an inner scope returns to the real clock, not the enclosing
    frozen instant — so read the mocked ``now()`` within the innermost
    active scope. This keeps test fixtures type-consistent with the rest of
    the codebase, which relies on the project's extended datetime class.

    Parameters
    ----------
    cls
        Concrete ``DateTime`` class that the underlying Pendulum
        traveller will use when constructing the "current" moment during
        time travel. Defaults to the project's
        :class:`mayutils.objects.datetime.datetime.DateTime` so that
        frozen or shifted times match the type used elsewhere in the
        codebase. Passed positionally only.

    See Also
    --------
    pendulum.travel_to : Underlying Pendulum helper for pinning ``now``.
    freezegun : Alternative library offering similar clock-mocking.
    mayutils.objects.datetime.datetime : Project ``DateTime`` subclass.
    mayutils.objects.datetime.traveller.traveller : Module-level singleton.

    Examples
    --------
    Pin time inside a fixture so assertions become deterministic:

    >>> from mayutils.objects.datetime.traveller import Traveller
    >>> from mayutils.objects.datetime.datetime import DateTime
    >>> with Traveller().travel_to("2026-04-22T10:00:00Z", freeze=True):
    ...     snapshot = DateTime.now("UTC")
    >>> snapshot.to_iso8601_string()
    '2026-04-22T10:00:00Z'

    Nest travels to model multi-step fixtures; read the mocked ``now()``
    inside the innermost scope (exiting a scope returns to the real clock,
    not the enclosing frozen instant):

    >>> from mayutils.objects.datetime.traveller import Traveller
    >>> from mayutils.objects.datetime.datetime import DateTime
    >>> nested_traveller = Traveller()
    >>> with nested_traveller.travel_to("2026-01-01T00:00:00Z", freeze=True):
    ...     with nested_traveller.travel(days=7, freeze=True):
    ...         shifted = DateTime.now("UTC")
    >>> shifted.to_iso8601_string()
    '2026-01-08T00:00:00Z'
    """

    def __init__(
        self,
        cls: type[DateTime] = DateTime,
        /,
    ) -> None:
        """
        Initialise the traveller with the datetime class to instantiate.

        Forwards the supplied ``DateTime`` subclass to Pendulum's parent
        constructor via the ``datetime_class`` keyword so that every
        mocked ``now()`` call returns an instance of the project's own
        datetime type. This indirection keeps tests free of isinstance
        surprises when asserting against values produced during a
        ``travel_to`` block, and it preserves Pendulum's stack-based
        restoration semantics so nested travels unwind cleanly on exit.

        Parameters
        ----------
        cls
            Concrete ``DateTime`` class that the underlying Pendulum
            traveller will use when constructing the "current" moment
            during time travel. Defaults to the project's
            :class:`mayutils.objects.datetime.datetime.DateTime` so that
            frozen or shifted times match the type used elsewhere in the
            codebase. Passed positionally only.

        See Also
        --------
        pendulum.travel_to : Underlying Pendulum helper for pinning ``now``.
        freezegun : Alternative library offering similar clock-mocking.
        mayutils.objects.datetime.datetime : Project ``DateTime`` subclass.
        mayutils.objects.datetime.traveller.Traveller.freeze : Pin ``now``.

        Examples
        --------
        Construct a traveller bound to the default project ``DateTime``
        and use it to pin the clock inside a test:

        >>> from mayutils.objects.datetime.traveller import Traveller
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> default_traveller = Traveller()
        >>> with default_traveller.travel_to("2026-04-22T10:00:00Z", freeze=True):
        ...     pinned = DateTime.now("UTC")
        >>> isinstance(pinned, DateTime)
        True
        >>> pinned.to_iso8601_string()
        '2026-04-22T10:00:00Z'

        Pass a custom ``DateTime`` subclass positionally to reuse the
        traveller with domain-specific datetime types:

        >>> from mayutils.objects.datetime.traveller import Traveller
        >>> from mayutils.objects.datetime.datetime import DateTime
        >>> class MyDateTime(DateTime):
        ...     pass
        >>> custom_traveller = Traveller(MyDateTime)
        >>> with custom_traveller.travel_to("2026-04-22T10:00:00Z", freeze=True):
        ...     stamped = MyDateTime.now("UTC")
        >>> isinstance(stamped, MyDateTime)
        True
        >>> stamped.year
        2026
        """
        super().__init__(
            datetime_class=cls,
        )


traveller = Traveller()
