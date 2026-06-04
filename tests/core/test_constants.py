"""Tests for ``mayutils.core.constants``.

The module is intentionally dependency-light: it documents the home for
shared package-level constants but currently declares no literal values or
singletons (those live behind the optional-extra feature submodules). These
tests therefore pin the module's "empty and import-safe" contract — it
imports without any optional extra and exposes no public constant names — so
that any future addition forces a deliberate, reviewed update here.
"""

from __future__ import annotations

import pytest

from mayutils.core import constants


class TestModuleIdentity:
    """Tests for the module's basic identity and import safety."""

    def test_module_name(self) -> None:
        """The module reports its fully qualified import name."""
        assert constants.__name__ == "mayutils.core.constants"

    def test_has_docstring(self) -> None:
        """The module ships a non-empty docstring describing its purpose."""
        assert constants.__doc__ is not None
        assert constants.__doc__.strip()


class TestNoPublicConstants:
    """Tests pinning that the module currently declares no public constants."""

    def test_exposes_no_public_names(self) -> None:
        """No public constant is defined; the module is currently a placeholder.

        Only genuine identifier-named attributes are considered: test-runner
        instrumentation (for example pytest's ``@py_builtins`` assertion-rewrite
        injections) uses ``@``-prefixed names that are not valid identifiers and
        is therefore excluded.
        """
        public_names = [name for name in vars(constants) if not name.startswith("_") and name.isidentifier()]
        assert public_names == []

    @pytest.mark.parametrize(
        "dunder",
        ["__name__", "__doc__", "__file__"],
    )
    def test_standard_dunders_present(self, dunder: str) -> None:
        """Standard module dunders remain available for introspection."""
        assert hasattr(constants, dunder)
