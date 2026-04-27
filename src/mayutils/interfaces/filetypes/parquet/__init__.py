"""
Expose a parquet-backed :class:`DataFile` subclass for the filetype facade.

Wraps the backend-agnostic ``read_parquet`` / ``to_parquet`` helpers
from :mod:`mayutils.objects.dataframes` so the
:class:`~mayutils.interfaces.filetypes.DataFile` façade gets parquet
I/O without duplicating pandas/polars dispatch, and layers
metadata-cheap introspection and streaming reads on top through
``pyarrow.parquet``. The module is intentionally small so that the
parquet-specific surface stays close to the underlying Arrow
metadata rather than re-implementing footer parsing.

See Also
--------
mayutils.interfaces.filetypes.DataFile : Base class the subclass extends.
mayutils.interfaces.filetypes.feather : Sibling Feather adapter.
mayutils.interfaces.filetypes.csv : Sibling CSV adapter.
pyarrow.parquet : Underlying metadata and streaming backend.
pandas.read_parquet : Pandas reader dispatched to by ``_read``.
polars.read_parquet : Polars reader dispatched to by ``_read``.

Examples
--------
>>> from pathlib import Path
>>> from mayutils.interfaces.filetypes.parquet import Parquet
>>> handle = Parquet(Path("events.parquet"))
>>> handle.suffix
'.parquet'
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, cast

from mayutils.core.extras import may_require_extras
from mayutils.interfaces.filetypes import DataFile
from mayutils.objects.dataframes import (
    DataframeBackends,
    DataFrames,
    read_parquet,
    to_parquet,
)

with may_require_extras():
    import polars as pl
    import pyarrow as pa
    import pyarrow.parquet as pq

if TYPE_CHECKING:
    from collections.abc import Iterator


class Parquet(DataFile):
    """
    Handle a parquet file with metadata-cheap introspection and streaming.

    Delegates round-trip I/O to the existing backend-aware helpers on
    :mod:`mayutils.objects.dataframes`, so :meth:`read` and
    :meth:`write` compose directly with the rest of the library's
    DataFrame plumbing. Schema and row-count reads go through the
    parquet footer (``pyarrow.parquet.ParquetFile``) so they don't
    touch the data body, and :meth:`iter_chunks` yields Arrow record
    batches converted to the requested DataFrame backend.

    See Also
    --------
    mayutils.interfaces.filetypes.DataFile : Abstract base providing the facade.
    mayutils.interfaces.filetypes.feather.Feather : Sibling Arrow IPC adapter.
    pyarrow.parquet.ParquetFile : Footer-level parquet reader used for metadata.
    pandas.read_parquet : Pandas reader dispatched to by :meth:`_read`.
    polars.read_parquet : Polars reader dispatched to by :meth:`_read`.

    Examples
    --------
    >>> from pathlib import Path
    >>> from mayutils.interfaces.filetypes.parquet import Parquet
    >>> handle = Parquet(Path("events.parquet"))
    >>> handle.path.suffix
    '.parquet'
    """

    suffix: ClassVar[str] = ".parquet"

    def _read(
        self,
        *,
        dataframe_backend: DataframeBackends,
        **kwargs: object,
    ) -> DataFrames:
        """
        Materialise the parquet file into a DataFrame.

        Dispatches to :func:`mayutils.objects.dataframes.read_parquet`,
        which selects between pandas and polars readers based on
        ``dataframe_backend``. The helper transparently handles both
        single-file and directory-style partitioned parquet datasets,
        with pyarrow doing the heavy lifting of combining row groups
        and applying any column projection supplied through
        ``kwargs``.

        Parameters
        ----------
        dataframe_backend
            Resolved DataFrame library to return. The value has
            already been resolved against :attr:`backend` by
            :meth:`DataFile.read` so implementations do not need to
            treat ``None`` as a default.
        **kwargs
            Forwarded to :func:`mayutils.objects.dataframes.read_parquet`
            (for example ``columns=[...]`` to project a subset of
            columns or ``filters=[...]`` for predicate pushdown).

        Returns
        -------
            Fully loaded DataFrame whose concrete type matches
            ``dataframe_backend``.

        See Also
        --------
        mayutils.objects.dataframes.read_parquet : Dispatched-to reader.
        Parquet._write : Symmetric writer on this subclass.
        Parquet.iter_chunks : Streaming alternative for large files.
        pyarrow.parquet.read_table : Underlying Arrow reader.
        pandas.read_parquet : Pandas reader selected for the pandas backend.
        polars.read_parquet : Polars reader selected for the polars backend.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.parquet import Parquet
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     path = Path(tmp) / "demo.parquet"
        ...     pd.DataFrame({"id": [1, 2, 3], "ts": [10, 20, 30]}).to_parquet(path)
        ...     df = Parquet(path)._read(
        ...         dataframe_backend="pandas",
        ...         columns=["id"],
        ...     )
        ...     df.shape
        (3, 1)
        """
        return read_parquet(
            self.path,
            dataframe_backend=dataframe_backend,
            **kwargs,
        )

    def _write(
        self,
        df: DataFrames,
        /,
        *,
        dataframe_backend: DataframeBackends,
        **kwargs: object,
    ) -> None:
        """
        Persist a DataFrame to the parquet file.

        Delegates to
        :func:`mayutils.objects.dataframes.to_parquet`, which picks
        the pandas or polars writer matching ``dataframe_backend``.
        Format-specific controls such as compression codec
        (``snappy``, ``zstd``, ``gzip``), partition layout
        (``partition_cols``), and row-group sizing are forwarded
        through ``kwargs`` so callers can tune on-disk layout without
        touching this dispatcher.

        Parameters
        ----------
        df
            DataFrame to persist; its runtime type has already been
            validated against ``dataframe_backend`` by
            :meth:`DataFile.write`.
        dataframe_backend
            Resolved backend that matches ``type(df)``.
        **kwargs
            Forwarded to the underlying writer (for example
            ``compression="zstd"`` for a denser codec or
            ``partition_cols=[...]`` on pandas for Hive-style
            partitioning).

        See Also
        --------
        mayutils.objects.dataframes.to_parquet : Dispatched-to writer.
        Parquet._read : Symmetric reader on this subclass.
        pyarrow.parquet.write_table : Underlying Arrow writer.
        pandas.DataFrame.to_parquet : Pandas writer dispatched to.
        polars.DataFrame.write_parquet : Polars writer dispatched to.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.parquet import Parquet
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     path = Path(tmp) / "demo.parquet"
        ...     Parquet(path)._write(
        ...         pd.DataFrame({"id": [1, 2, 3]}),
        ...         dataframe_backend="pandas",
        ...         compression="zstd",
        ...     )
        ...     path.exists()
        True
        """
        to_parquet(
            df=df,
            path=self.path,
            dataframe_backend=dataframe_backend,
            **kwargs,
        )

    def schema(
        self,
    ) -> dict[str, object]:
        """
        Return the column-to-arrow-dtype mapping from the parquet footer.

        Reads only the parquet footer through
        ``pyarrow.parquet.ParquetFile`` so the data body is never
        materialised. The mapping preserves declaration order, and
        the values are raw :class:`pyarrow.DataType` instances rather
        than library-converted dtypes, which keeps the dtype
        information lossless across pandas/polars consumers.

        Returns
        -------
            Column name to :class:`pyarrow.DataType` mapping declared
            by the parquet footer.

        See Also
        --------
        DataFile.columns : Column-name-only wrapper.
        DataFile.dtypes : Full-mapping alias.
        Parquet.row_count : Sibling metadata-only helper.
        pyarrow.parquet.ParquetFile.schema_arrow : Underlying Arrow schema accessor.
        pyarrow.Schema : Container for the returned field types.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.parquet import Parquet
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     path = Path(tmp) / "demo.parquet"
        ...     pd.DataFrame({"id": [1, 2, 3], "ts": [10, 20, 30]}).to_parquet(path)
        ...     list(Parquet(path).schema())
        ['id', 'ts']
        """
        arrow_schema = pq.ParquetFile(source=self.path).schema_arrow  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

        return {name: arrow_schema.field(name).type for name in arrow_schema.names}  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

    def row_count(
        self,
    ) -> int:
        """
        Return the total row count from the parquet footer metadata.

        Reads only the ``num_rows`` field in the parquet footer via
        ``pyarrow.parquet.ParquetFile.metadata`` so the data body is
        never touched. This is typically orders of magnitude cheaper
        than a full scan for files with large row groups, making it
        the preferred way to gate conversions or decide between
        :meth:`read` and :meth:`iter_chunks`.

        Returns
        -------
            Non-negative total number of rows declared by the parquet
            file, summed across all row groups.

        See Also
        --------
        DataFile.size : Byte-level counterpart.
        DataFile.iter_chunks : Streaming alternative to full reads.
        Parquet.schema : Sibling metadata-only helper.
        pyarrow.parquet.ParquetFile.metadata : Source of ``num_rows``.
        pyarrow.parquet.FileMetaData.num_rows : Exact field read.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.parquet import Parquet
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     path = Path(tmp) / "demo.parquet"
        ...     pd.DataFrame({"id": list(range(7))}).to_parquet(path)
        ...     Parquet(path).row_count()
        7
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
        """
        Stream the parquet file as DataFrame chunks converted from Arrow batches.

        Iterates the parquet file through
        :meth:`pyarrow.parquet.ParquetFile.iter_batches`, converting
        each record batch into a single-batch Arrow table and then
        into the requested DataFrame backend. Record-batch streaming
        respects row-group boundaries, so memory usage stays bounded
        by ``chunk_size`` rather than the total file size, which
        makes this the right entry point for parquet files larger
        than RAM.

        Parameters
        ----------
        chunk_size
            Upper bound on the number of rows per yielded chunk;
            forwarded as ``batch_size`` to
            :meth:`pyarrow.parquet.ParquetFile.iter_batches`. The
            final chunk may be smaller when the total row count is
            not an exact multiple of ``chunk_size``.
        dataframe_backend
            DataFrame library to convert each chunk to; defaults to
            :attr:`backend` when ``None``.
        **kwargs
            Forwarded to :meth:`pyarrow.parquet.ParquetFile.iter_batches`
            (for example ``columns=[...]`` to restrict the projection
            or ``row_groups=[...]`` to scan only specific row groups).

        Yields
        ------
            Successive chunks whose concatenation equals the result
            of :meth:`read`. Each chunk has at most ``chunk_size``
            rows and its concrete type matches the resolved backend.

        See Also
        --------
        DataFile.read : Full-materialisation counterpart.
        DataFile.row_count : Size hint for sizing ``chunk_size``.
        Parquet._read : Whole-file reader that shares the same dispatch.
        pyarrow.parquet.ParquetFile.iter_batches : Underlying batch iterator.
        pyarrow_table_to_backend : Helper used for per-chunk conversion.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.parquet import Parquet
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     path = Path(tmp) / "demo.parquet"
        ...     pd.DataFrame({"id": list(range(5))}).to_parquet(path)
        ...     sizes = [len(chunk) for chunk in Parquet(path).iter_chunks(2)]
        ...     sum(sizes)
        5
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
    """
    Convert an Arrow table to the requested DataFrame backend.

    Exists so both :meth:`Parquet.iter_chunks` and any future Arrow
    producers in this module can share a single conversion path. The
    helper prefers zero-copy conversions where the underlying
    library supports them: ``polars.from_arrow`` returns a polars
    DataFrame that shares Arrow buffers, and ``pyarrow.Table.to_pandas``
    picks the appropriate pandas representation for each column type.

    Parameters
    ----------
    table
        Arrow table to convert. May be a single-batch or multi-batch
        table; the function does not re-chunk it.
    backend
        Target DataFrame library.

    Returns
    -------
        Materialised DataFrame whose concrete type matches
        ``backend``.

    See Also
    --------
    Parquet.iter_chunks : Primary caller of this helper.
    pyarrow.Table.to_pandas : Backend-specific conversion for pandas.
    polars.from_arrow : Backend-specific conversion for polars.
    pandas.DataFrame : Concrete return type for the pandas backend.
    polars.DataFrame : Concrete return type for the polars backend.

    Examples
    --------
    >>> import pyarrow as pa
    >>> from mayutils.interfaces.filetypes.parquet import pyarrow_table_to_backend
    >>> table = pa.table({"id": [1, 2, 3]})
    >>> df = pyarrow_table_to_backend(table, backend="pandas")
    >>> list(df.columns)
    ['id']
    """
    if backend == "polars":
        return cast("pl.DataFrame", pl.from_arrow(data=table))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]

    return table.to_pandas()  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]


__all__ = [
    "Parquet",
]
