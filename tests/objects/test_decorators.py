"""Tests for ``mayutils.objects.decorators``."""

from __future__ import annotations

import doctest
import sys
import types
from typing import TYPE_CHECKING, Any

import pytest

from mayutils.objects.decorators import flexwrap

if TYPE_CHECKING:
    from collections.abc import Callable


class TestFlexwrap:
    """Tests for :func:`flexwrap` — bare + parameterised decorator dispatch."""

    @staticmethod
    def _make_shout() -> Callable[..., Any]:
        """Build a flexwrap-adapted decorator used across the tests.

        Returns
        -------
            A decorator built via :func:`flexwrap` that uppercases the
            wrapped function's string result and prepends ``prefix``.
        """

        @flexwrap
        def shout(func: Callable[..., str], /, *, prefix: str = "!") -> Callable[..., str]:
            def wrapper(*args: object, **kwargs: object) -> str:
                return prefix + func(*args, **kwargs).upper()

            return wrapper

        return shout

    def test_decorates_a_class(self) -> None:
        """Applying a flexwrap decorator to a class returns it without raising (no ``mappingproxy`` crash)."""

        @flexwrap
        def register[T](target: T, /) -> T:
            return target

        class Worker:
            def run(self) -> str:
                return "done"

        assert register(Worker) is Worker

    def test_class_method_doctests_are_discoverable(self) -> None:
        """A flexwrap-decorated class exposes its method doctests to ``doctest`` discovery (#7)."""
        module = types.ModuleType("flexwrap_doctest_probe")
        sys.modules[module.__name__] = module
        try:

            class Probe:
                """Probe decorator-class."""

                def __init__(self, func: Callable[..., object], /) -> None:
                    self._func = func

                def __call__(self, *args: object, **kwargs: object) -> object:
                    """Invoke the wrapped callable.

                    Parameters
                    ----------
                    *args
                        Positional arguments forwarded to the wrapped callable.
                    **kwargs
                        Keyword arguments forwarded to the wrapped callable.

                    Returns
                    -------
                        The wrapped callable's return value.
                    """
                    return self._func(*args, **kwargs)

                def ping(self) -> str:
                    """Return a pong.

                    Returns
                    -------
                        The literal string ``"pong"``.

                    Examples
                    --------
                    >>> 6 * 7
                    42
                    """
                    return "pong"

            # Simulate definition inside the probe module so doctest's
            # ``_from_module`` filter accepts the recursed methods.
            Probe.__module__ = module.__name__
            Probe.ping.__module__ = module.__name__

            flexwrap(Probe)

            found = {test.name for test in doctest.DocTestFinder().find(module, module.__name__) if test.examples}
            assert any(name.endswith("Probe.ping") for name in found), sorted(found)
        finally:
            del sys.modules[module.__name__]

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
            """Say hello.

            Returns
            -------
                The greeting text.
            """
            return "hello"

        assert greet.__name__ == "greet"
        assert greet.__doc__ is not None
        assert "Say hello." in greet.__doc__

    def test_positional_args_rejected(self) -> None:
        """The parameterised form refuses non-callable positional arguments."""
        shout = self._make_shout()

        with pytest.raises(expected_exception=TypeError, match="only supports keyword arguments"):
            shout("not-a-callable", "also-not")

    def test_parameterised_preserves_metadata(self) -> None:
        """Metadata survives the parameterised branch too."""
        shout = self._make_shout()

        @shout(prefix="? ")
        def question() -> str:
            """Ask something.

            Returns
            -------
                The question text.
            """
            return "what"

        assert question.__name__ == "question"
        assert question.__doc__ is not None
        assert "Ask something." in question.__doc__
        assert question() == "? WHAT"
