"""Pendulum-backed timezone wrapper with timezone and locale helpers.

This module exposes :class:`Tz`, a thin subclass of :class:`pendulum.Timezone`
that centralises the common ways the rest of ``mayutils`` constructs, lists
and mocks timezones, together with process-wide locale management. A
module-level :data:`UTC` instance is provided as the canonical reference
timezone so callers do not repeatedly re-instantiate it. All helpers depend
on the optional ``pendulum`` extra and are guarded by
:func:`mayutils.core.extras.may_require_extras` so import-time failure
surfaces an actionable install hint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from pendulum import (
        FixedTimezone,
        get_locale,
        local_timezone,
        locale,
        set_local_timezone,
        set_locale,
        test_local_timezone,
    )
    from pendulum import (
        Timezone as PendulumTimezone,
    )
    from pendulum.tz import fixed_timezone, timezones

if TYPE_CHECKING:
    from contextlib import _GeneratorContextManager  # pyright: ignore[reportPrivateUsage]

    from pendulum.locales.locale import Locale


class Tz(PendulumTimezone):
    """Timezone handle with ergonomic constructors and local-timezone mocking.

    Subclasses :class:`pendulum.Timezone` so every instance is a fully
    functional pendulum timezone while additionally exposing class-level
    factories for IANA names and fixed UTC offsets, process-wide discovery
    of available zones, and helpers to set or temporarily mock the local
    machine timezone. Locale helpers are grouped here as well because
    pendulum ties locale state to its timezone-aware formatting.

    Notes
    -----
    Instances are interchangeable with :class:`pendulum.Timezone` anywhere
    pendulum expects one; the subclass adds behaviour without altering the
    underlying ``__new__`` contract.
    """

    def __new__(
        cls,
        key: str,
        /,
    ) -> Self:
        """Construct a :class:`Tz` bound to the supplied IANA timezone key.

        Forwards straight to :meth:`pendulum.Timezone.__new__` so the
        returned instance carries all of pendulum's timezone behaviour
        (offset resolution, DST transitions, serialisation) while being
        typed as :class:`Tz`; this is what lets downstream code subclass
        pendulum without losing the attribute-level tooling added here.

        Parameters
        ----------
        key : str
            IANA timezone identifier (for example ``"UTC"``,
            ``"Europe/London"`` or ``"America/New_York"``). Positional-only
            to match pendulum's own constructor signature and to keep the
            common ``Tz("Europe/London")`` call site unambiguous.

        Returns
        -------
        Self
            A fresh :class:`Tz` instance resolving to the zone named by
            ``key``, usable anywhere a :class:`pendulum.Timezone` is
            expected.

        Raises
        ------
        pendulum.tz.exceptions.InvalidTimezone
            If ``key`` does not correspond to a known IANA zone; the error
            originates from pendulum's underlying timezone registry.
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
        """Construct a timezone from either an IANA name or a signed offset.

        Dispatches on the type of ``name`` so the same entry point covers
        both named zones (e.g. ``"Europe/London"``) and anonymous fixed
        offsets. The special case of the string ``"utc"`` (any casing) is
        normalised to the canonical ``"UTC"`` IANA key so downstream
        equality and serialisation behave consistently.

        Parameters
        ----------
        name : str or int, default ``"UTC"``
            When a string, interpreted as an IANA timezone key used to
            construct a :class:`Tz`; the case-insensitive value ``"utc"``
            is normalised to the canonical ``"UTC"`` zone. When an integer,
            interpreted as a signed offset in seconds from UTC and used to
            build a :class:`pendulum.FixedTimezone` with no IANA identity.

        Returns
        -------
        Self or FixedTimezone
            A :class:`Tz` instance when ``name`` is a string, otherwise a
            :class:`pendulum.FixedTimezone` with the supplied offset.

        Examples
        --------
        >>> Tz.spawn(name="Europe/London")  # doctest: +SKIP
        Timezone('Europe/London')
        >>> Tz.spawn(name=3600)  # doctest: +SKIP
        Timezone('+01:00')
        """
        if isinstance(name, int):
            return fixed_timezone(offset=name)

        if name.lower() == "utc":
            return cls("UTC")

        return cls(name)

    @classmethod
    def list(
        cls,
    ) -> set[str]:
        """Enumerate every IANA timezone identifier known to pendulum.

        Delegates to :func:`pendulum.tz.timezones` and is primarily useful
        for validation (membership checks) and for presenting selectable
        choices in UIs or CLIs.

        Returns
        -------
        set of str
            The complete set of IANA timezone keys that :meth:`spawn`
            accepts as its string form, such as ``"Europe/London"`` or
            ``"America/New_York"``.
        """
        return timezones()

    @staticmethod
    def local() -> PendulumTimezone | FixedTimezone:
        """Detect the timezone currently configured for the running process.

        Resolves the machine's local zone via :func:`pendulum.local_timezone`,
        honouring any prior call to :meth:`set_local` or
        :meth:`test_local` as well as the underlying OS-level configuration.

        Returns
        -------
        PendulumTimezone or FixedTimezone
            The timezone pendulum considers local. A
            :class:`pendulum.Timezone` is returned when the local zone maps
            to a named IANA entry, otherwise a
            :class:`pendulum.FixedTimezone` representing a raw UTC offset.
        """
        return local_timezone()

    def set_local(
        self,
    ) -> None:
        """Override pendulum's local timezone with this instance.

        Permanently (for the lifetime of the process) replaces whatever
        pendulum returns from :func:`pendulum.local_timezone` with ``self``.
        Intended for deterministic behaviour in tests, notebooks and CLI
        entry points where the host machine's zone must not leak into
        computations; for scoped overrides prefer :meth:`test_local`.

        Returns
        -------
        None
            This method is used for its side effect on pendulum's global
            state and has no meaningful return value.
        """
        return set_local_timezone(mock=self)

    def test_local(
        self,
    ) -> _GeneratorContextManager[None, None, None]:
        """Context-manager variant that scopes the local-timezone override.

        Installs ``self`` as pendulum's local timezone on entry and restores
        the previous value on exit, making it safe to use inside tests or
        nested scopes without leaking state across the suite.

        Returns
        -------
        contextlib._GeneratorContextManager
            A re-entrant context manager that applies the override for the
            duration of its ``with`` block and rolls it back on exit.

        Examples
        --------
        >>> with Tz("Europe/London").test_local():  # doctest: +SKIP
        ...     ...  # code that should see London as local
        """
        return test_local_timezone(mock=self)

    @staticmethod
    def locale() -> str:
        """Report pendulum's currently active locale identifier.

        The locale governs how pendulum formats weekday names, month
        names, ordinal suffixes and similar human-readable tokens across
        any :class:`~pendulum.DateTime`, independent of the timezone.

        Returns
        -------
        str
            The BCP-47-style locale tag pendulum is currently configured
            with (for example ``"en"`` or ``"fr"``).
        """
        return get_locale()

    @staticmethod
    def set_locale(
        name: str,
        /,
    ) -> None:
        """Switch pendulum's active locale for the current process.

        Assigns the locale used by pendulum's formatting and parsing layer;
        the change is global and persists for the lifetime of the
        interpreter unless overwritten by a subsequent call.

        Parameters
        ----------
        name : str
            Locale identifier to activate (for example ``"en"``,
            ``"en_gb"`` or ``"fr"``). Must correspond to a locale that
            pendulum ships or can load via :meth:`load_locale`; unknown
            identifiers raise inside the pendulum call.

        Returns
        -------
        None
            This method mutates pendulum's global locale state and returns
            no value.
        """
        return set_locale(name=name)

    @staticmethod
    def load_locale(
        name: str,
        /,
    ) -> Locale:
        """Load a pendulum locale descriptor without activating it.

        Useful when callers need to inspect locale-specific data (such as
        translated month or weekday names) without mutating the global
        locale state the way :meth:`set_locale` does.

        Parameters
        ----------
        name : str
            Locale identifier to resolve (for example ``"en"`` or
            ``"fr"``). Selects which translation bundle pendulum loads.

        Returns
        -------
        pendulum.locales.locale.Locale
            The loaded locale object, exposing the translation tables
            pendulum uses internally for formatting and parsing.
        """
        return locale(name=name)


UTC = Tz("UTC")
