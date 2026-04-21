"""Parquet-backed :class:`DataFile` subclass.

Wraps the backend-agnostic ``read_parquet`` / ``to_parquet`` helpers
from :mod:`mayutils.objects.dataframes` so the
:class:`~mayutils.interfaces.filetypes.DataFile` façade gets parquet
I/O without duplicating pandas/polars dispatch, and layers
metadata-cheap introspection and streaming reads on top through
``pyarrow.parquet``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Self, cast

from mayutils.core.extras import may_require_extras
from mayutils.interfaces.filetypes import DataFile
from mayutils.objects.dataframes import (
    DataframeBackends,
    DataFrames,
    read_parquet,
    to_parquet,
)

with may_require_extras():
    import pandas as pd
    import polars as pl
    import pyarrow as pa
    import pyarrow.parquet as pq

if TYPE_CHECKING:
    from collections.abc import Iterator


class Parquet(DataFile):
    """Handle to a parquet file with metadata-cheap introspection.

    Delegates round-trip I/O to the existing backend-aware helpers on
    :mod:`mayutils.objects.dataframes`, so :meth:`read` and
    :meth:`write` compose directly with the rest of the library's
    DataFrame plumbing. Schema and row-count reads go through the
    parquet footer (``pyarrow.parquet.ParquetFile``) so they don't
    touch the data body, and :meth:`iter_chunks` yields Arrow record
    batches converted to the requested DataFrame backend.
    """

    suffix: ClassVar[str] = ".parquet"

    def read(
        self,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> DataFrames:
        """Materialise the parquet file into a DataFrame.

        Parameters
        ----------
        dataframe_backend : {"pandas", "polars"} or None, optional
            Target DataFrame library. When ``None``, falls back to
            :attr:`backend`.
        **kwargs
            Forwarded to :func:`mayutils.objects.dataframes.read_parquet`
            (for example ``columns=[...]``).

        Returns
        -------
        pandas.DataFrame or polars.DataFrame
            Fully loaded DataFrame whose concrete type matches
            ``dataframe_backend``.
        """
        return read_parquet(
            self.path,
            dataframe_backend=dataframe_backend if dataframe_backend is not None else self.backend,
            **kwargs,
        )

    def write(
        self,
        df: DataFrames,
        /,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """Write a DataFrame to the parquet file.

        Parameters
        ----------
        df : pandas.DataFrame or polars.DataFrame
            DataFrame to persist.
        dataframe_backend : {"pandas", "polars"} or None, optional
            Explicit dispatch override; when ``None``, the backend is
            inferred from ``type(df)``.
        **kwargs
            Forwarded to the underlying writer (for example
            ``partition_cols=[...]`` on pandas).

        Returns
        -------
        Self
            The current handle, for fluent chaining.
        """
        if dataframe_backend is None:
            dataframe_backend = "pandas" if isinstance(df, pd.DataFrame) else "polars"

        to_parquet(
            df=df,
            path=self.path,
            dataframe_backend=dataframe_backend,
            **kwargs,
        )

        return self

    def schema(
        self,
    ) -> dict[str, Any]:
        """Return the column-to-arrow-dtype mapping from the parquet footer.

        Returns
        -------
        dict of str to Any
            Column name → :class:`pyarrow.DataType`.
        """
        arrow_schema = pq.ParquetFile(source=self.path).schema_arrow  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

        return {name: arrow_schema.field(name).type for name in arrow_schema.names}  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

    def row_count(
        self,
    ) -> int:
        """Return the number of rows using the parquet footer metadata.

        Returns
        -------
        int
            Total number of rows declared by the parquet file.
        """
        return pq.ParquetFile(source=self.path).metadata.num_rows  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

    def iter_chunks(
        self,
        chunk_size: int,
        /,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Iterator[DataFrames]:
        """Stream the parquet file as Arrow record batches.

        Parameters
        ----------
        chunk_size : int
            Upper bound on the number of rows per yielded chunk;
            forwarded as ``batch_size`` to
            :meth:`pyarrow.parquet.ParquetFile.iter_batches`.
        dataframe_backend : {"pandas", "polars"} or None, optional
            DataFrame library to convert each chunk to; defaults to
            :attr:`backend`.
        **kwargs
            Forwarded to :meth:`pyarrow.parquet.ParquetFile.iter_batches`
            (for example ``columns=[...]``).

        Yields
        ------
        pandas.DataFrame or polars.DataFrame
            Successive chunks whose concatenation equals the result
            of :meth:`read`.
        """
        backend = dataframe_backend if dataframe_backend is not None else self.backend
        parquet_file = pq.ParquetFile(source=self.path)

        for batch in parquet_file.iter_batches(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            batch_size=chunk_size,
            **kwargs,
        ):
            table = pa.Table.from_batches([batch])  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAttributeAccessIssue]

            yield pyarrow_table_to_backend(table, backend=backend)  # pyright: ignore[reportUnknownArgumentType]


def pyarrow_table_to_backend(
    table: pa.Table,  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownParameterType]
    /,
    *,
    backend: DataframeBackends,
) -> DataFrames:
    """Convert an Arrow table to the requested DataFrame backend.

    Parameters
    ----------
    table : pyarrow.Table
        Arrow table to convert.
    backend : {"pandas", "polars"}
        Target DataFrame library.

    Returns
    -------
    pandas.DataFrame or polars.DataFrame
        Materialised DataFrame whose concrete type matches ``backend``.
    """
    if backend == "polars":
        return cast("pl.DataFrame", pl.from_arrow(data=table))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]

    return cast("pd.DataFrame", table.to_pandas())  # pyright: ignore[reportUnknownMemberType]


__all__ = [
    "Parquet",
]
