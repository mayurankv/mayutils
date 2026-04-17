"""Tests for ``mayutils.objects.strings``."""

from __future__ import annotations

import pytest

from mayutils.objects.strings import (
    camel,
    kebabify,
    noneish_string,
    snakify,
    unsnakify,
)


class TestNoneishString:
    """Tests for :func:`noneish_string` — coerces empty strings to ``None``."""

    def test_empty_returns_none(self) -> None:
        """An empty string collapses to ``None``."""
        assert noneish_string(string="") is None

    def test_non_empty_returns_input(self) -> None:
        """Non-empty strings are returned unchanged."""
        assert noneish_string(string="hello") == "hello"

    def test_none_returns_none(self) -> None:
        """``None`` passes through unchanged."""
        assert noneish_string(string=None) is None


class TestSnakify:
    """Tests for :func:`snakify` — converts arbitrary case styles to ``snake_case``."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("HelloWorld", "hello_world"),
            ("helloWorld", "hello_world"),
            ("hello-world", "hello_world"),
            ("alreadySnakeCase", "already_snake_case"),
        ],
    )
    def test_snakify(self, raw: str, expected: str) -> None:
        """PascalCase, camelCase and kebab-case inputs all normalise to snake_case."""
        assert snakify(string=raw) == expected

    def test_roundtrip_snake_unsnake(self) -> None:
        """:func:`unsnakify` inverts snake-case into title-cased words."""
        assert unsnakify(string="hello_world") == "Hello World"


class TestKebabify:
    """Tests for :func:`kebabify` — converts arbitrary case styles to ``kebab-case``."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("HelloWorld", "hello-world"),
            ("helloWorld", "hello-world"),
            ("hello_world", "hello-world"),
            ("hello world", "hello-world"),
            ("HTTPResponse", "http-response"),
            ("alreadyKebabCase", "already-kebab-case"),
        ],
    )
    def test_kebabify(self, raw: str, expected: str) -> None:
        """Mixed-case, separator, and acronym inputs all normalise to kebab-case."""
        assert kebabify(string=raw) == expected


class TestCamel:
    """Tests for :func:`camel` — converts arbitrary case styles to ``camelCase``."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("hello_world", "helloWorld"),
            ("hello-world", "helloWorld"),
            ("Hello World", "helloWorld"),
        ],
    )
    def test_camel(self, raw: str, expected: str) -> None:
        """Snake, kebab and space-separated inputs all normalise to camelCase."""
        assert camel(string=raw) == expected
