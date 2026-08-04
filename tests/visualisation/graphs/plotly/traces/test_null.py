"""Tests for ``mayutils.visualisation.graphs.plotly.traces.null``.

The :class:`Null` trace fills empty ``SubPlot`` cells so their axis exists
before real traces are added. Without anchor data it must stay exactly as
before (empty ``x``/``y``, invisible via ``showlegend=False`` alone); when
given real ``x``/``y`` values borrowed from elsewhere in the grid, it must
render a genuinely invisible (fully transparent) line instead of an empty
trace, since Plotly only draws a subplot's axis tick labels when at least
one of its traces has real path geometry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

pytest.importorskip("plotly")

if TYPE_CHECKING:
    import numpy as np
else:
    np = pytest.importorskip("numpy")

from mayutils.visualisation.graphs.plotly.traces.null import Null
from mayutils.visualisation.graphs.plotly.traces.types import TraceType


class TestUnanchoredNull:
    """No ``x``/``y`` given: today's fully-empty placeholder behaviour."""

    def test_empty_data(
        self,
    ) -> None:
        """With no arguments, ``x`` and ``y`` are both empty."""
        trace = Null()

        assert np.array_equal(trace.x, ())
        assert np.array_equal(trace.y, ())

    def test_hidden_from_legend(
        self,
    ) -> None:
        """The trace never appears in the legend."""
        trace = Null()

        assert trace.showlegend is False

    def test_meta_tags_trace_type(
        self,
    ) -> None:
        """``meta`` carries the ``NULL`` trace type for downstream filtering."""
        trace = Null()

        assert trace.meta == TraceType.NULL

    def test_x_datetime_seeds_a_single_date(
        self,
    ) -> None:
        """``x_datetime=True`` seeds ``x`` with one date so Plotly infers a date axis."""
        trace = Null(x_datetime=True)

        assert len(trace.x) == 1
        assert np.array_equal(trace.y, ())

    def test_partial_anchor_falls_back_to_empty(
        self,
    ) -> None:
        """Supplying only one of ``x``/``y`` is treated as no anchor at all."""
        trace = Null(x=[1, 2])

        assert np.array_equal(trace.x, ())
        assert np.array_equal(trace.y, ())


class TestAnchoredNull:
    """Real ``x``/``y`` given: an invisible-but-real line placeholder."""

    def test_data_round_trips(
        self,
    ) -> None:
        """The supplied ``x``/``y`` are used verbatim, not fabricated."""
        trace = Null(x=[1, 2], y=[3, 4])

        assert np.array_equal(trace.x, (1, 2))
        assert np.array_equal(trace.y, (3, 4))

    def test_rendered_as_transparent_line(
        self,
    ) -> None:
        """The line renders (``mode="lines"``) but is fully transparent."""
        trace = Null(x=[1, 2], y=[3, 4])

        line = cast("dict[str, str]", trace.to_plotly_json()["line"])
        assert trace.mode == "lines"
        assert line["color"] == "rgba(0,0,0,0)"

    def test_hidden_from_legend_and_hover(
        self,
    ) -> None:
        """The anchored line still hides from the legend and hover."""
        trace = Null(x=[1, 2], y=[3, 4])

        assert trace.showlegend is False
        assert trace.hoverinfo == "skip"

    def test_meta_tags_trace_type(
        self,
    ) -> None:
        """``meta`` still carries the ``NULL`` trace type once anchored."""
        trace = Null(x=[1, 2], y=[3, 4])

        assert trace.meta == TraceType.NULL
