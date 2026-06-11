"""Tests for ``mayutils.objects.types``."""

from __future__ import annotations

from mayutils.objects.types import (
    SQL,
    JsonParsed,
    JsonString,
    JsonValue,
    RecursiveMapping,
    SupportsStr,
)


class TestSQL:
    """Tests for :data:`SQL` — a :class:`str` NewType for inline SQL."""

    def test_constructs_from_str(self) -> None:
        """The NewType constructor returns the underlying ``str`` value unchanged."""
        raw = "SELECT 1"
        assert SQL(raw) == raw

    def test_value_is_instance_of_str(self) -> None:
        """Instances returned by the NewType are plain :class:`str` at runtime."""
        assert isinstance(SQL("SELECT 1"), str)


class TestJsonString:
    """Tests for :data:`JsonString` — a :class:`str` NewType."""

    def test_constructs_from_str(self) -> None:
        """The NewType constructor returns the underlying ``str`` value unchanged."""
        raw = '{"a": 1}'
        assert JsonString(raw) == raw

    def test_value_is_instance_of_str(self) -> None:
        """Instances returned by the NewType are plain :class:`str` at runtime."""
        assert isinstance(JsonString("{}"), str)


class TestJsonValue:
    """Tests for :data:`JsonValue` — a recursive JSON value type alias."""

    def test_accepts_primitives(self) -> None:
        """All JSON primitive types satisfy the alias."""
        values: list[JsonValue] = ["text", 42, 3.14, True, False, None]
        assert len(values) == 6  # noqa: PLR2004

    def test_accepts_nested_structure(self) -> None:
        """Arbitrarily nested dicts and lists satisfy the alias."""
        nested: JsonValue = {"a": [1, {"b": [True, None]}], "c": "hello"}
        assert isinstance(nested, dict)

    def test_accepts_empty_containers(self) -> None:
        """Empty lists and dicts are valid JSON values."""
        empty_list: JsonValue = []
        empty_dict: JsonValue = {}
        assert empty_list == []
        assert empty_dict == {}


class TestJsonParsed:
    """Tests for :data:`JsonParsed` — a :class:`Mapping` NewType."""

    def test_wraps_dict(self) -> None:
        """A ``dict`` passed through the NewType round-trips unchanged."""
        payload: dict[str, int | list[int]] = {"a": 1, "b": [2, 3]}
        assert JsonParsed(payload) == payload


class TestRecursiveMapping:
    """Tests for :data:`RecursiveMapping` — a recursive type alias over :class:`~collections.abc.Mapping`."""

    def test_flat_dict_satisfies_alias(self) -> None:
        """A flat ``dict`` is assignable to the alias."""
        data: RecursiveMapping[str, int] = {"a": 1, "b": 2}
        assert data == {"a": 1, "b": 2}

    def test_nested_dict_satisfies_alias(self) -> None:
        """A nested ``dict`` whose values are leaves or sub-mappings satisfies the alias."""
        inner: RecursiveMapping[str, int] = {"c": 2}
        data: RecursiveMapping[str, int] = {"a": 1, "b": inner}
        assert data["b"] == {"c": 2}

    def test_is_type_alias(self) -> None:
        """The alias is a PEP 695 :class:`TypeAliasType` at runtime."""
        from typing import TypeAliasType

        assert isinstance(RecursiveMapping, TypeAliasType)


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
