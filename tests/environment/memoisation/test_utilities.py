"""Tests for ``mayutils.environment.memoisation.utilities``.

Covers deterministic cache-key generation and the TTL helpers
(:func:`expiry`, :func:`is_expired`, :func:`format_ttl`). Requires the
``datetime`` extra (for ``pendulum``); the module is skipped at
collection time otherwise.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("pendulum")

from mayutils.environment.memoisation.utilities import (
    expiry,
    format_ttl,
    is_expired,
    make_cache_key,
)
from mayutils.objects.datetime import DateTime, Duration


class TestMakeCacheKey:
    """Tests for :func:`make_cache_key` — deterministic key from a call signature."""

    def test_returns_64_char_hex(self) -> None:
        """The key is the 64-char lowercase hex SHA-256 digest of the bundle."""
        key = make_cache_key("fetch", args=("GBP",), kwargs={})
        assert len(key) == 64  # noqa: PLR2004
        assert all(character in "0123456789abcdef" for character in key)

    def test_same_signature_same_key(self) -> None:
        """Identical name, args and kwargs produce an identical key."""
        first = make_cache_key("f", args=(1, 2), kwargs={"a": 3})
        second = make_cache_key("f", args=(1, 2), kwargs={"a": 3})
        assert first == second

    def test_function_name_is_part_of_key(self) -> None:
        """Two callables with the same argument shape produce distinct keys."""
        assert make_cache_key("f", args=(1,), kwargs={}) != make_cache_key("g", args=(1,), kwargs={})

    def test_kwargs_ordering_does_not_matter(self) -> None:
        """Keyword ordering at the call site does not change the key."""
        assert make_cache_key("f", args=(), kwargs={"a": 1, "b": 2}) == make_cache_key("f", args=(), kwargs={"b": 2, "a": 1})

    def test_positional_ordering_matters(self) -> None:
        """Positional argument order does change the key."""
        assert make_cache_key("f", args=(1, 2), kwargs={}) != make_cache_key("f", args=(2, 1), kwargs={})

    def test_empty_args_and_kwargs_is_stable(self) -> None:
        """An empty call signature still yields a stable, repeatable key."""
        assert make_cache_key("f", args=(), kwargs={}) == make_cache_key("f", args=(), kwargs={})

    def test_args_value_changes_key(self) -> None:
        """Changing a positional value changes the key."""
        assert make_cache_key("f", args=(1,), kwargs={}) != make_cache_key("f", args=(2,), kwargs={})

    def test_kwargs_value_changes_key(self) -> None:
        """Changing a keyword value changes the key."""
        assert make_cache_key("f", args=(), kwargs={"a": 1}) != make_cache_key("f", args=(), kwargs={"a": 2})


class TestIsExpired:
    """Tests for :func:`is_expired` — compares an absolute expiry against now."""

    def test_none_is_never_expired(self) -> None:
        """``None`` is the immortal marker and never counts as expired."""
        assert is_expired(None) is False

    def test_future_is_not_expired(self) -> None:
        """A timestamp in the future has not expired."""
        assert is_expired(DateTime.now() + timedelta(hours=1)) is False

    def test_past_is_expired(self) -> None:
        """A timestamp in the past has expired."""
        assert is_expired(DateTime.now() - timedelta(hours=1)) is True


class TestExpiry:
    """Tests for :func:`expiry` — absolute expiry from a relative TTL."""

    def test_none_ttl_passes_through(self) -> None:
        """A ``None`` TTL disables expiry and returns ``None``."""
        assert expiry(None) is None

    def test_positive_ttl_is_in_the_future(self) -> None:
        """A positive TTL yields a deadline strictly after ``now``."""
        before = DateTime.now()
        stamp = expiry(Duration(minutes=10))
        assert stamp is not None
        assert stamp > before

    def test_expiry_round_trips_through_is_expired(self) -> None:
        """An expiry computed from a positive TTL is not yet expired."""
        assert is_expired(expiry(Duration(hours=1))) is False


class TestFormatTtl:
    """Tests for :func:`format_ttl` — compact human-readable TTL labels."""

    @pytest.mark.parametrize(
        ("ttl", "expected"),
        [
            (Duration(days=2), "ttl_2d"),
            (Duration(hours=6), "ttl_6h"),
            (Duration(minutes=30), "ttl_30m"),
            (Duration(seconds=45), "ttl_45s"),
            (Duration(days=1), "ttl_1d"),
            (Duration(hours=1), "ttl_1h"),
            (Duration(minutes=1), "ttl_1m"),
            (Duration(seconds=0), "ttl_0s"),
        ],
    )
    def test_largest_whole_unit(self, ttl: Duration, expected: str) -> None:
        """The TTL is rendered using the largest whole unit at or below it."""
        assert format_ttl(ttl) == expected

    def test_boundaries_round_down_to_smaller_unit(self) -> None:
        """Durations just under a unit boundary fall back to the smaller unit."""
        assert format_ttl(Duration(hours=23, minutes=59)) == "ttl_23h"
        assert format_ttl(Duration(minutes=59, seconds=59)) == "ttl_59m"
