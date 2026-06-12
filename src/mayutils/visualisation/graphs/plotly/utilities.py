"""Utility functions for Plotly chart rendering and data preparation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from mayutils.core.extras import may_require_extras

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import ArrayLike, NDArray
    from pandas import DataFrame


def include_plotly_js(
    *,
    include_tags: bool = True,
) -> str:
    """
    Return the bundled Plotly JavaScript library as a string.

    Reads ``plotly.min.js`` from the installed ``plotly`` package and
    optionally wraps it in ``<script>`` tags for direct HTML embedding.

    Parameters
    ----------
    include_tags
        When ``True``, wrap the JS source in ``<script>`` tags.

    Returns
    -------
    str
        The JavaScript source, optionally wrapped in HTML script tags.

    See Also
    --------
    melt_dataframe : Prepare DataFrame data for plotly traces.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.utilities import include_plotly_js
    >>> js = include_plotly_js(include_tags=False)
    >>> isinstance(js, str)
    True
    """
    with may_require_extras():
        import plotly

    pkg_path = Path(plotly.__path__[0])
    js_path = pkg_path / "package_data" / "plotly.min.js"
    plotly_js = js_path.read_text(encoding="utf-8")

    return (
        f"""
    <script type="text/javascript">
    {plotly_js}
    </script>
    """
        if include_tags
        else plotly_js
    )


def map_categorical_array(
    arr: NDArray[np.object_],
    /,
    *,
    mapping: ArrayLike | None = None,
) -> NDArray[np.int64]:
    """
    Convert a categorical array to integer codes.

    Each unique category is assigned an integer starting from 0. The
    ordering follows the first-seen order in *arr* unless an explicit
    *mapping* is provided.

    Parameters
    ----------
    arr
        1-D array of categorical (object) values.
    mapping
        Optional ordered array of unique categories defining the
        integer assignment. Must contain every value present in *arr*.

    Returns
    -------
    NDArray[np.int64]
        Integer-coded array with the same length as *arr*.

    Raises
    ------
    ValueError
        If *mapping* contains duplicate values or does not cover all
        categories in *arr*.

    See Also
    --------
    melt_dataframe : Reshape a DataFrame for use with plotly traces.

    Examples
    --------
    >>> import numpy as np
    >>> from mayutils.visualisation.graphs.plotly.utilities import map_categorical_array
    >>> arr = np.array(["a", "b", "a"], dtype=object)
    >>> map_categorical_array(arr).tolist()
    [0, 1, 0]
    """
    with may_require_extras():
        import numpy as np

    if mapping is not None:
        mapping_arr = np.asarray(mapping)
        if len(set(mapping_arr)) != len(mapping_arr):
            msg = "Mapping is not unique"
            raise ValueError(msg)
    else:
        mapping_arr = arr[sorted(np.unique(arr, return_index=True)[1])]

    mapping_dict = {value: idx for idx, value in enumerate(mapping_arr)}
    arr_numerical = np.asarray([mapping_dict.get(value, -1) for value in arr])

    if arr_numerical.min() != 0:
        msg = "Mapping is not complete"
        raise ValueError(msg)

    return arr_numerical


def melt_dataframe(
    df: DataFrame,
    /,
) -> tuple[NDArray[Any], NDArray[Any], NDArray[Any]]:
    """
    Melt a DataFrame into three arrays suitable for 3-D plotly traces.

    The DataFrame index becomes the first array, the melted column names
    become the second, and the cell values become the third.

    Parameters
    ----------
    df
        A DataFrame whose index and columns define two categorical
        dimensions and whose values form the third dimension.

    Returns
    -------
    tuple[NDArray[Any], NDArray[Any], NDArray[Any]]
        ``(index_values, column_names, cell_values)`` arrays.

    See Also
    --------
    map_categorical_array : Convert the categorical arrays to integer codes.

    Examples
    --------
    >>> import pandas as pd
    >>> from mayutils.visualisation.graphs.plotly.utilities import melt_dataframe
    >>> df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    >>> idx, cols, vals = melt_dataframe(df)
    >>> len(idx)
    4
    """
    values = df.melt(ignore_index=False).reset_index().to_numpy().transpose()

    return (
        values[0],
        values[1],
        values[2],
    )
