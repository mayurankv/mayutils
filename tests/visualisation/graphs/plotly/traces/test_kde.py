"""Tests for ``mayutils.visualisation.graphs.plotly.traces.kde``.

The :class:`Kde` trace evaluates a Gaussian kernel density estimate over a
1000-point grid spanning the data range and delegates to :class:`Line`.
These tests reproduce the density independently with
:func:`scipy.stats.gaussian_kde` and assert the trace's ``x``/``y`` arrays
match via :func:`numpy.allclose`, covering the grid construction, default
(Scott's-rule) bandwidth, an explicit bandwidth, and the metadata defaults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("plotly")
pytest.importorskip("scipy")

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray
else:
    np = pytest.importorskip("numpy")

from scipy.stats import gaussian_kde

from mayutils.visualisation.graphs.plotly.traces.kde import Kde
from mayutils.visualisation.graphs.plotly.traces.types import TraceType

_GRID_SIZE = 1000
_SAMPLE: list[float] = [1.0, 2.0, 2.0, 3.0, 5.0, 8.0]


def _expected_grid(sample: list[float]) -> NDArray[np.float64]:
    """Return the 1000-point evaluation grid the trace builds for ``sample``.

    Parameters
    ----------
    sample
        The raw observation values.

    Returns
    -------
    NDArray[np.float64]
        ``linspace(min, max, 1000)`` over the sample range.
    """
    arr: NDArray[np.float64] = np.asarray(sample, dtype=np.float64)
    return np.linspace(start=float(np.min(arr)), stop=float(np.max(arr)), num=_GRID_SIZE)


class TestKdeGrid:
    """Tests for the evaluation grid spanning the data range."""

    def test_grid_spans_data_range(self) -> None:
        """The grid runs from the sample minimum to its maximum."""
        x = np.asarray(Kde(x=_SAMPLE).x, dtype=np.float64)
        assert np.isclose(x[0], min(_SAMPLE))
        assert np.isclose(x[-1], max(_SAMPLE))

    def test_grid_has_thousand_points(self) -> None:
        """The density is evaluated on exactly 1000 grid points."""
        trace = Kde(x=_SAMPLE)
        assert len(np.asarray(trace.x)) == _GRID_SIZE
        assert len(np.asarray(trace.y)) == _GRID_SIZE

    def test_grid_matches_linspace(self) -> None:
        """The grid equals ``linspace(min, max, 1000)`` over the data."""
        x = np.asarray(Kde(x=_SAMPLE).x, dtype=np.float64)
        assert np.allclose(x, _expected_grid(_SAMPLE))


class TestKdeDensity:
    """Tests for the density values against a direct scipy computation."""

    def test_default_bandwidth_matches_scipy(self) -> None:
        """Default (Scott's-rule) density matches ``gaussian_kde`` evaluated directly."""
        trace = Kde(x=_SAMPLE)
        grid = _expected_grid(_SAMPLE)
        expected = gaussian_kde(dataset=np.asarray(_SAMPLE), bw_method=None)(grid)
        assert np.allclose(np.asarray(trace.y, dtype=np.float64), expected)

    def test_density_is_non_negative(self) -> None:
        """A Gaussian KDE never produces negative density values."""
        y = np.asarray(Kde(x=_SAMPLE).y, dtype=np.float64)
        assert np.all(y >= 0)

    def test_partial_mass_matches_scipy_over_grid(self) -> None:
        """Trapezoidal mass over the clipped grid matches scipy's exact box integral.

        The grid spans only ``[min, max]`` of the data, so the Gaussian tails
        beyond that range are truncated and the mass is below 1.0; the curve
        nonetheless faithfully samples the underlying density.
        """
        x = np.asarray(Kde(x=_SAMPLE).x, dtype=np.float64)
        y = np.asarray(Kde(x=_SAMPLE).y, dtype=np.float64)
        area = float(np.trapezoid(y=y, x=x))
        reference = gaussian_kde(dataset=np.asarray(_SAMPLE), bw_method=None)
        expected = float(reference.integrate_box_1d(low=min(_SAMPLE), high=max(_SAMPLE)))
        assert expected < 1.0
        assert np.isclose(area, expected, atol=1e-3)


class TestKdeBandwidth:
    """Tests for the explicit ``bandwidth`` smoothing parameter."""

    def test_explicit_bandwidth_matches_scipy(self) -> None:
        """An explicit bandwidth is forwarded to ``gaussian_kde`` as ``bw_method``."""
        trace = Kde(x=_SAMPLE, bandwidth=0.5)
        grid = _expected_grid(_SAMPLE)
        expected = gaussian_kde(dataset=np.asarray(_SAMPLE), bw_method=0.5)(grid)
        assert np.allclose(np.asarray(trace.y, dtype=np.float64), expected)

    def test_bandwidth_changes_density(self) -> None:
        """A non-default bandwidth produces a different density curve."""
        default_y = np.asarray(Kde(x=_SAMPLE).y, dtype=np.float64)
        narrow_y = np.asarray(Kde(x=_SAMPLE, bandwidth=0.1).y, dtype=np.float64)
        assert not np.allclose(default_y, narrow_y)


class TestKdeTraceMetadata:
    """Tests for the trace defaults inherited from :class:`Line`."""

    def test_customdata_is_raw_sample(self) -> None:
        """``customdata`` carries the raw observations, not the grid."""
        trace = Kde(x=_SAMPLE)
        assert np.array_equal(np.asarray(trace.customdata, dtype=np.float64), np.asarray(_SAMPLE))

    def test_default_fill_is_tozeroy(self) -> None:
        """The KDE area fills down to the zero baseline by default."""
        assert Kde(x=_SAMPLE).fill == "tozeroy"

    def test_fill_override_is_respected(self) -> None:
        """A caller-supplied ``fill`` overrides the ``tozeroy`` default."""
        assert Kde(x=_SAMPLE, fill="toself").fill == "toself"

    def test_meta_is_kde_trace_type(self) -> None:
        """The trace carries the ``KDE`` trace-type marker in ``meta``."""
        assert Kde(x=_SAMPLE).meta == TraceType.KDE
