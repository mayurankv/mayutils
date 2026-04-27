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
from typing import Any, Literal, cast, get_args, overload

from mayutils.core.extras import may_require_extras
from mayutils.export import OUTPUT_FOLDER

with may_require_extras():
    import pandas as pd
    import polars as pl
    from pandas import DataFrame
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


type DataframeBackends = Literal["pandas", "polars"]
"""Supported DataFrame backends."""

type DataFrames = DataFrame | pl.DataFrame
"""Union of supported concrete DataFrame types."""

DATA_FOLDER: Path = OUTPUT_FOLDER / "Data"
"""Default on-disk root for DataFrame artifacts."""


def infer_backend(
    df: DataFrames,
    /,
) -> DataframeBackends:
    """
    Return the backend literal that matches a DataFrame's runtime type.

    Inspects the concrete class of ``df`` and maps it to one of the
    literal tags in :data:`DataframeBackends`. The helper is used by
    the backend-dispatching writers (parquet, csv, feather, xlsx, ...)
    to pick between the pandas and polars code paths when the caller
    does not supply an explicit backend override. Other DataFrame
    ecosystems such as :mod:`modin` or :mod:`dask` are intentionally
    not handled here.

    Parameters
    ----------
    df
        DataFrame whose concrete class identifies the backend.

    Returns
    -------
        ``"pandas"`` when ``df`` is a :class:`pandas.DataFrame`,
        otherwise ``"polars"``.

    See Also
    --------
    to_parquet : Backend-dispatching parquet writer that consumes this result.
    read_parquet : Backend-selecting parquet reader sibling helper.
    pandas.DataFrame : Concrete pandas type recognised by this helper.
    polars.DataFrame : Concrete polars type recognised by this helper.

    Examples
    --------
    >>> import pandas as pd
    >>> import polars as pl
    >>> from mayutils.objects.dataframes import infer_backend
    >>> infer_backend(pd.DataFrame({"a": [1, 2, 3]}))
    'pandas'
    >>> infer_backend(pl.DataFrame({"a": [1, 2, 3]}))
    'polars'
    """
    if isinstance(df, DataFrame):
        return "pandas"

    return "polars"


