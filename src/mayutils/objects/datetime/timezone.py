"""
Expose pendulum-backed timezone helpers with ergonomic construction.

Centralises the common ways the rest of ``mayutils`` constructs, lists and
mocks timezones together with process-wide locale management via the
:class:`Tz` wrapper. A module-level :data:`UTC` instance is provided as the
canonical reference timezone so callers avoid repeatedly re-instantiating it
during conversions between IANA-named zones and fixed UTC offsets. All
helpers depend on the optional ``pendulum`` extra and are guarded by
:func:`mayutils.core.extras.may_require_extras` so import-time failure
surfaces an actionable install hint.

See Also
--------
zoneinfo.ZoneInfo : Standard-library IANA timezone loader for Python 3.9+.
pendulum.timezone : Upstream pendulum factory this module wraps.
datetime.timezone : Fixed-offset timezone implementation in the stdlib.
Tz : Primary class exported by this module.

Examples
--------
>>> from mayutils.objects.datetime.timezone import Tz, UTC
>>> UTC.name
'UTC'
>>> Tz("Europe/London").name
'Europe/London'
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from pendulum import (
        FixedTimezone,
    )
    from pendulum import (
        Timezone as PendulumTimezone,
    )

if TYPE_CHECKING:
    from contextlib import _GeneratorContextManager  # pyright: ignore[reportPrivateUsage]

    from pendulum.locales.locale import Locale


class Tz(PendulumTimezone):
    """
    Wrap :class:`pendulum.Timezone` with ergonomic constructors and mocking.

    Subclasses :class:`pendulum.Timezone` so every instance remains a fully
    functional pendulum timezone while additionally exposing class-level
    factories for IANA names and fixed UTC offsets, process-wide discovery
    of available zones, and helpers to set or temporarily mock the local
    machine timezone. Locale helpers are grouped here as well because
    pendulum ties locale state to its timezone-aware formatting. Instances
    are interchangeable with :class:`pendulum.Timezone` anywhere pendulum
    expects one; the subclass adds behaviour without altering the
    underlying ``__new__`` contract.

    See Also
    --------
    pendulum.timezone : Upstream factory producing the parent class.
    zoneinfo.ZoneInfo : Standard-library IANA timezone alternative.
    datetime.timezone : Stdlib class for fixed-offset timezones.
    Tz.spawn : Dispatch between IANA names and fixed offsets.

    Examples
    --------
    >>> from mayutils.objects.datetime.timezone import Tz
    >>> london = Tz("Europe/London")
    >>> london.name
    'Europe/London'
    >>> with london.test_local():
    ...     Tz.local().name
    'Europe/London'
    """

    def __new__(
        cls,
        key: str,
        /,
    ) -> Self:
        """
        Construct a :class:`Tz` bound to the supplied IANA timezone key.

        Forwards straight to :meth:`pendulum.Timezone.__new__` so the
        returned instance carries all of pendulum's timezone behaviour
        (offset resolution, DST transitions, serialisation) while being
        typed as :class:`Tz`. This is what lets downstream code subclass
        pendulum without losing the attribute-level tooling added here.
        DST rules are inherited from the IANA zoneinfo database the
        underlying pendulum installation resolves against.

        Parameters
        ----------
        key
            IANA timezone identifier (for example ``"UTC"``,
            ``"Europe/London"`` or ``"America/New_York"``). Positional-only
            to match pendulum's own constructor signature and to keep the
            common ``Tz("Europe/London")`` call site unambiguous.

        Returns
        -------
            A fresh :class:`Tz` instance resolving to the zone named by
            ``key``, usable anywhere a :class:`pendulum.Timezone` is
            expected. Unknown IANA keys propagate
            ``pendulum.tz.exceptions.InvalidTimezone`` up from the
            parent constructor.

        See Also
        --------
        pendulum.timezone : Upstream factory producing the same instance.
        zoneinfo.ZoneInfo : Standard-library IANA loader accepting the
            same keys.
        Tz.spawn : Dispatcher accepting either IANA names or integer
            offsets.

        Examples
        --------
        >>> from mayutils.objects.datetime.timezone import Tz
        >>> tz = Tz("Europe/London")
        >>> tz.name
        'Europe/London'
        >>> Tz("America/New_York").name
        'America/New_York'
        """
        return super().__new__(
            cls=cls,
            key=key,
        )

    @classmethod
    def spawn(
        cls,
        *,
        name: str | int = "UTC",
    ) -> Self | FixedTimezone:
        """
        Construct a timezone from either an IANA name or a signed offset.

        Dispatches on the type of ``name`` so the same entry point covers
        both named zones (for example ``"Europe/London"``) and anonymous
        fixed offsets. The special case of the string ``"utc"`` (any
        casing) is normalised to the canonical ``"UTC"`` IANA key so
        downstream equality and serialisation behave consistently. Named
        zones retain DST transitions, whereas integer offsets produce a
        :class:`pendulum.FixedTimezone` that is permanently at the given
        UTC offset with no DST awareness.

        Parameters
        ----------
        name
            When a string, interpreted as an IANA timezone key used to
            construct a :class:`Tz`; the case-insensitive value ``"utc"``
            is normalised to the canonical ``"UTC"`` zone. When an
            integer, interpreted as a signed offset in seconds from UTC
            and used to build a :class:`pendulum.FixedTimezone` with no
            IANA identity.

        Returns
        -------
            A :class:`Tz` instance when ``name`` is a string, otherwise a
            :class:`pendulum.FixedTimezone` with the supplied offset.

        See Also
        --------
        pendulum.timezone : Upstream factory handling IANA names.
        datetime.timezone : Stdlib equivalent for fixed-offset zones.
        zoneinfo.ZoneInfo : Alternative for IANA zones using stdlib.
        Tz.list : Enumerate valid IANA keys this method accepts.

        Examples
        --------
        >>> from mayutils.objects.datetime.timezone import Tz
        >>> Tz.spawn(name="Europe/London").name
        'Europe/London'
        >>> Tz.spawn(name=3600).name
        '+01:00'
        >>> Tz.spawn(name="utc").name
        'UTC'
        """
        with may_require_extras():
            from pendulum.tz import fixed_timezone

        if isinstance(name, int):
            return fixed_timezone(offset=name)

        if name.lower() == "utc":
            return cls("UTC")

        return cls(name)

    @classmethod
    def list(
        cls,
    ) -> set[str]:
        """
        Enumerate every IANA timezone identifier known to pendulum.

        Delegates to :func:`pendulum.tz.timezones` and is primarily useful
        for validation (membership checks) and for presenting selectable
        choices in UIs or CLIs. The returned set mirrors the snapshot of
        the IANA tzdata bundle shipped with the installed pendulum
        package, so availability of newly added zones depends on the
        pendulum version in the current environment.

        Returns
        -------
            The complete set of IANA timezone keys that :meth:`spawn`
            accepts as its string form, such as ``"Europe/London"`` or
            ``"America/New_York"``.

        See Also
        --------
        pendulum.tz.timezones : Underlying pendulum enumerator wrapped
            here.
        zoneinfo.available_timezones : Standard-library equivalent
            enumerator.
        Tz.spawn : Consumer of the keys returned by this method.

        Examples
        --------
        >>> from mayutils.objects.datetime.timezone import Tz
        >>> "Europe/London" in Tz.list()
        True
        >>> "UTC" in Tz.list()
        True
        """
        with may_require_extras():
            from pendulum.tz import timezones

        return timezones()

    @staticmethod
    def local() -> PendulumTimezone | FixedTimezone:
        """
        Detect the timezone currently configured for the running process.

        Resolves the machine's local zone via :func:`pendulum.local_timezone`,
        honouring any prior call to :meth:`set_local` or :meth:`test_local`
        as well as the underlying OS-level configuration. The resolution
        first consults pendulum's mocked value, then falls back to the
        environment-aware detection pendulum performs (``TZ`` variable,
        ``/etc/localtime`` and Windows registry as applicable).

        Returns
        -------
            The timezone pendulum considers local. A
            :class:`pendulum.Timezone` is returned when the local zone
            maps to a named IANA entry, otherwise a
            :class:`pendulum.FixedTimezone` representing a raw UTC
            offset.

        See Also
        --------
        pendulum.local_timezone : Underlying detection routine.
        datetime.timezone : Fixed-offset fallback type used when no IANA
            zone is detected.
        Tz.set_local : Permanently override the detected local zone.
        Tz.test_local : Context-scoped mocking of the local zone.

        Examples
        --------
        >>> from pendulum import Timezone as PendulumTimezone
        >>> from mayutils.objects.datetime.timezone import Tz
        >>> with Tz("Europe/London").test_local():
        ...     Tz.local().name
        'Europe/London'
        >>> with Tz("UTC").test_local():
        ...     isinstance(Tz.local(), PendulumTimezone)
        True
        """
        with may_require_extras():
            from pendulum import local_timezone

        return local_timezone()

    def set_local(
        self,
    ) -> None:
        """
        Override pendulum's local timezone with this instance.

        Permanently (for the lifetime of the process) replaces whatever
        pendulum returns from :func:`pendulum.local_timezone` with
        ``self``. Intended for deterministic behaviour in tests,
        notebooks and CLI entry points where the host machine's zone
        must not leak into computations. For scoped overrides prefer
        :meth:`test_local`, which rolls the override back on exit.

        Returns
        -------
            This method is used for its side effect on pendulum's global
            state and has no meaningful return value.

        See Also
        --------
        pendulum.set_local_timezone : Underlying pendulum mutator.
        Tz.test_local : Scoped equivalent that restores the prior zone.
        Tz.local : Query pendulum for the currently configured local
            zone.

        Examples
        --------
        >>> from pendulum import set_local_timezone
        >>> from mayutils.objects.datetime.timezone import Tz
        >>> try:
        ...     Tz("Europe/London").set_local()
        ...     Tz.local().name
        ... finally:
        ...     set_local_timezone()
        'Europe/London'
        """
        with may_require_extras():
            from pendulum import set_local_timezone

        return set_local_timezone(mock=self)

    def test_local(
        self,
    ) -> _GeneratorContextManager[None, None, None]:
        """
        Scope a local-timezone override to a context-manager block.

        Installs ``self`` as pendulum's local timezone on entry and
        restores the previous value on exit, making it safe to use
        inside tests or nested scopes without leaking state across the
        suite. Because the override is temporary, DST-sensitive
        computations executed inside the block observe the mocked zone
        while the rest of the process continues to see whatever value
        was previously active.

        Returns
        -------
            A re-entrant context manager that applies the override for
            the duration of its ``with`` block and rolls it back on
            exit.

        See Also
        --------
        pendulum.test_local_timezone : Underlying pendulum context
            manager.
        Tz.set_local : Permanent, unscoped equivalent.
        Tz.local : Query the currently configured local zone.

        Examples
        --------
        >>> from mayutils.objects.datetime.timezone import Tz
        >>> with Tz("Europe/London").test_local():
        ...     Tz.local().name
        'Europe/London'
        >>> with Tz("America/New_York").test_local():
        ...     Tz.local().name
        'America/New_York'
        """
        with may_require_extras():
            from pendulum import test_local_timezone

        return test_local_timezone(mock=self)

    @staticmethod
    def locale() -> str:
        """
        Report pendulum's currently active locale identifier.

        The locale governs how pendulum formats weekday names, month
        names, ordinal suffixes and similar human-readable tokens across
        any :class:`~pendulum.DateTime`, independent of the timezone.
        This helper is therefore complementary to the timezone tools on
        this class: timezone controls instants in time, whereas the
        locale controls their presentation to humans.

        Returns
        -------
            The BCP-47-style locale tag pendulum is currently configured
            with (for example ``"en"`` or ``"fr"``).

        See Also
        --------
        pendulum.get_locale : Underlying pendulum accessor.
        Tz.set_locale : Mutator for the process-wide locale.
        Tz.load_locale : Load a locale without activating it.

        Examples
        --------
        >>> from mayutils.objects.datetime.timezone import Tz
        >>> _previous = Tz.locale()
        >>> try:
        ...     Tz.set_locale("en")
        ...     first = Tz.locale()
        ...     Tz.set_locale("fr")
        ...     second = Tz.locale()
        ... finally:
        ...     Tz.set_locale(_previous)
        >>> first
        'en'
        >>> second
        'fr'
        """
        with may_require_extras():
            from pendulum import get_locale

        return get_locale()

    @staticmethod
    def set_locale(
        name: str,
        /,
    ) -> None:
        """
        Switch pendulum's active locale for the current process.

        Assigns the locale used by pendulum's formatting and parsing
        layer; the change is global and persists for the lifetime of the
        interpreter unless overwritten by a subsequent call. Combine
        with :meth:`set_local` when you need both the timezone and the
        presentation layer pinned to a specific locale for a long-lived
        process, or with :meth:`test_local` for scoped overrides.

        Parameters
        ----------
        name
            Locale identifier to activate (for example ``"en"``,
            ``"en_gb"`` or ``"fr"``). Must correspond to a locale that
            pendulum ships or can load via :meth:`load_locale`; unknown
            identifiers raise inside the pendulum call.

        Returns
        -------
            This method mutates pendulum's global locale state and
            returns no value.

        See Also
        --------
        pendulum.set_locale : Underlying pendulum mutator.
        Tz.locale : Query the currently active locale tag.
        Tz.load_locale : Load a locale descriptor without activating it.

        Examples
        --------
        >>> from mayutils.objects.datetime.timezone import Tz
        >>> _previous = Tz.locale()
        >>> try:
        ...     Tz.set_locale("en_gb")
        ...     active = Tz.locale()
        ... finally:
        ...     Tz.set_locale(_previous)
        >>> active
        'en_gb'
        """
        with may_require_extras():
            from pendulum import set_locale

        return set_locale(name=name)

    @staticmethod
    def load_locale(
        name: str,
        /,
    ) -> Locale:
        """
        Load a pendulum locale descriptor without activating it.

        Useful when callers need to inspect locale-specific data (such
        as translated month or weekday names) without mutating the
        global locale state the way :meth:`set_locale` does. The
        returned object exposes the raw translation tables pendulum
        bundles for the requested locale and is otherwise inert with
        respect to pendulum's global formatting configuration.

        Parameters
        ----------
        name
            Locale identifier to resolve (for example ``"en"`` or
            ``"fr"``). Selects which translation bundle pendulum loads.

        Returns
        -------
            The loaded locale object, exposing the translation tables
            pendulum uses internally for formatting and parsing.

        See Also
        --------
        pendulum.locale : Upstream loader wrapped by this method.
        Tz.set_locale : Mutator activating a locale globally.
        Tz.locale : Accessor for the active locale identifier.

        Examples
        --------
        >>> from mayutils.objects.datetime.timezone import Tz
        >>> fr = Tz.load_locale("fr")
        >>> isinstance(fr, object)
        True
        """
        with may_require_extras():
            from pendulum import locale

        return locale(name=name)


UTC = Tz("UTC")
