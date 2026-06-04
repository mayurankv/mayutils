"""Tests for ``mayutils.objects.datetime.constants``.

Requires the ``datetime`` (for ``pendulum``) and ``numerics`` (for ``numpy``)
extras; the module is skipped at collection time otherwise.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

np = pytest.importorskip("numpy")
pendulum = pytest.importorskip("pendulum")

from mayutils.objects.datetime.constants import (  # noqa: E402
    DAY_SECONDS,
    DIFFERENCE_FORMATTER,
    FORMATTER,
)


class TestDaySeconds:
    """Tests for the :data:`DAY_SECONDS` conversion factor."""

    def test_equals_86400(self) -> None:
        """A standard civil day is exactly 86400 seconds."""
        assert DAY_SECONDS == 86400  # noqa: PLR2004

    def test_is_int(self) -> None:
        """The constant is an integer, not a float, for clean indexing."""
        assert isinstance(DAY_SECONDS, int)

    def test_self_consistent_product(self) -> None:
        """It equals the product of hours, minutes and seconds sub-units."""
        assert DAY_SECONDS == 24 * 60 * 60

    def test_matches_timedelta(self) -> None:
        """It agrees with stdlib ``timedelta(days=1).total_seconds()``."""
        one_day_seconds = int(timedelta(days=1).total_seconds())
        assert one_day_seconds == DAY_SECONDS


class TestFormatter:
    """Tests for the shared :data:`FORMATTER` instance."""

    def test_is_pendulum_formatter(self) -> None:
        """``FORMATTER`` is a :class:`pendulum.Formatter` instance."""
        assert isinstance(FORMATTER, pendulum.Formatter)

    def test_round_trips_tokens(self) -> None:
        """Token formatting renders a datetime to the expected string."""
        dt = pendulum.datetime(2026, 4, 22, 9, 30)
        assert FORMATTER.format(dt, "YYYY-MM-DD HH:mm") == "2026-04-22 09:30"


class TestDifferenceFormatter:
    """Tests for the shared :data:`DIFFERENCE_FORMATTER` instance."""

    def test_humanises_difference(self) -> None:
        """A three-hour gap is rendered as a humanised relative string."""
        now = pendulum.datetime(2026, 4, 22, 12, 0)
        past = pendulum.datetime(2026, 4, 22, 9, 0)
        assert DIFFERENCE_FORMATTER.format(past.diff(now), is_now=True) == "3 hours ago"