def to_parquet(
    df: DataFrames,
    path: Path | str,
    dataframe_backend: DataframeBackends | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> None:
    """
    Serialise a DataFrame to a parquet file via the matching backend writer.

    Dispatches to either :meth:`pandas.DataFrame.to_parquet` or
    :meth:`polars.DataFrame.write_parquet` depending on the concrete
    type of ``df``, providing a uniform call surface regardless of
    which DataFrame library produced the object. When ``dataframe_backend``
    is left as ``None`` the backend is inferred from the top-level module
    of ``type(df)``. Only the two supported backends are recognised;
    :mod:`modin` and :mod:`dask` objects must be converted beforehand.

    Parameters
    ----------
    df
        The in-memory table whose contents are flushed to disk. Its
        concrete type drives automatic backend detection when
        ``dataframe_backend`` is left unspecified.
    path
        Filesystem location for the output parquet file. A string is
        normalised to :class:`pathlib.Path` before being passed to the
        backend writer.
    dataframe_backend
        Explicit override that selects which writer to invoke. When
        ``None`` (the default) the top-level module of ``type(df)`` is
        inspected to determine the backend automatically, which is the
        expected usage for most callers.
    **kwargs
        Additional keyword arguments forwarded verbatim to the
        underlying backend writer. For pandas the ``index`` keyword
        defaults to ``True`` when not supplied, preserving the
        DataFrame index in the output file.

    Raises
    ------
    TypeError
        If ``df`` is of a type whose top-level module is not one of
        the supported backends, if the chosen backend does not match
        the runtime type of ``df``, or if an unknown literal is passed
        as ``dataframe_backend``.

    See Also
    --------
    read_parquet : Symmetrical reader that materialises a parquet file.
    infer_backend : Helper used to detect the backend when no override is given.
    pandas.DataFrame.to_parquet : Underlying writer for the pandas backend.
    polars.DataFrame.write_parquet : Underlying writer for the polars backend.

    Examples
    --------
    >>> import tempfile
    >>> import pandas as pd
    >>> import polars as pl
    >>> from pathlib import Path
    >>> from mayutils.objects.dataframes import to_parquet
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     pdf = pd.DataFrame({"a": [1, 2, 3]})
    ...     to_parquet(pdf, Path(tmp) / "example_pd.parquet", dataframe_backend="pandas")
    ...     ldf = pl.DataFrame({"a": [1, 2, 3]})
    ...     to_parquet(ldf, Path(tmp) / "example_pl.parquet", dataframe_backend="polars")
    """
    path = Path(path)

    if dataframe_backend is None:
        module = type(df).__module__.split(sep=".")[0]

        if module not in get_args(DataframeBackends):
            msg = f"Unsupported DataFrame type: {module}"
            raise TypeError(msg)

        dataframe_backend = cast("DataframeBackends", module)

    if dataframe_backend == "pandas":
        if not isinstance(df, DataFrame):
            msg = f"Expected a pandas DataFrame for backend 'pandas', got {type(df)}"
            raise TypeError(msg)

        df.to_parquet(
            path=path,
            index=kwargs.pop("index", True),
            **kwargs,
        )

    elif dataframe_backend == "polars":
        if not isinstance(df, pl.DataFrame):
            msg = f"Expected a polars DataFrame for backend 'polars', got {type(df)}"
            raise TypeError(msg)

        df.write_parquet(
            file=path,
            **kwargs,
        )

    else:
        msg = f"Unsupported DataFrame backend: {dataframe_backend}"
        raise TypeError(msg)


@overload
def read_parquet(  # numpydoc ignore=GL08
    path: Path | str,
    /,
    *,
    dataframe_backend: Literal["pandas"] = "pandas",
    **kwargs: object,
) -> DataFrame: ...


@overload
def read_parquet(  # numpydoc ignore=GL08
    path: Path | str,
    /,
    *,
    dataframe_backend: Literal["polars"],
    **kwargs: object,
) -> pl.DataFrame: ...


@overload
def read_parquet(  # numpydoc ignore=GL08
    path: Path | str,
    /,
    *,
    dataframe_backend: DataframeBackends,
    **kwargs: object,
) -> DataFrames: ...


def read_parquet(
    path: Path | str,
    /,
    *,
    dataframe_backend: DataframeBackends = "pandas",
    **kwargs: Any,
) -> DataFrames:
    """
    Load a parquet file into a DataFrame of the requested backend.

    Dispatches to :func:`pandas.read_parquet` or
    :func:`polars.read_parquet` based on ``dataframe_backend`` so
    downstream code can consume the returned object with the preferred
    library API without performing an explicit conversion. The default
    backend is pandas, matching the most common usage across the
    library; callers that want a columnar, zero-copy workflow can opt
    in to polars. Other ecosystems such as :mod:`modin` and
    :mod:`dask` are not supported by this helper.

    Parameters
    ----------
    path
        Filesystem location of the parquet file to be read. A string
        is normalised to :class:`pathlib.Path` before dispatch.
    dataframe_backend
        Selects which backend's reader to call and therefore the
        concrete return type. Defaults to ``"pandas"`` to match the
        most common caller expectation in the library.
    **kwargs
        Additional keyword arguments forwarded verbatim to the
        underlying backend reader, allowing column projection, row
        group filtering, and other native options to flow through.

    Returns
    -------
        The materialised DataFrame containing the parsed parquet
        contents; its concrete type mirrors ``dataframe_backend``.

    Raises
    ------
    TypeError
        If ``dataframe_backend`` is not one of the supported literal
        values.

    See Also
    --------
    to_parquet : Symmetrical writer that persists a DataFrame to parquet.
    infer_backend : Helper that maps a DataFrame to its backend literal.
    pandas.read_parquet : Underlying reader for the pandas backend.
    polars.read_parquet : Underlying reader for the polars backend.

    Examples
    --------
    >>> import tempfile
    >>> import pandas as pd
    >>> import polars as pl
    >>> from pathlib import Path
    >>> from mayutils.objects.dataframes import read_parquet, to_parquet
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     pdf_path = Path(tmp) / "example_pd.parquet"
    ...     pl_path = Path(tmp) / "example_pl.parquet"
    ...     to_parquet(pd.DataFrame({"a": [1, 2, 3]}), pdf_path, dataframe_backend="pandas")
    ...     to_parquet(pl.DataFrame({"a": [1, 2, 3]}), pl_path, dataframe_backend="polars")
    ...     pdf = read_parquet(pdf_path)
    ...     ldf = read_parquet(pl_path, dataframe_backend="polars")
    ...     pdf.shape, ldf.shape
    ((3, 1), (3, 1))
    """
    path = Path(path)

    if dataframe_backend == "pandas":
        return pd.read_parquet(
            path=path,
            **kwargs,
        )
    if dataframe_backend == "polars":
        return pl.read_parquet(
            source=path,
            **kwargs,
        )

    msg = f"Unsupported DataFrame backend: {dataframe_backend}"
    raise TypeError(msg)


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
    "DataFrames",
    "DataframeBackends",
    "infer_backend",
    "read_parquet",
    "setup_pandas",
    "to_parquet",
]
