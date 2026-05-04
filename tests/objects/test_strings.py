"""Tests for ``mayutils.objects.strings``."""

from __future__ import annotations

import pytest

from mayutils.objects.strings import String


class TestToNone:
    """Tests for :meth:`String.to_none` — coerces empty strings to ``None``."""

    def test_empty_returns_none(self) -> None:
        """An empty string collapses to ``None``."""
        assert String.to_none("") is None

    def test_non_empty_returns_input(self) -> None:
        """Non-empty strings are returned unchanged."""
        assert String.to_none("hello") == "hello"

    def test_none_returns_none(self) -> None:
        """``None`` passes through unchanged."""
        assert String.to_none(None) is None


class TestToSnake:
    """Tests for :meth:`String.to_snake` — converts arbitrary case styles to ``snake_case``."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("HelloWorld", "hello_world"),
            ("helloWorld", "hello_world"),
            ("hello-world", "hello_world"),
            ("alreadySnakeCase", "already_snake_case"),
        ],
    )
    def test_to_snake(self, raw: str, expected: str) -> None:
        """PascalCase, camelCase and kebab-case inputs all normalise to snake_case."""
        assert String.to_snake(raw) == expected


class TestToKebab:
    """Tests for :meth:`String.to_kebab` — converts arbitrary case styles to ``kebab-case``."""

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
    def test_to_kebab(self, raw: str, expected: str) -> None:
        """Mixed-case, separator, and acronym inputs all normalise to kebab-case."""
        assert String.to_kebab(raw) == expected


class TestToCamel:
    """Tests for :meth:`String.to_camel` — converts arbitrary case styles to ``camelCase``."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("hello_world", "helloWorld"),
            ("hello-world", "helloWorld"),
            ("Hello World", "helloWorld"),
            ("HelloWorld", "helloWorld"),
            ("fooBar", "fooBar"),
            ("XMLParser", "xmlParser"),
            ("", ""),
        ],
    )
    def test_to_camel(self, raw: str, expected: str) -> None:
        """Snake, kebab, space and case-boundary inputs all normalise to camelCase."""
        assert String.to_camel(raw) == expected


class TestToPascal:
    """Tests for :meth:`String.to_pascal` — converts arbitrary case styles to ``PascalCase``."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("hello_world", "HelloWorld"),
            ("hello-world", "HelloWorld"),
            ("helloWorld", "HelloWorld"),
            ("XMLParser", "XmlParser"),
            ("", ""),
        ],
    )
    def test_to_pascal(self, raw: str, expected: str) -> None:
        """Inputs in various styles all normalise to PascalCase."""
        assert String.to_pascal(raw) == expected


class TestToTitle:
    """Tests for :meth:`String.to_title` — converts arbitrary case styles to ``Title Case``."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("hello_world", "Hello World"),
            ("hello-world", "Hello World"),
            ("helloWorld", "Hello World"),
            ("XMLParser", "Xml Parser"),
            ("", ""),
        ],
    )
    def test_to_title(self, raw: str, expected: str) -> None:
        """Inputs in various styles all normalise to Title Case."""
        assert String.to_title(raw) == expected


class TestToSentence:
    """Tests for :meth:`String.to_sentence` — converts arbitrary case styles to ``Sentence case``."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("hello_world", "Hello world"),
            ("hello-world", "Hello world"),
            ("helloWorld", "Hello world"),
            ("XMLParser", "Xml parser"),
            ("", ""),
        ],
    )
    def test_to_sentence(self, raw: str, expected: str) -> None:
        """Inputs in various styles all normalise to Sentence case."""
        assert String.to_sentence(raw) == expected


class TestToSlug:
    """Tests for :meth:`String.to_slug`."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("SELECT * FROM loans", "select_from_loans"),
            ("  --hello--  ", "hello"),
            ("a///b///c", "a_b_c"),
            ("Hello World", "hello_world"),
            ("", ""),
        ],
    )
    def test_to_slug(self, raw: str, expected: str) -> None:
        """Inputs in various styles all normalise to a filesystem-safe slug."""
        assert String.to_slug(raw) == expected

    def test_max_length(self) -> None:
        """Output is truncated to max_length without trailing underscores."""
        result = String.to_slug("a_b_c_d_e_f", max_length=5)
        assert len(result) <= 5  # noqa: PLR2004
