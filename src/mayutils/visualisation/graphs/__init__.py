"""Graphing backend namespace for the visualisation layer.

This package groups the plotting helpers that sit on top of the supported
rendering libraries (Plotly, Matplotlib, Seaborn, ggplot). It centralises the
shared type aliases used to discriminate between backends so downstream
modules can dispatch on a single canonical literal rather than ad-hoc
strings, keeping the chart construction APIs backend-agnostic.
"""

from typing import Literal

type PlotType = Literal["plotly", "matplotlib", "seaborn", "ggplot"]
