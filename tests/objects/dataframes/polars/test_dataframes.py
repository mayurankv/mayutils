"""Tests for ``mayutils.objects.dataframes.polars.dataframes``.

These tests pin the module-surface contract: the module and its package
import cleanly under the ``polars`` extra and declare exactly the expected
public helpers via ``__all__``, so a regression that adds an untested helper
here is surfaced. Behavioural coverage for ``parse_temporal_columns`` lives
in ``test_temporal.py`` alongside this file.
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
    """Tests for the declared public surface of the polars module."""

    def test_module_imports(self) -> None:
        """The polars dataframe module imports under the polars extra."""
        assert polars_dataframes.__name__ == "mayutils.objects.dataframes.polars.dataframes"

    def test_package_imports(self) -> None:
        """The polars subpackage namespace resolves to its dotted path."""
        assert polars_pkg.__name__ == "mayutils.objects.dataframes.polars"

    def test_declared_public_surface(self) -> None:
        """Module and package both export exactly ``parse_temporal_columns``."""
        assert polars_dataframes.__all__ == ["parse_temporal_columns"]
        assert polars_pkg.__all__ == ["parse_temporal_columns"]
        assert polars_pkg.parse_temporal_columns is polars_dataframes.parse_temporal_columns


class TestPolarsBaseline:
    """Sanity baseline confirming polars itself behaves as the docstring shows."""

    def test_sum_matches_docstring(self) -> None:
        """The module docstring's column-sum example evaluates to six."""
        frame = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        assert frame.select(pl.col("a").sum()).item() == 6  # noqa: PLR2004
