"""Tests for ``mayutils.objects.functions``."""

from __future__ import annotations

import pytest

from mayutils.objects.functions import null, set_inline


class TestNull:
    """Tests for :func:`null` — a signature-compatible no-op callable."""

    def test_no_args_returns_none(self) -> None:
        """Calling with no arguments returns ``None``."""
        assert null() is None

    def test_positional_args_ignored(self) -> None:
        """Positional arguments are discarded and the result is still ``None``."""
        assert null(1, 2, 3) is None

    def test_keyword_args_ignored(self) -> None:
        """Keyword arguments are discarded and the result is still ``None``."""
        assert null(key="value", other=[1, 2]) is None

    def test_mixed_args_ignored(self) -> None:
        """Mixing positional and keyword arguments still returns ``None``."""
        assert null(1, "two", key=3) is None


class TestSetInline:
    """Tests for :func:`set_inline` — assign-and-return an item on a container."""

    def test_assigns_on_dict(self) -> None:
        """The key is added to a ``dict`` with the supplied value."""
        result = set_inline(parent_object={}, property_name="k", value=1)
        assert result == {"k": 1}

    def test_returns_same_object(self) -> None:
        """The returned reference is the mutated input, not a copy."""
        container: dict[str, int] = {"a": 0}
        result = set_inline(parent_object=container, property_name="a", value=42)
        assert result is container
        assert container == {"a": 42}

    def test_assigns_on_list(self) -> None:
        """An existing list index can be overwritten."""
        container = [0, 0, 0]
        set_inline(parent_object=container, property_name=1, value=9)  # pyright: ignore[reportArgumentType]
        assert container == [0, 9, 0]

    def test_invalid_list_index_raises(self) -> None:
        """Out-of-range list indices propagate :class:`IndexError`."""
        with pytest.raises(IndexError):
            set_inline(parent_object=[], property_name=0, value=1)  # pyright: ignore[reportArgumentType]
