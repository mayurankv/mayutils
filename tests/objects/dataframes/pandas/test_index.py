"""Tests for ``mayutils.objects.dataframes.pandas.index``.

Covers :meth:`IndexUtilsAccessor.get_multiindex`, which flattens a
:class:`pandas.MultiIndex` into nested Python lists in row- or level-oriented
form, including single- and multi-level indices and the non-``MultiIndex``
error case.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import pandas as pd
else:
    pd = pytest.importorskip("pandas")

from mayutils.objects.dataframes.pandas.index import IndexUtilsAccessor


class TestInit:
    """Tests for :meth:`IndexUtilsAccessor.__init__`."""

    def test_binds_index_by_reference(self) -> None:
        """The supplied index is stored verbatim."""
        index = pd.Index([1, 2, 3], name="n")
        assert IndexUtilsAccessor(index).index is index


class TestGetMultiindex:
    """Tests for :meth:`IndexUtilsAccessor.get_multiindex` — nested-list flattening."""

    def test_row_oriented(self) -> None:
        """Without transpose each inner list is one index row."""
        index = pd.MultiIndex.from_tuples([("a", 1), ("a", 2), ("b", 1)], names=["g", "n"])
        assert IndexUtilsAccessor(index).get_multiindex() == [["a", 1], ["a", 2], ["b", 1]]

    def test_level_oriented(self) -> None:
        """With transpose each inner list collects one level's values."""
        index = pd.MultiIndex.from_tuples([("a", 1), ("a", 2), ("b", 1)], names=["g", "n"])
        assert IndexUtilsAccessor(index).get_multiindex(transpose=True) == [["a", "a", "b"], [1, 2, 1]]

    def test_repeated_tuples_preserved(self) -> None:
        """Duplicate index entries appear repeatedly in the output."""
        index = pd.MultiIndex.from_tuples([("a", 1), ("a", 1)], names=["g", "n"])
        assert IndexUtilsAccessor(index).get_multiindex() == [["a", 1], ["a", 1]]

    def test_single_level_rows(self) -> None:
        """A single-level MultiIndex yields one-element inner rows."""
        index = pd.MultiIndex.from_tuples([("a",), ("b",)], names=["g"])
        assert IndexUtilsAccessor(index).get_multiindex() == [["a"], ["b"]]

    def test_single_level_transposed(self) -> None:
        """Transposing a single-level MultiIndex yields one inner level list."""
        index = pd.MultiIndex.from_tuples([("a",), ("b",)], names=["g"])
        assert IndexUtilsAccessor(index).get_multiindex(transpose=True) == [["a", "b"]]

    def test_three_levels_row_oriented(self) -> None:
        """Three-level rows carry all three values per entry."""
        index = pd.MultiIndex.from_tuples([("a", 1, "x"), ("b", 2, "y")], names=["l1", "l2", "l3"])
        assert IndexUtilsAccessor(index).get_multiindex() == [["a", 1, "x"], ["b", 2, "y"]]

    def test_three_levels_transposed(self) -> None:
        """Transposing three levels yields three inner level lists."""
        index = pd.MultiIndex.from_tuples([("a", 1, "x"), ("b", 2, "y")], names=["l1", "l2", "l3"])
        assert IndexUtilsAccessor(index).get_multiindex(transpose=True) == [["a", "b"], [1, 2], ["x", "y"]]

    def test_plain_index_raises(self) -> None:
        """A non-``MultiIndex`` has no levels to flatten and raises ``TypeError``."""
        with pytest.raises(expected_exception=TypeError, match="not of type MultiIndex"):
            IndexUtilsAccessor(pd.Index([1, 2, 3])).get_multiindex()
