"""Tests for ``mayutils.visualisation.graphs.plotly.traces.ecdf``.

The :class:`Ecdf` trace turns raw observations into a step-wise CDF before
delegating to :class:`Line`.  These tests pin down the deterministic data
computation — the sorted ``x`` order, the (optionally weighted and
normalised) cumulative ``y`` values, the ``toself`` baseline-prepend, and the
``line_shape`` selection — by reading the arrays back off the constructed
plotly trace.  Pixel rendering is out of scope.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

import pytest

pytest.importorskip("plotly")

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray
else:
    np = pytest.importorskip("numpy")

from mayutils.visualisation.graphs.plotly.traces.ecdf import Ecdf
from mayutils.visualisation.graphs.plotly.traces.types import TraceType


def _xy(trace: Ecdf) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return the trace's ``x`` and ``y`` data as float arrays.

    Parameters
    ----------
    trace
        The constructed ECDF trace to read data off.

    Returns
    -------
    tuple[NDArray[np.float64], NDArray[np.float64]]
        The ``(x, y)`` data arrays cast to ``float64``.
    """
    return (
        np.asarray(trace.x, dtype=np.float64),
        np.asarray(trace.y, dtype=np.float64),
    )


class TestStandardEcdf:
    """Tests for the standard ascending ECDF data."""

    def test_probability_step_values(self) -> None:
        """A four-point sample yields evenly spaced 0.25 steps up to 1.0."""
        x, y = _xy(Ecdf(x=[1, 2, 3, 4], fill="tozeroy"))
        assert np.array_equal(x, np.array([1.0, 2.0, 3.0, 4.0]))
        assert np.allclose(y, np.array([0.25, 0.5, 0.75, 1.0]))

    def test_y_is_monotonic_non_decreasing(self) -> None:
        """The cumulative ``y`` values never decrease."""
        _, y = _xy(Ecdf(x=[5, 1, 4, 2, 3], fill="tozeroy"))
        assert np.all(np.diff(y) >= 0)

    def test_probability_reaches_one(self) -> None:
        """Probability normalisation makes the final step exactly 1.0."""
        _, y = _xy(Ecdf(x=[7, 3, 9, 1], fill="tozeroy"))
        assert np.isclose(y[-1], 1.0)

    def test_unsorted_input_matches_sorted(self) -> None:
        """Shuffled input produces the same sorted x/y arrays as ordered input."""
        sorted_x, sorted_y = _xy(Ecdf(x=[1, 2, 3, 4], fill="tozeroy"))
        shuffled_x, shuffled_y = _xy(Ecdf(x=[3, 1, 4, 2], fill="tozeroy"))
        assert np.array_equal(sorted_x, shuffled_x)
        assert np.allclose(sorted_y, shuffled_y)

    def test_single_point(self) -> None:
        """A single observation maps to its value at cumulative probability 1.0."""
        x, y = _xy(Ecdf(x=[5], fill="tozeroy"))
        assert np.array_equal(x, np.array([5.0]))
        assert np.allclose(y, np.array([1.0]))


class TestEcdfTies:
    """Tests for ECDF handling of duplicate observations."""

    def test_duplicates_kept_as_separate_steps(self) -> None:
        """Tied values are retained as distinct points, each adding a step."""
        x, y = _xy(Ecdf(x=[1, 2, 2, 3], fill="tozeroy"))
        assert np.array_equal(x, np.array([1.0, 2.0, 2.0, 3.0]))
        assert np.allclose(y, np.array([0.25, 0.5, 0.75, 1.0]))


class TestEcdfNorm:
    """Tests for the ``norm`` normalisation modes."""

    @pytest.mark.parametrize(
        ("norm", "expected"),
        [
            ("probability", [0.25, 0.5, 0.75, 1.0]),
            ("percentage", [25.0, 50.0, 75.0, 100.0]),
            ("count", [1.0, 2.0, 3.0, 4.0]),
        ],
    )
    def test_norm_scales_cumulative_sum(
        self,
        norm: Literal["probability", "percentage", "count"],
        expected: list[float],
    ) -> None:
        """Each norm rescales the cumulative count consistently."""
        _, y = _xy(Ecdf(x=[1, 2, 3, 4], norm=norm, fill="tozeroy"))
        assert np.allclose(y, np.array(expected))


