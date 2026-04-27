"""
Provide pandas-specific accessors and styling utilities for mayutils dataframes.

This subpackage aggregates the pandas integration layer of ``mayutils``,
bundling together the ``.utils`` accessors registered on
:class:`pandas.DataFrame`, :class:`pandas.Series`, and
:class:`pandas.Index`, the dtype helpers used by those accessors, and
the image-capable :class:`Styler` subclass together with its row
formatter and style-map helpers. Re-exporting the public surface from a
single module allows downstream callers to import the pandas-specific
pieces without reaching into submodules, while keeping the accessor
registration driven by :func:`mayutils.objects.dataframes.setup_pandas`.

See Also
--------
pandas.DataFrame : Tabular type extended by :class:`DataframeUtilsAccessor`.
pandas.Series : One-dimensional type extended by :class:`SeriesUtilsAccessor`.
pandas.Index : Axis labels extended by :class:`IndexUtilsAccessor`.
pandas.io.formats.style.Styler : Base styling class specialised by :class:`Styler`.
mayutils.objects.dataframes.polars : Polars counterpart exposing analogous helpers.

Examples
--------
>>> import pandas as pd
>>> from mayutils.objects.dataframes import setup_pandas
>>> from mayutils.objects.dataframes.pandas import DataframeUtilsAccessor
>>> setup_pandas()
>>> df = pd.DataFrame({"a": [1, 2, 3]})
>>> isinstance(df.utils, DataframeUtilsAccessor)
True
"""

from mayutils.objects.dataframes.pandas.dataframes import (
    DataframeUtilsAccessor,
    DatetimeKind,
    DtypeSpec,
)
from mayutils.objects.dataframes.pandas.index import IndexUtilsAccessor
from mayutils.objects.dataframes.pandas.series import SeriesUtilsAccessor
from mayutils.objects.dataframes.pandas.stylers import (
    RowFormatter,
    StyleMap,
    Styler,
)

__all__ = [
    "DataframeUtilsAccessor",
    "DatetimeKind",
    "DtypeSpec",
    "IndexUtilsAccessor",
    "RowFormatter",
    "SeriesUtilsAccessor",
    "StyleMap",
    "Styler",
]
