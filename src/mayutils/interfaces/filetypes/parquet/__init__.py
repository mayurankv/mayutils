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

from typing import TYPE_CHECKING, Any, ClassVar, Self, cast

from mayutils.core.extras import may_require_extras
from mayutils.interfaces.filetypes import DataFile
from mayutils.objects.dataframes.backends import DataFrames

with may_require_extras():
    import pandas as pd
    import polars as pl
    import pyarrow as pa
    import pyarrow.parquet as pq

if TYPE_CHECKING:
    from collections.abc import Iterator


class Parquet[DataFrameType: DataFrames = pd.DataFrame](DataFile[DataFrameType]):
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

    def read(
        self,
        **kwargs: Any,  # noqa: ANN401
    ) -> DataFrameType:
        """
        Materialise the parquet file into a DataFrame.

        Dispatches to :func:`mayutils.objects.dataframes.read_parquet`,
        which selects between pandas and polars readers based on
        :attr:`backend`. The helper transparently handles both
        single-file and directory-style partitioned parquet datasets,
        with pyarrow doing the heavy lifting of combining row groups
        and applying any column projection supplied through
        ``kwargs``.

        Parameters
        ----------
        **kwargs
            Forwarded to :func:`mayutils.objects.dataframes.read_parquet`
            (for example ``columns=[...]`` to project a subset of
            columns or ``filters=[...]`` for predicate pushdown).

        Returns
        -------
            Fully loaded DataFrame whose concrete type matches
            :attr:`backend`.

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
        ...     df = Parquet(path).read(
        ...         columns=["id"],
        ...     )
        ...     df.shape
        (3, 1)
        """
        if self.backend.name == "pandas":
            return self.backend.cast(
                pd.read_parquet(
                    path=self.path,
                    **kwargs,
                ),
            )

        return self.backend.cast(
            pl.read_parquet(
                source=self.path,
                **kwargs,
            ),
        )

    def write(
        self,
        df: DataFrameType,
        /,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """
        Persist a DataFrame to the parquet file.

        Delegates to
        :func:`mayutils.objects.dataframes.to_parquet`, which picks
        the pandas or polars writer matching :attr:`backend`.
        Format-specific controls such as compression codec
        (``snappy``, ``zstd``, ``gzip``), partition layout
        (``partition_cols``), and row-group sizing are forwarded
        through ``kwargs`` so callers can tune on-disk layout without
        touching this dispatcher.

        Parameters
        ----------
        df
            DataFrame to persist; its runtime type has already been
            validated against :attr:`backend` by
            :meth:`DataFile.write`.
        **kwargs
            Forwarded to the underlying writer (for example
            ``compression="zstd"`` for a denser codec or
            ``partition_cols=[...]`` on pandas for Hive-style
            partitioning).

        Returns
        -------
            ``self``, for method chaining.

        Raises
        ------
        TypeError
            If *df* is not an instance of the class associated with
            :attr:`backend`.

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
        ...     _ = Parquet(path).write(
        ...         pd.DataFrame({"id": [1, 2, 3]}),
        ...         compression="zstd",
        ...     )
        ...     path.exists()
        True
        """
        if self.backend.name == "pandas":
            if not isinstance(df, pd.DataFrame):
                msg = f"Expected pandas DataFrame, got {type(df)}"
                raise TypeError(msg)

            df.to_parquet(
                path=self.path,
                index=kwargs.pop("index", True),
                **kwargs,
            )

        else:
            if not isinstance(df, pl.DataFrame):
                msg = f"Expected polars DataFrame, got {type(df)}"
                raise TypeError(msg)

            df.write_parquet(
                file=self.path,
                **kwargs,
            )

        return self

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
        arrow_schema = pq.ParquetFile(source=self.path).schema_arrow

        return {name: arrow_schema.field(name).type for name in arrow_schema.names}  # pyright: ignore[reportUnknownMemberType]

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
        return pq.ParquetFile(source=self.path).metadata.num_rows

    def iter_chunks(
        self,
        chunk_size: int,
        /,
        **kwargs: Any,  # noqa: ANN401
    ) -> Iterator[DataFrameType]:
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
        parquet_file = pq.ParquetFile(source=self.path)

        for batch in parquet_file.iter_batches(  # pyright: ignore[reportUnknownMemberType]
            batch_size=chunk_size,
            **kwargs,
        ):
            table = pa.Table.from_batches(batches=[batch])

            if self.backend.name == "polars":
                yield self.backend.cast(cast("pl.DataFrame", pl.from_arrow(data=table)))  # pyright: ignore[reportUnknownMemberType]

            yield self.backend.cast(table.to_pandas())  # pyright: ignore[reportUnknownMemberType]


__all__ = [
    "Parquet",
]
