"""Tests for ``mayutils.objects.datetime.traveller``.

Requires the ``datetime`` (for ``pendulum``) and ``numerics`` (for ``numpy``)
extras; the module is skipped at collection time otherwise.
"""

from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")
pendulum = pytest.importorskip("pendulum")

from mayutils.objects.datetime import DateTime  # noqa: E402
from mayutils.objects.datetime.traveller import Traveller, traveller  # noqa: E402


class TestTravellerSingleton:
    """Tests for the module-level :data:`traveller` instance."""

    def test_is_traveller(self) -> None:
        """The singleton is a :class:`Traveller` instance."""
        assert isinstance(traveller, Traveller)


class TestFreeze:
    """Tests for freezing ``now`` to a fixed instant."""

    def test_freezes_now(self) -> None:
        """Inside a frozen scope ``now`` is pinned to the target instant."""
        with traveller.travel_to(DateTime.parse("2026-01-01T00:00:00Z"), freeze=True):
            pinned = DateTime.now("UTC")
        assert pinned.to_iso8601_string() == "2026-01-01T00:00:00Z"

    def test_frozen_now_is_stable(self) -> None:
        """Repeated reads within a frozen scope return the same instant."""
        with traveller.travel_to(DateTime.parse("2026-01-01T00:00:00Z"), freeze=True):
            first = DateTime.now("UTC")
            second = DateTime.now("UTC")
        assert first == second

    def test_returns_project_datetime(self) -> None:
        """The frozen ``now`` is the project's :class:`DateTime` subclass."""
        with traveller.travel_to(DateTime.parse("2026-04-22T10:00:00Z"), freeze=True):
            pinned = DateTime.now("UTC")
        assert type(pinned) is DateTime


class TestRestoration:
    """Tests that the real clock is restored once a scope exits."""

    def test_restores_after_scope(self) -> None:
        """After the scope the clock is no longer pinned to the target."""
        target = DateTime.parse("2000-01-01T00:00:00Z")
        before = DateTime.now("UTC")
        with traveller.travel_to(target, freeze=True):
            pass
        after = DateTime.now("UTC")
        assert after != target
        assert before <= after


class TestNesting:
    """Tests for nested travels and relative advances."""

    def test_advances_time(self) -> None:
        """Advancing seven days inside a frozen anchor shifts ``now`` forward.

        The outer ``travel_to(..., freeze=True)`` freezes the clock, so the inner
        relative ``travel`` simply moves the frozen instant forward by a week.
        """
        nested = Traveller()
        with nested.travel_to(DateTime.parse("2026-01-01T00:00:00Z"), freeze=True), nested.travel(days=7):
            shifted = DateTime.now("UTC")
        assert shifted.to_iso8601_string() == "2026-01-08T00:00:00Z"

    def test_inner_scope_exit_restores_real_clock_on_shared_instance(self) -> None:
        """Document current behaviour: reusing one instance does NOT stack scopes.

        The class docstring claims nested mocks "stack" and that each scope
        "restores the previous clock when it exits", but pendulum's traveller
        keeps a single coordinate machine per instance. Exiting the inner
        ``travel`` therefore tears it down entirely and leaves the *real* clock
        active rather than the outer frozen instant. See module REPORT.
        """
        target = DateTime.parse("2026-01-01T00:00:00Z")
        inner_target = DateTime.parse("2026-01-08T00:00:00Z")
        before = DateTime.now("UTC")
        nested = Traveller()
        with nested.travel_to(target, freeze=True):
            with nested.travel(days=7):
                inner = DateTime.now("UTC")
            outer = DateTime.now("UTC")
        after = DateTime.now("UTC")
        assert inner == inner_target
        # The outer read is the live clock, not the outer frozen instant.
        assert outer != target
        assert outer != inner_target
        assert before <= outer <= after


class TestCustomDateTimeClass:
    """Tests for binding the traveller to a custom ``DateTime`` subclass."""

    def test_custom_subclass_returned(self) -> None:
        """A custom subclass passed to the constructor is what ``now`` yields."""

        class MyDateTime(DateTime):
            pass

        custom = Traveller(MyDateTime)
        with custom.travel_to(DateTime.parse("2026-04-22T10:00:00Z"), freeze=True):
            stamped = MyDateTime.now("UTC")
        assert isinstance(stamped, MyDateTime)
        assert stamped.year == 2026  # noqa: PLR2004
