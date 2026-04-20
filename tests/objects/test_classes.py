"""Tests for ``mayutils.objects.classes``."""

from __future__ import annotations

from typing import Any

import pytest

from mayutils.objects.classes import (
    BaseClass,
    add_method,
    adopt_super_methods,
    classonlyproperty,
    readonlyclassonlyproperty,
)


class TestClassOnlyProperty:
    """Tests for :class:`classonlyproperty` — a descriptor readable only on the class."""

    def test_reads_on_class(self) -> None:
        """Accessing the descriptor via the class returns the wrapped getter's result."""

        class Foo:
            @classonlyproperty
            def name(cls: type) -> str:  # noqa: N805 # pyright: ignore[reportGeneralTypeIssues]
                return cls.__name__

        assert Foo.name == "Foo"

    def test_instance_access_raises(self) -> None:
        """Reading the descriptor from an instance raises :class:`AttributeError`."""

        class Foo:
            @classonlyproperty
            def name(cls: type) -> str:  # noqa: N805 # pyright: ignore[reportGeneralTypeIssues]
                return cls.__name__

        with pytest.raises(AttributeError, match="class, not instances"):
            _ = Foo().name


class TestReadOnlyClassOnlyProperty:
    """Tests for :class:`readonlyclassonlyproperty` — forbids assignment at the class level."""

    def test_reads_on_class(self) -> None:
        """Read behaviour is inherited from :class:`classonlyproperty`."""

        class Foo:
            @readonlyclassonlyproperty
            def version(cls: type) -> int:  # noqa: N805 # pyright: ignore[reportGeneralTypeIssues]
                return 1

        assert Foo.version == 1

    def test_instance_assignment_raises(self) -> None:
        """Assigning via an instance raises :class:`AttributeError`."""

        class Foo:
            @readonlyclassonlyproperty
            def version(cls: type) -> int:  # noqa: N805 # pyright: ignore[reportGeneralTypeIssues]
                return 1

        with pytest.raises(AttributeError, match="read-only"):
            Foo().version = 2  # pyright: ignore[reportAttributeAccessIssue]


class TestBaseClass:
    """Tests for :class:`BaseClass` — a stable anchor for mixin utilities."""

    def test_is_instantiable(self) -> None:
        """:class:`BaseClass` carries no abstract methods and can be instantiated."""
        assert isinstance(BaseClass(), BaseClass)


class TestAddMethod:
    """Tests for :func:`add_method` — chainable method installation."""

    def test_installs_when_absent(self) -> None:
        """With no prior binding, the new method is called with ``prior_value=None``."""

        class Foo:
            pass

        captured: dict[str, Any] = {}

        def hook(self_obj: Foo, *_: Any, prior_value: int | None, **__: Any) -> int:  # noqa: ANN401, ARG001
            captured["prior"] = prior_value
            return 7

        add_method(Foo, hook, "run")

        result = Foo().run()  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType, reportAttributeAccessIssue]  # ty:ignore[unresolved-attribute]

        assert result == 7  # noqa: PLR2004
        assert captured["prior"] is None

    def test_chains_with_existing(self) -> None:
        """A pre-existing method's return value flows into ``prior_value``."""

        class Foo:
            def run(self) -> int:
                return 3

        def hook(self_obj: Foo, *_: Any, prior_value: int | None, **__: Any) -> int:  # noqa: ANN401, ARG001
            assert prior_value == 3  # noqa: PLR2004
            return prior_value + 1

        add_method(Foo, hook, "run")

        assert Foo().run() == 4  # noqa: PLR2004

    def test_none_result_preserves_prior(self) -> None:
        """Returning ``None`` from the hook keeps the existing return value."""

        class Foo:
            def run(self) -> int:
                return 5

        def hook(self_obj: Foo, *_: Any, prior_value: int | None, **__: Any) -> int | None:  # noqa: ANN401, ARG001
            return None

        add_method(Foo, hook, "run")

        assert Foo().run() == 5  # noqa: PLR2004

    def test_returns_class(self) -> None:
        """The decorator returns the class for chaining."""

        class Foo:
            pass

        def hook(self_obj: Foo, *_: Any, prior_value: int | None, **__: Any) -> int | None:  # noqa: ANN401, ARG001
            return None

        assert add_method(Foo, hook, "run") is Foo

    def test_forwards_args_and_kwargs(self) -> None:
        """Positional and keyword args flow through to the hook."""

        class Foo:
            pass

        def hook(
            self_obj: Foo,  # noqa: ARG001
            *args: Any,  # noqa: ANN401
            prior_value: tuple[tuple[Any, ...], dict[str, Any]] | None,  # noqa: ARG001
            **kwargs: Any,  # noqa: ANN401
        ) -> tuple[tuple[Any, ...], dict[str, Any]] | None:
            return args, kwargs

        add_method(Foo, hook, "run")

        assert Foo().run(1, 2, k=3) == ((1, 2), {"k": 3})  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]  # ty:ignore[unresolved-attribute]


class TestAdoptSuperMethods:
    """Tests for :func:`adopt_super_methods` — rewraps base methods to return ``self``."""

    def test_inherited_methods_return_self(self) -> None:
        """Wrapped base methods return the receiving instance so calls chain."""

        class Base:
            def foo(self) -> int:
                return 1

            def bar(self) -> int:
                return 2

        @adopt_super_methods
        class Sub(Base):
            pass

        instance = Sub()
        assert instance.foo() is instance
        assert instance.bar() is instance

    def test_overridden_methods_are_left_alone(self) -> None:
        """Methods already defined on the subclass are not rewrapped."""

        class Base:
            def foo(self) -> int:
                return 1

        @adopt_super_methods
        class Sub(Base):
            def foo(self) -> int:
                return 99

        assert Sub().foo() == 99  # noqa: PLR2004

    def test_returns_class(self) -> None:
        """The decorator returns the decorated class itself."""

        class Base:
            def foo(self) -> int:
                return 1

        decorated = adopt_super_methods(type("Sub", (Base,), {}))
        assert decorated.__name__ == "Sub"

    def test_dunder_attributes_skipped(self) -> None:
        """Double-underscore attributes on the base are not rewrapped."""

        class Base:
            def foo(self) -> int:
                return 1

        @adopt_super_methods
        class Sub(Base):
            pass

        # __init__ / __repr__ etc. remain intact and return their native values
        assert Sub().__class__.__name__ == "Sub"
