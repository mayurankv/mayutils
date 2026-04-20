"""Tests for ``mayutils.objects.numbers``."""

from __future__ import annotations

import pytest

from mayutils.objects.numbers import ordinal, prettify


class TestPrettify:
    """Tests for :func:`prettify` — formats numbers with SI-style magnitude suffixes."""

    def test_zero(self) -> None:
        """Zero formats as the literal string ``"0"`` (no suffix)."""
        assert prettify(0) == "0"

    @pytest.mark.parametrize(
        ("value", "expected_suffix"),
        [
            (1_500, "K"),
            (2_500_000, "M"),
            (1_234_567_890, "B"),
        ],
    )
    def test_suffix_scales(self, value: float, expected_suffix: str) -> None:
        """Each magnitude threshold picks up the correct SI suffix (K/M/B)."""
        assert prettify(value).endswith(expected_suffix)


class TestOrdinal:
    """Tests for :func:`ordinal` — turns an integer into its English ordinal form."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (1, "1st"),
            (2, "2nd"),
            (3, "3rd"),
            (4, "4th"),
            (11, "11th"),
            (12, "12th"),
            (13, "13th"),
            (21, "21st"),
            (22, "22nd"),
            (23, "23rd"),
            (101, "101st"),
        ],
    )
    def test_ordinals(self, value: int, expected: str) -> None:
        """Teens all take ``-th``; other two-digit endings follow the 1/2/3/4+ rule."""
        assert ordinal(value) == expected
