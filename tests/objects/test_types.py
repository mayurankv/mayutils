"""Tests for ``mayutils.objects.types``."""

from __future__ import annotations

from mayutils.objects.types import (
    JsonParsed,
    JsonString,
    RecursiveDict,
    SupportsStr,
)


class TestJsonString:
    """Tests for :data:`JsonString` — a :class:`str` NewType."""

    def test_constructs_from_str(self) -> None:
        """The NewType constructor returns the underlying ``str`` value unchanged."""
        raw = '{"a": 1}'
        assert JsonString(raw) == raw

    def test_value_is_instance_of_str(self) -> None:
        """Instances returned by the NewType are plain :class:`str` at runtime."""
        assert isinstance(JsonString("{}"), str)


class TestJsonParsed:
    """Tests for :data:`JsonParsed` — a :class:`Mapping` NewType."""

    def test_wraps_dict(self) -> None:
        """A ``dict`` passed through the NewType round-trips unchanged."""
        payload: dict[str, int | list[int]] = {"a": 1, "b": [2, 3]}
        assert JsonParsed(payload) == payload


class TestRecursiveDict:
    """Tests for :class:`RecursiveDict` — a recursively-typed dict subclass."""

    def test_is_dict_subclass(self) -> None:
        """Instances are true subclasses of :class:`dict`."""
        assert issubclass(RecursiveDict, dict)

    def test_constructs_flat(self) -> None:
        """A flat key/value mapping round-trips through the constructor."""
        data = RecursiveDict[str, int]({"a": 1, "b": 2})
        assert data == {"a": 1, "b": 2}

    def test_accepts_nested_values(self) -> None:
        """Nested :class:`RecursiveDict` values are retained as leaf mappings."""
        inner: RecursiveDict[str, int] = RecursiveDict()
        inner["c"] = 2
        data: RecursiveDict[str, int] = RecursiveDict()
        data["a"] = 1
        data["b"] = inner
        assert data["b"] == {"c": 2}

    def test_supports_mutation(self) -> None:
        """Standard ``dict`` mutation operations work on the subclass."""
        data: RecursiveDict[str, int] = RecursiveDict()
        data["k"] = 1
        assert data == {"k": 1}


class TestSupportsStr:
    """Tests for :class:`SupportsStr` — a structural protocol for stringifiable objects."""

    def test_str_satisfies_protocol(self) -> None:
        """Built-in :class:`str` instances satisfy the protocol at runtime."""

        def take(value: SupportsStr) -> str:
            return str(value)

        assert take("hello") == "hello"

    def test_int_satisfies_protocol(self) -> None:
        """Any object with ``__str__`` satisfies the protocol (e.g. :class:`int`)."""

        def take(value: SupportsStr) -> str:
            return str(value)

        assert take(42) == "42"

    def test_custom_class_satisfies_protocol(self) -> None:
        """A user-defined class with a ``__str__`` method satisfies the protocol."""

        class Named:
            def __str__(self) -> str:
                return "named"

        def take(value: SupportsStr) -> str:
            return str(value)

        assert take(Named()) == "named"
