"""Tests for ``mayutils.visualisation.graphs.plotly.utilities``.

The module exposes three pure helpers used while preparing data for plotly
traces: :func:`include_plotly_js` (loads the bundled JS), :func:`map_categorical_array`
(categorical-to-integer coding), and :func:`melt_dataframe` (long-form reshape).
These tests pin the deterministic input -> output behaviour and the documented
``ValueError`` paths; the JS bundle is only checked structurally.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("plotly")
pytest.importorskip("pandas")

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd
else:
    np = pytest.importorskip("numpy")
    pd = pytest.importorskip("pandas")

from mayutils.visualisation.graphs.plotly.utilities import (
    include_plotly_js,
    map_categorical_array,
    melt_dataframe,
)


class TestIncludePlotlyJs:
    """Tests for :func:`include_plotly_js`."""

    def test_returns_raw_source_without_tags(self) -> None:
        """Without tags the helper returns a non-empty raw JS string."""
        js = include_plotly_js(include_tags=False)
        assert isinstance(js, str)
        assert len(js) > 0
        assert "<script" not in js

    def test_wraps_in_script_tags(self) -> None:
        """With tags the JS source is wrapped in a ``<script>`` element."""
        js = include_plotly_js(include_tags=True)
        assert "<script" in js
        assert "</script>" in js


class TestMapCategoricalArray:
    """Tests for :func:`map_categorical_array` — categorical-to-integer coding."""

    def test_first_seen_order(self) -> None:
        """Without a mapping, codes follow the first-seen order of categories."""
        arr = np.array(["b", "a", "b", "c"], dtype=object)
        assert map_categorical_array(arr).tolist() == [0, 1, 0, 2]

    def test_repeated_values_share_codes(self) -> None:
        """Equal categories always receive the same integer code."""
        arr = np.array(["a", "b", "a"], dtype=object)
        assert map_categorical_array(arr).tolist() == [0, 1, 0]

    def test_returns_int64(self) -> None:
        """Codes are returned as an ``int64`` array."""
        arr = np.array(["a", "b"], dtype=object)
        assert map_categorical_array(arr).dtype == np.int64

    def test_explicit_mapping_defines_codes(self) -> None:
        """An explicit mapping sets the code assigned to each category."""
        arr = np.array(["a", "b", "a"], dtype=object)
        mapping = np.array(["b", "a"])
        assert map_categorical_array(arr, mapping=mapping).tolist() == [1, 0, 1]

    def test_duplicate_mapping_raises(self) -> None:
        """A mapping with repeated entries raises ``ValueError``."""
        arr = np.array(["a", "b"], dtype=object)
        with pytest.raises(ValueError, match="not unique"):
            map_categorical_array(arr, mapping=np.array(["a", "a"]))

    def test_incomplete_mapping_raises(self) -> None:
        """A mapping missing a present category raises ``ValueError``."""
        arr = np.array(["a", "z"], dtype=object)
        with pytest.raises(ValueError, match="not complete"):
            map_categorical_array(arr, mapping=np.array(["b", "a"]))


class TestMeltDataframe:
    """Tests for :func:`melt_dataframe` — long-form reshape into three arrays."""

    def test_returns_three_aligned_arrays(self) -> None:
        """The index, column-name, and value arrays line up element-wise."""
        df = pd.DataFrame({"x": [1, 2], "y": [3, 4]}, index=["r0", "r1"])
        index_values, column_names, cell_values = melt_dataframe(df)
        assert index_values.tolist() == ["r0", "r1", "r0", "r1"]
        assert column_names.tolist() == ["x", "x", "y", "y"]
        assert cell_values.tolist() == [1, 2, 3, 4]

    def test_length_is_rows_times_columns(self) -> None:
        """Each output array has one entry per (row, column) cell."""
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        index_values, column_names, cell_values = melt_dataframe(df)
        assert len(index_values) == 6  # noqa: PLR2004
        assert len(column_names) == len(cell_values) == len(index_values)

    def test_single_column(self) -> None:
        """A single-column frame melts to that column repeated per row."""
        df = pd.DataFrame({"only": [10, 20]})
        index_values, column_names, cell_values = melt_dataframe(df)
        assert index_values.tolist() == [0, 1]
        assert column_names.tolist() == ["only", "only"]
        assert cell_values.tolist() == [10, 20]
