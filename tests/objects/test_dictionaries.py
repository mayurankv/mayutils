"""Tests for ``mayutils.objects.dictionaries``."""

from __future__ import annotations

from mayutils.objects.dictionaries import invert_dict


class TestInvertDict:
    """Tests for :func:`invert_dict` — swap keys and values of a mapping."""

    def test_basic_swap(self) -> None:
        """Unique keys / values round-trip through inversion."""
        assert invert_dict({"a": 1, "b": 2}) == {1: "a", 2: "b"}

    def test_empty_mapping(self) -> None:
        """An empty input produces an empty dict."""
        assert invert_dict({}) == {}

    def test_duplicate_values_last_wins(self) -> None:
        """When values collide, the last key encountered in insertion order wins."""
        assert invert_dict({"a": 1, "b": 1}) == {1: "b"}

    def test_does_not_mutate_input(self) -> None:
        """The source mapping is not mutated by inversion."""
        source = {"a": 1, "b": 2}
        invert_dict(source)
        assert source == {"a": 1, "b": 2}

    def test_returns_new_dict(self) -> None:
        """The result is a fresh :class:`dict`, not an alias of the input."""
        source = {"a": 1}
        result = invert_dict(source)
        assert result is not source
        assert isinstance(result, dict)

    def test_heterogeneous_hashable_values(self) -> None:
        """Non-string hashable values work as destination keys."""
        assert invert_dict({"a": (1, 2), "b": frozenset({3})}) == {(1, 2): "a", frozenset({3}): "b"}
