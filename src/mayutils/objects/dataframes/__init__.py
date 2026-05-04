"""
Provide DataFrame backend dispatchers, accessors, and parquet I/O helpers.

Centralises utilities that work across the two DataFrame backends
supported by ``mayutils`` (pandas and polars). Exposes backend-agnostic
readers and writers for parquet artefacts, registers the ``.utils``
custom accessor namespace on pandas objects, and provides small
conversion helpers (such as spreadsheet-style column lettering) that
are shared between tabular workflows across the library.

See Also
--------
pandas.DataFrame : Canonical pandas DataFrame backend.
polars.DataFrame : Canonical polars DataFrame backend.
mayutils.objects.dataframes.pandas : Pandas-specific helpers and accessors.
mayutils.objects.dataframes.polars : Polars-specific helpers.

Examples
--------
>>> import pandas as pd
>>> from mayutils.objects.dataframes import infer_backend
>>> infer_backend(pd.DataFrame({"x": [1]}))
'pandas'
"""

from pathlib import Path

from mayutils.core.extras import may_require_extras
from mayutils.export import OUTPUT_FOLDER

with may_require_extras():
    from pandas.api.extensions import (
        register_dataframe_accessor,
        register_index_accessor,
        register_series_accessor,
    )

    from mayutils.objects.dataframes.pandas.dataframes import (
        DataframeUtilsAccessor,
    )
    from mayutils.objects.dataframes.pandas.index import (
        IndexUtilsAccessor,
    )
    from mayutils.objects.dataframes.pandas.series import (
        SeriesUtilsAccessor,
    )


DATA_FOLDER: Path = OUTPUT_FOLDER / "Data"
"""Default on-disk root for DataFrame artifacts."""


def setup_pandas() -> None:
    """
    Install ``mayutils`` custom accessors onto pandas objects.

    Attaches :class:`DataframeUtilsAccessor`, :class:`SeriesUtilsAccessor`,
    and :class:`IndexUtilsAccessor` to pandas via its extension API so
    that any DataFrame, Series, or Index gains a ``.utils`` namespace
    carrying helper methods defined in this package. The registration
    is global to the pandas module and therefore a process-wide effect.
    The function is invoked automatically by :func:`mayutils.setup`
    during package import, which is the standard path for enabling the
    accessors; callers may still invoke it explicitly (for example
    after a dynamic pandas reimport) and repeat invocations simply
    overwrite the existing registration with the same class. No
    equivalent hook exists for :mod:`polars`, :mod:`modin`, or
    :mod:`dask`, which expose their own extension mechanisms.

    See Also
    --------
    pandas.api.extensions.register_dataframe_accessor : Underlying pandas hook used here.
    pandas.api.extensions.register_series_accessor : Hook used for Series accessors.
    pandas.api.extensions.register_index_accessor : Hook used for Index accessors.
    mayutils.objects.dataframes.pandas.dataframes.DataframeUtilsAccessor : Registered DataFrame accessor.

    Examples
    --------
    >>> import pandas as pd
    >>> from mayutils.objects.dataframes import setup_pandas
    >>> setup_pandas()
    >>> df = pd.DataFrame({"a": [1, 2, 3]})
    >>> hasattr(df, "utils")
    True
    """
    register_dataframe_accessor(name="utils")(DataframeUtilsAccessor)
    register_series_accessor(name="utils")(SeriesUtilsAccessor)
    register_index_accessor(name="utils")(IndexUtilsAccessor)


__all__ = [
    "DATA_FOLDER",
    "setup_pandas",
]
