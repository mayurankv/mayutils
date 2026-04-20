"""DataFrame backend dispatchers, accessors, and parquet I/O helpers.

This package centralises utilities that work across the two DataFrame
backends supported by ``mayutils`` (pandas and polars). It exposes
backend-agnostic readers and writers for parquet artifacts, registers
the ``.utils`` custom accessor namespace on pandas objects, and
provides small conversion helpers (such as spreadsheet-style column
lettering) that are shared between tabular workflows across the
library.
"""

from pathlib import Path
from typing import Any, Literal, cast, get_args, overload

from mayutils.core.extras import may_require_extras
from mayutils.export import OUTPUT_FOLDER

with may_require_extras():
    import pandas as pd
    import polars as pl
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

type DataFrames = pd.DataFrame | pl.DataFrame
"""Union of supported concrete DataFrame types."""

DATA_FOLDER: Path = OUTPUT_FOLDER / "Data"
"""Default on-disk root for DataFrame artifacts."""


def to_parquet(
    df: DataFrames,
    path: Path | str,
    dataframe_backend: DataframeBackends | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> None:
    """Serialise a DataFrame to a parquet file using the matching backend writer.

    Dispatches to either ``pandas.DataFrame.to_parquet`` or
    ``polars.DataFrame.write_parquet`` depending on the concrete type
    of ``df``, providing a uniform call surface regardless of which
    DataFrame library produced the object.

    Parameters
    ----------
    df : pandas.DataFrame or polars.DataFrame
        The in-memory table whose contents are to be flushed to disk.
        Its concrete type drives automatic backend detection when
        ``dataframe_backend`` is left unspecified.
    path : Path or str
        Filesystem location for the output parquet file. A string is
        normalised to :class:`pathlib.Path` before being passed to the
        backend writer.
    dataframe_backend : {"pandas", "polars"} or None, optional
        Explicit override that selects which writer to invoke. When
        ``None`` (the default) the top-level module of ``type(df)`` is
        inspected to determine the backend automatically, which is the
        expected usage for most callers.
    **kwargs
        Additional keyword arguments forwarded verbatim to the
        underlying backend writer. For pandas the ``index`` keyword
        defaults to ``True`` when not supplied, preserving the
        DataFrame index in the output file.

    Returns
    -------
    None
        The function persists state to disk and returns no value.

    Raises
    ------
    TypeError
        If ``df`` is of a type whose top-level module is not one of the
        supported backends, or if an explicit ``dataframe_backend`` is
        supplied that does not match the known set.
    """
    path = Path(path)

    if dataframe_backend is None:
        module = type(df).__module__.split(sep=".")[0]

        if module not in get_args(DataframeBackends):
            msg = f"Unsupported DataFrame type: {module}"
            raise TypeError(msg)

        dataframe_backend = cast("DataframeBackends", module)

    if dataframe_backend == "pandas":
        if not isinstance(df, pd.DataFrame):
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
def read_parquet(
    path: Path | str,
    /,
    *,
    dataframe_backend: Literal["pandas"] = "pandas",
    **kwargs: Any,  # noqa: ANN401
) -> pd.DataFrame: ...


@overload
def read_parquet(
    path: Path | str,
    /,
    *,
    dataframe_backend: Literal["polars"],
    **kwargs: Any,  # noqa: ANN401
) -> pl.DataFrame: ...


@overload
def read_parquet(
    path: Path | str,
    /,
    *,
    dataframe_backend: DataframeBackends,
    **kwargs: Any,  # noqa: ANN401
) -> DataFrames: ...


def read_parquet(
    path: Path | str,
    /,
    *,
    dataframe_backend: DataframeBackends = "pandas",
    **kwargs: Any,
) -> DataFrames:
    """Load a parquet file into a DataFrame of the requested backend.

    Dispatches to ``pandas.read_parquet`` or ``polars.read_parquet``
    based on ``dataframe_backend`` so downstream code can consume the
    returned object with the preferred library API without performing
    an explicit conversion.

    Parameters
    ----------
    path : Path or str
        Filesystem location of the parquet file to be read. A string
        is normalised to :class:`pathlib.Path` before dispatch.
    dataframe_backend : {"pandas", "polars"}, optional
        Selects which backend's reader to call and therefore the
        concrete return type. Defaults to ``"pandas"`` to match the
        most common caller expectation in the library.
    **kwargs
        Additional keyword arguments forwarded verbatim to the
        underlying backend reader, allowing column projection, row
        group filtering, and other native options to flow through.

    Returns
    -------
    pandas.DataFrame or polars.DataFrame
        The materialised DataFrame containing the parsed parquet
        contents; its concrete type mirrors ``dataframe_backend``.

    Raises
    ------
    TypeError
        If ``dataframe_backend`` is not one of the supported literal
        values.
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
    """Install ``mayutils`` custom accessors onto pandas objects.

    Attaches the ``DataframeUtilsAccessor``, ``SeriesUtilsAccessor``,
    and ``IndexUtilsAccessor`` classes to pandas via its extension API
    so that any DataFrame, Series, or Index gains a ``.utils``
    namespace carrying helper methods defined in this package. The
    registration is global to the pandas module and therefore a
    process-wide effect.

    The function is invoked automatically by :func:`mayutils.setup`
    during package import, which is the standard path for enabling
    the accessors. Callers may still invoke it explicitly (for example
    after a dynamic pandas reimport); repeat invocations simply
    overwrite the existing registration with the same class.

    Returns
    -------
    None
        The function mutates pandas' accessor registry and returns no
        value.
    """
    register_dataframe_accessor(name="utils")(DataframeUtilsAccessor)
    register_series_accessor(name="utils")(SeriesUtilsAccessor)
    register_index_accessor(name="utils")(IndexUtilsAccessor)


def column_to_excel(
    column: int,
    /,
) -> str:
    """Translate a one-indexed column ordinal into spreadsheet letter notation.

    Applies the bijective base-26 encoding used by spreadsheets to map
    positive integers onto the sequence ``A``, ``B``, ..., ``Z``,
    ``AA``, ``AB``, ..., ``ZZ``, ``AAA``, ... This is the inverse of
    the letter-based column addressing used by Excel-compatible
    exporters across the library.

    Parameters
    ----------
    column : int
        The one-indexed position of the column, where ``1`` denotes
        the leftmost column. Values of ``0`` or below yield an empty
        string because the base-26 loop terminates immediately, so
        callers are expected to pass strictly positive integers.

    Returns
    -------
    str
        The uppercase letter sequence that identifies the column in
        spreadsheet notation, composed solely of ASCII characters
        ``A``-``Z``.

    Examples
    --------
    >>> column_to_excel(1)
    'A'
    >>> column_to_excel(27)
    'AA'
    >>> column_to_excel(702)
    'ZZ'
    """
    result: list[str] = []

    while column > 0:
        column, rem = divmod(column - 1, 26)
        result.append(chr(65 + rem))

    return "".join(reversed(result))


__all__ = [
    "DATA_FOLDER",
    "DataFrames",
    "DataframeBackends",
    "column_to_excel",
    "read_parquet",
    "setup_pandas",
    "to_parquet",
]
