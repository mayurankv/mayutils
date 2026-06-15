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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mayutils.objects.dataframes.pandas.dataframes import (
        DataframeUtilsAccessor,
        DatetimeKind,
        DtypeSpec,
        parse_temporal_columns,
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
    "parse_temporal_columns",
]


def __getattr__(
    name: str,
) -> object:
    """
    Materialise the lazily exported pandas accessor symbols on first access.

    The accessor classes and dtype helpers live in submodules that import
    pandas, and :class:`Styler` subclasses a pandas styler base, so importing
    their defining modules requires the optional dataframe extras. Deferring
    those imports to first attribute access (and caching the result back into
    the module globals) keeps this package importable without pandas while
    preserving the public ``mayutils.objects.dataframes.pandas`` surface.

    Parameters
    ----------
    name
        Attribute being looked up on the module.

    Returns
    -------
        The requested accessor class, dtype helper or styler symbol.

    Raises
    ------
    AttributeError
        If *name* is not a lazily materialised attribute.

    See Also
    --------
    mayutils.objects.dataframes.pandas.index.IndexUtilsAccessor : One of the
        lazily exported accessor classes.
    mayutils.objects.dataframes.setup_pandas : Registers these accessors on
        the pandas namespace.

    Examples
    --------
    >>> from mayutils.objects.dataframes.pandas import IndexUtilsAccessor
    >>> IndexUtilsAccessor.__name__
    'IndexUtilsAccessor'
    """
    submodules = {
        "DataframeUtilsAccessor": "dataframes",
        "DatetimeKind": "dataframes",
        "DtypeSpec": "dataframes",
        "IndexUtilsAccessor": "index",
        "RowFormatter": "stylers",
        "SeriesUtilsAccessor": "series",
        "StyleMap": "stylers",
        "Styler": "stylers",
        "parse_temporal_columns": "dataframes",
    }

    if name not in submodules:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)

    from importlib import import_module

    value: object = getattr(import_module(f"{__name__}.{submodules[name]}"), name)
    globals()[name] = value

    return value
