"""Tests for ``mayutils.objects.decorators``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from mayutils.objects.decorators import flexwrap

if TYPE_CHECKING:
    from collections.abc import Callable


class TestFlexwrap:
    """Tests for :func:`flexwrap` — bare + parameterised decorator dispatch."""

    @staticmethod
    def _make_shout() -> Callable[..., Any]:
        """Build a flexwrap-adapted decorator used across the tests."""

        @flexwrap
        def shout(func: Callable[..., str], prefix: str = "!") -> Callable[..., str]:
            def wrapper(*args: Any, **kwargs: Any) -> str:  # noqa: ANN401
                return prefix + func(*args, **kwargs).upper()

            return wrapper

        return shout

    def test_bare_form(self) -> None:
        """``@deco`` (no call) wraps the function with defaults."""
        shout = self._make_shout()

        @shout
        def hello() -> str:
            return "hi"

        assert hello() == "!HI"

    def test_parameterised_form(self) -> None:
        """``@deco(**kwargs)`` wraps the function with the given configuration."""
        shout = self._make_shout()

        @shout(prefix=">>> ")
        def hey() -> str:
            return "hey"

        assert hey() == ">>> HEY"

    def test_preserves_function_metadata(self) -> None:
        """Wrapped functions keep their original ``__name__`` and ``__doc__``."""
        shout = self._make_shout()

        @shout
        def greet() -> str:
            """Say hello."""
            return "hello"

        assert greet.__name__ == "greet"
        assert greet.__doc__ == "Say hello."

    def test_positional_args_rejected(self) -> None:
        """The parameterised form refuses non-callable positional arguments."""
        shout = self._make_shout()

        with pytest.raises(TypeError, match="only supports keyword arguments"):
            shout("not-a-callable", "also-not")  # pyright: ignore[reportCallIssue]

    def test_parameterised_preserves_metadata(self) -> None:
        """Metadata survives the parameterised branch too."""
        shout = self._make_shout()

        @shout(prefix="? ")
        def question() -> str:
            """Ask something."""
            return "what"

        assert question.__name__ == "question"
        assert question.__doc__ == "Ask something."
        assert question() == "? WHAT"
