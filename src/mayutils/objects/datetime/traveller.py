"""Time-travel helper backed by Pendulum's testing traveller.

This module exposes a :class:`Traveller` subclass of
``pendulum.testing.traveller.Traveller`` that is pre-bound to the
project's :class:`mayutils.objects.datetime.datetime.DateTime` class.
It enables deterministic manipulation of the current instant inside
tests by freezing, advancing, or travelling to arbitrary moments in
time while ensuring that any ``DateTime.now()`` calls return values of
the project's own ``DateTime`` subclass rather than stock Pendulum
instances. A module-level ``traveller`` singleton is provided for
convenience so that callers can import a ready-to-use instance without
having to instantiate one themselves.
"""

from __future__ import annotations

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from pendulum.testing.traveller import Traveller as PendulumTraveller

from mayutils.objects.datetime.datetime import DateTime


class Traveller(PendulumTraveller):  # ty:ignore[unsupported-base]
    """Pendulum time traveller bound to the project's ``DateTime`` class.

    Extends ``pendulum.testing.traveller.Traveller`` so that any
    frozen, advanced, or relocated "now" value is produced as an
    instance of :class:`mayutils.objects.datetime.datetime.DateTime`
    rather than the default Pendulum ``DateTime``. This keeps test
    fixtures type-consistent with the rest of the codebase, which
    relies on the project's extended datetime class.
    """

    def __init__(
        self,
        cls: type[DateTime] = DateTime,
        /,
    ) -> None:
        """Initialise the traveller with the datetime class to instantiate.

        Parameters
        ----------
        cls : type[DateTime], optional
            Concrete ``DateTime`` class that the underlying Pendulum
            traveller will use when constructing the "current" moment
            during time travel. Defaults to the project's
            :class:`mayutils.objects.datetime.datetime.DateTime` so
            that frozen or shifted times match the type used
            elsewhere in the codebase. Passed positionally only.
        """
        super().__init__(
            datetime_class=cls,
        )


traveller = Traveller()