class TestWeightedEcdf:
    """Tests for per-observation weighting via ``y``."""

    def test_weights_scale_step_heights(self) -> None:
        """Weights make step heights proportional to the cumulative weight."""
        _, y = _xy(Ecdf(x=[1, 2, 3], y=[1, 1, 2], fill="tozeroy"))
        assert np.allclose(y, np.array([0.25, 0.5, 1.0]))

    def test_weights_follow_x_sort_order(self) -> None:
        """Weights are reordered alongside ``x`` when the input is unsorted."""
        _, y = _xy(Ecdf(x=[3, 1, 2], y=[2, 1, 1], fill="tozeroy"))
        assert np.allclose(y, np.array([0.25, 0.5, 1.0]))

    def test_mismatched_lengths_raise(self) -> None:
        """A weight array of the wrong length raises ``ValueError``."""
        with pytest.raises(ValueError, match="not the same length"):
            Ecdf(x=[1, 2, 3], y=[1, 2])


class TestEcdfMode:
    """Tests for the ascending / reversed / complementary direction modes."""

    def test_reversed_orders_x_descending(self) -> None:
        """Reversed mode walks ``x`` from largest to smallest, ``y`` still 0->1."""
        x, y = _xy(Ecdf(x=[1, 2, 3, 4], mode="reversed", fill="tozeroy"))
        assert np.array_equal(x, np.array([4.0, 3.0, 2.0, 1.0]))
        assert np.allclose(y, np.array([0.25, 0.5, 0.75, 1.0]))

    def test_complementary_is_survival_function(self) -> None:
        """Complementary mode gives the survival curve descending to 0.0."""
        x, y = _xy(Ecdf(x=[1, 2, 3, 4], mode="complementary", fill="tozeroy"))
        assert np.array_equal(x, np.array([1.0, 2.0, 3.0, 4.0]))
        assert np.allclose(y, np.array([0.75, 0.5, 0.25, 0.0]))

    def test_complementary_plus_standard_sums_to_total(self) -> None:
        """Standard and complementary counts sum to the total at each step."""
        _, standard = _xy(Ecdf(x=[1, 2, 3, 4], mode="standard", norm="count", fill="tozeroy"))
        _, complementary = _xy(Ecdf(x=[1, 2, 3, 4], mode="complementary", norm="count", fill="tozeroy"))
        assert np.allclose(standard + complementary, 4.0)


class TestEcdfLineShape:
    """Tests for the ``line_shape`` step-direction selection."""

    @pytest.mark.parametrize(
        ("mode", "left_inclusive", "expected"),
        [
            ("standard", False, "vh"),
            ("standard", True, "hv"),
            ("reversed", False, "hv"),
            ("reversed", True, "vh"),
            ("complementary", False, "vh"),
            ("complementary", True, "hv"),
        ],
    )
    def test_line_shape_matrix(
        self,
        mode: Literal["standard", "reversed", "complementary"],
        *,
        left_inclusive: bool,
        expected: str,
    ) -> None:
        """``line_shape`` flips with mode and ``left_inclusive`` per the XOR rule."""
        trace = Ecdf(x=[1, 2, 3], mode=mode, left_inclusive=left_inclusive, fill="tozeroy")
        line = cast("dict[str, str]", trace.to_plotly_json()["line"])
        assert line["shape"] == expected


class TestEcdfYShift:
    """Tests for the vertical ``y_shift`` offset."""

    def test_shift_added_to_y_but_not_customdata(self) -> None:
        """``y_shift`` offsets ``y`` while ``customdata`` keeps the unshifted values."""
        trace = Ecdf(x=[1, 2], y_shift=10, fill="tozeroy")
        assert np.allclose(np.asarray(trace.y, dtype=np.float64), np.array([10.5, 11.0]))
        assert np.allclose(np.asarray(trace.customdata, dtype=np.float64), np.array([0.5, 1.0]))


class TestEcdfFillToSelf:
    """Tests for the ``toself`` baseline-prepend used by the default fill."""

    def test_toself_prepends_baseline_point(self) -> None:
        """``toself`` prepends ``(x[-1], y_shift)`` to close the filled area."""
        x, y = _xy(Ecdf(x=[10, 20, 30], fill="toself", y_shift=2))
        assert np.array_equal(x, np.array([30.0, 10.0, 20.0, 30.0]))
        assert np.allclose(y, np.array([2.0, 2.0 + 1 / 3, 2.0 + 2 / 3, 3.0]))

    def test_default_fill_is_toself(self) -> None:
        """The default fill prepends a point, lengthening x/y by one."""
        trace = Ecdf(x=[1, 2, 3])
        assert trace.fill == "toself"
        assert len(np.asarray(trace.x)) == 4  # noqa: PLR2004


class TestEcdfTraceMetadata:
    """Tests for the trace-type tagging inherited from :class:`Line`."""

    def test_meta_is_ecdf_trace_type(self) -> None:
        """The trace carries the ``ECDF`` trace-type marker in ``meta``."""
        assert Ecdf(x=[1, 2, 3]).meta == TraceType.ECDF
