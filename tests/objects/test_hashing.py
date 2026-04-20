"""Tests for ``mayutils.objects.hashing``."""

from __future__ import annotations

from datetime import datetime

import pendulum
import pytest

from mayutils.objects.datetime import DateTime
from mayutils.objects.hashing import hash_inputs, serialise


class TestSerialise:
    """Tests for :func:`serialise` — JSON ``default`` callback for datetimes."""

    def test_stdlib_datetime_returns_iso(self) -> None:
        """A stdlib :class:`datetime` is converted to its ISO-8601 string."""
        dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=pendulum.timezone("UTC"))
        assert serialise(dt) == dt.isoformat()

    def test_pendulum_datetime_returns_iso(self) -> None:
        """A pendulum ``DateTime`` is converted to its ISO-8601 string."""
        dt = pendulum.datetime(2025, 1, 15, 10, 30, 0)
        assert serialise(dt) == dt.isoformat()

    def test_mayutils_datetime_returns_iso(self) -> None:
        """A mayutils ``DateTime`` is converted to its ISO-8601 string."""
        dt = DateTime(2025, 1, 15, 10, 30, 0)
        assert serialise(dt) == dt.isoformat()

    def test_unsupported_type_raises(self) -> None:
        """Non-datetime inputs raise :class:`TypeError`."""
        with pytest.raises(TypeError, match="not serialisable"):
            serialise(object())


class TestHashInputs:
    """Tests for :func:`hash_inputs` — deterministic SHA-256 over args/kwargs."""

    def test_digest_length(self) -> None:
        """Digest is 64 lowercase hex characters (SHA-256)."""
        digest = hash_inputs(1, "two", key=3)
        assert len(digest) == 64  # noqa: PLR2004
        assert all(c in "0123456789abcdef" for c in digest)

    def test_same_inputs_same_digest(self) -> None:
        """Repeating the same inputs produces an identical digest."""
        assert hash_inputs(1, 2, 3, key="value") == hash_inputs(1, 2, 3, key="value")

    def test_different_inputs_different_digest(self) -> None:
        """Any change in the payload changes the digest."""
        assert hash_inputs(1, 2) != hash_inputs(1, 3)

    def test_kwarg_order_does_not_matter(self) -> None:
        """Keyword argument ordering at the call site does not affect the digest."""
        assert hash_inputs(a=1, b=2) == hash_inputs(b=2, a=1)

    def test_positional_order_matters(self) -> None:
        """Positional argument order does affect the digest."""
        assert hash_inputs(1, 2) != hash_inputs(2, 1)

    def test_accepts_datetime_values(self) -> None:
        """Datetime-like inputs are serialised via :func:`serialise`."""
        dt = DateTime(2025, 1, 15, 10, 30, 0)
        digest_1 = hash_inputs(dt)
        digest_2 = hash_inputs(dt)
        assert digest_1 == digest_2

    def test_no_inputs_produces_stable_digest(self) -> None:
        """Calling with no arguments still produces a deterministic digest."""
        assert hash_inputs() == hash_inputs()
