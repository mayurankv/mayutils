"""Tests for ``mayutils.objects.datetime.timezone``.

Requires the ``datetime`` (for ``pendulum``) and ``numerics`` (for ``numpy``)
extras; the module is skipped at collection time otherwise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

np = pytest.importorskip("numpy")
pendulum = pytest.importorskip("pendulum")

if TYPE_CHECKING:
    from pendulum import FixedTimezone
    from pendulum import Timezone as PendulumTimezone
else:
    FixedTimezone = pytest.importorskip("pendulum").FixedTimezone
    PendulumTimezone = pytest.importorskip("pendulum").Timezone

from pendulum.tz.exceptions import InvalidTimezone  # noqa: E402

from mayutils.objects.datetime.timezone import UTC, Tz  # noqa: E402


class TestTzConstruction:
    """Tests for constructing :class:`Tz` from IANA keys."""

    def test_is_pendulum_timezone(self) -> None:
        """A ``Tz`` is interchangeable with a :class:`pendulum.Timezone`."""
        assert isinstance(Tz("Europe/London"), PendulumTimezone)

    @pytest.mark.parametrize("name", ["UTC", "Europe/London", "America/New_York"])
    def test_name_round_trips(self, name: str) -> None:
        """The IANA key supplied is preserved on the ``name`` attribute."""
        assert Tz(name).name == name

    def test_invalid_name_raises(self) -> None:
        """An unknown IANA key raises :class:`InvalidTimezone`."""
        with pytest.raises(InvalidTimezone):
            Tz("Not/AZone")


class TestUtc:
    """Tests for the module-level :data:`UTC` instance."""

    def test_is_tz(self) -> None:
        """``UTC`` is a :class:`Tz` instance."""
        assert isinstance(UTC, Tz)

    def test_name_is_utc(self) -> None:
        """``UTC`` resolves to the canonical ``"UTC"`` name."""
        assert UTC.name == "UTC"


class TestSpawn:
    """Tests for :meth:`Tz.spawn` — the named/offset dispatcher."""

    def test_default_is_utc(self) -> None:
        """With no argument ``spawn`` yields the UTC zone."""
        assert Tz.spawn().name == "UTC"

    def test_named_zone(self) -> None:
        """A string is treated as an IANA name."""
        result = Tz.spawn(name="Europe/London")
        assert isinstance(result, Tz)
        assert result.name == "Europe/London"

    @pytest.mark.parametrize("raw", ["utc", "UTC", "Utc", "uTc"])
    def test_utc_casing_normalises(self, raw: str) -> None:
        """Any casing of ``"utc"`` maps to the canonical ``"UTC"`` zone."""
        result = Tz.spawn(name=raw)
        assert isinstance(result, Tz)
        assert result.name == "UTC"

    def test_integer_offset_builds_fixed_timezone(self) -> None:
        """An integer offset produces a :class:`FixedTimezone`."""
        result = Tz.spawn(name=3600)
        assert isinstance(result, FixedTimezone)
        assert result.name == "+01:00"

    def test_zero_offset(self) -> None:
        """A zero offset is the ``+00:00`` fixed zone."""
        assert Tz.spawn(name=0).name == "+00:00"

    def test_negative_offset(self) -> None:
        """A negative offset produces a negative fixed zone."""
        assert Tz.spawn(name=-3600).name == "-01:00"


class TestList:
    """Tests for :meth:`Tz.list` — IANA enumeration."""

    def test_returns_set(self) -> None:
        """The enumeration is returned as a set."""
        assert isinstance(Tz.list(), set)

    @pytest.mark.parametrize("name", ["UTC", "Europe/London", "America/New_York"])
    def test_contains_known_zones(self, name: str) -> None:
        """Well-known zones appear in the enumeration."""
        assert name in Tz.list()

    def test_spawn_accepts_listed_names(self) -> None:
        """Every listed name is accepted by :meth:`Tz.spawn`."""
        sample = next(iter(Tz.list()))
        assert isinstance(Tz.spawn(name=sample), Tz)


class TestConvert:
    """Tests for converting and localising datetimes via a :class:`Tz`."""

    def test_localises_naive_to_utc(self) -> None:
        """Converting a naive datetime through ``UTC`` attaches UTC tzinfo."""
        naive = pendulum.naive(2025, 1, 15, 12, 0)
        assert naive.tzinfo is None
        result = UTC.convert(naive)
        assert result.tzinfo is not None
        assert (result.year, result.month, result.day, result.hour) == (2025, 1, 15, 12)

    def test_converts_utc_to_summer_offset(self) -> None:
        """A UTC instant converts to British Summer Time (+1h) in July."""
        london = Tz("Europe/London")
        utc_noon = pendulum.datetime(2025, 7, 1, 12, 0, tz="UTC")
        result = london.convert(utc_noon)
        assert result.hour == 13  # noqa: PLR2004
        assert result == utc_noon

    def test_converts_utc_to_winter_offset(self) -> None:
        """A UTC instant in January maps onto the same wall clock (+0h)."""
        london = Tz("Europe/London")
        utc_noon = pendulum.datetime(2025, 1, 15, 12, 0, tz="UTC")
        result = london.convert(utc_noon)
        assert result.hour == 12  # noqa: PLR2004

    def test_utc_convert_is_identity_for_utc_aware(self) -> None:
        """Converting an already-UTC datetime through ``UTC`` is a no-op."""
        aware = pendulum.datetime(2025, 1, 15, 12, 0, tz="UTC")
        result = UTC.convert(aware)
        assert result == aware
        assert (result.hour, result.minute) == (12, 0)
