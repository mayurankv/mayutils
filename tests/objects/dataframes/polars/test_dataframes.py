"""Tests for ``mayutils.objects.dataframes.polars.dataframes``.

The polars dataframe module is currently a documentation/re-export surface with
no public transformation helpers yet (see its module docstring). These tests
pin that contract: the module and its package import cleanly under the
``polars`` extra and expose no public callables, so a regression that adds an
untested helper here is surfaced. Real transformation tests should be added
alongside any future helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import polars as pl
else:
    pl = pytest.importorskip("polars")

import mayutils.objects.dataframes.polars as polars_pkg
import mayutils.objects.dataframes.polars.dataframes as polars_dataframes


class TestModuleSurface:
    """Tests for the current (empty) public surface of the polars module."""

    def test_module_imports(self) -> None:
        """The polars dataframe module imports under the polars extra."""
        assert polars_dataframes.__name__ == "mayutils.objects.dataframes.polars.dataframes"

    def test_package_imports(self) -> None:
        """The polars subpackage namespace resolves to its dotted path."""
        assert polars_pkg.__name__ == "mayutils.objects.dataframes.polars"

    def test_no_public_callables_yet(self) -> None:
        """No public (non-dunder) helpers are defined in the module yet."""
        public = [name for name in vars(polars_dataframes) if not name.startswith("_")]
        assert public == []


class TestPolarsBaseline:
    """Sanity baseline confirming polars itself behaves as the docstring shows."""

    def test_sum_matches_docstring(self) -> None:
        """The module docstring's column-sum example evaluates to six."""
        frame = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        assert frame.select(pl.col("a").sum()).item() == 6  # noqa: PLR2004
