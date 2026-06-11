"""
Provide the :class:`Feather` handle for Arrow IPC (Feather) file I/O.

Wraps ``pyarrow.feather`` for round-trip reads and writes and
``pyarrow.ipc.open_file`` for metadata-cheap introspection and
record-batch streaming. Backend dispatch mirrors the parquet subclass:
full reads return a pandas or polars DataFrame according to
:attr:`Feather.backend`, and chunked reads slice an Arrow table into
row windows before converting each slice to the requested DataFrame
library. Feather v2 (the default Arrow IPC container) supports
LZ4 and ZSTD compression; the legacy Feather v1 format is
effectively deprecated and retained only for backward compatibility.

See Also
--------
pyarrow.feather : Low-level Feather reader and writer that backs this module.
pyarrow.ipc.open_file : IPC file opener used for cheap metadata access.
pandas.read_feather : Pandas reader that underpins :meth:`Feather._read`.
polars.read_ipc : Polars reader that underpins :meth:`Feather._read`.
mayutils.interfaces.filetypes.DataFile : Abstract base class extended by :class:`Feather`.

Examples
--------
>>> import tempfile
>>> import pandas as pd
>>> from pathlib import Path
>>> from mayutils.interfaces.filetypes.feather import Feather
>>> with tempfile.TemporaryDirectory() as tmp:
...     path = Path(tmp) / "trades.feather"
...     pd.DataFrame({"id": [1, 2, 3], "value": [3.14, 2.72, 1.41]}).to_feather(path)
...     handle = Feather(path)
...     handle.row_count()
3
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Self, cast

from mayutils.core.extras import may_require_extras
from mayutils.interfaces.filetypes import DataFile
from mayutils.objects.dataframes.backends import DataFrames

if TYPE_CHECKING:
    from collections.abc import Iterator

    import pandas as pd
    import polars as pl


class Feather[DataFrameType: DataFrames = pd.DataFrame](DataFile[DataFrameType]):
    """
    Represent an Arrow IPC (Feather v2) file with pandas/polars dispatch.

    Backend dispatch for :meth:`read` and :meth:`write` goes through
    the native pandas/polars Feather helpers (``pandas.read_feather`` /
    ``pandas.DataFrame.to_feather`` and ``polars.read_ipc`` /
    ``polars.DataFrame.write_ipc``), while metadata-level calls
    (:meth:`schema`, :meth:`row_count`, :meth:`iter_chunks`) go
    through ``pyarrow.ipc`` so they do not materialise the full file.
    Feather v2 is the default on-disk layout and supports LZ4 and ZSTD
    compression; callers can pass ``compression="lz4"`` or
    ``compression="zstd"`` through ``**kwargs`` to either writer.
    Feather v1 is an older on-disk layout retained only for legacy
    pipelines and is not produced by default.

    Attributes
    ----------
    suffix
        File extension used for dispatch, namely ``".feather"``.

    See Also
    --------
    pyarrow.feather : Low-level Feather reader and writer.
    pyarrow.ipc.open_file : Opener used for cheap metadata access.
    pandas.read_feather : Pandas reader underpinning :meth:`_read`.
    polars.read_ipc : Polars reader underpinning :meth:`_read`.
    mayutils.interfaces.filetypes.DataFile : Abstract base class.

    Examples
    --------
    >>> import tempfile
    >>> import pandas as pd
    >>> from pathlib import Path
    >>> from mayutils.interfaces.filetypes.feather import Feather
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     path = Path(tmp) / "trades.feather"
    ...     pd.DataFrame({"id": [1, 2], "value": [3.14, 2.72]}).to_feather(path)
    ...     handle = Feather(path)
    ...     schema = handle.schema()
    ...     sorted(schema.keys())
    ['id', 'value']
    """

    suffix: ClassVar[str] = ".feather"

    def read(
        self,
        **kwargs: Any,  # noqa: ANN401
    ) -> DataFrameType:
        """
        Materialise the Feather file into a DataFrame.

        Dispatches to :func:`polars.read_ipc` when the resolved backend
        is ``"polars"`` and to :func:`pandas.read_feather` otherwise.
        Both readers accept the Feather v2 (Arrow IPC file) layout and
        transparently honour LZ4 or ZSTD compression blocks; callers
        can forward reader-specific kwargs such as ``columns=[...]`` or
        ``memory_map=True`` via ``**kwargs``. Legacy Feather v1 files
        are still decodable by the pandas reader.

        Parameters
        ----------
        **kwargs
            Forwarded verbatim to the backend reader (for example
            ``columns=[...]`` or ``memory_map=True``).

        Returns
        -------
            Fully loaded DataFrame whose concrete type matches
            ``self.backend``.

        See Also
        --------
        pyarrow.feather.read_table : Arrow-level reader used indirectly.
        pandas.read_feather : Pandas backend invoked by this method.
        polars.read_ipc : Polars backend invoked by this method.
        Feather._write : Sibling writer that round-trips the output.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.feather import Feather
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     path = Path(tmp) / "demo.feather"
        ...     pd.DataFrame({"id": [1, 2], "value": [3.14, 2.72]}).to_feather(path)
        ...     handle = Feather(path)
        ...     frame = handle.read()
        ...     frame.shape
        (2, 2)
        """
        if self.backend.name == "polars":
            with may_require_extras():
                import polars as pl

            return self.backend.cast(
                pl.read_ipc(
                    source=self.path,
                    **kwargs,
                ),
            )

        with may_require_extras():
            import pandas as pd

        return self.backend.cast(
            pd.read_feather(
                path=self.path,
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
        Serialise a DataFrame to the Feather file.

        Writes the supplied DataFrame to :attr:`path` using the backend
        that matches its runtime type. Pandas output flows through
        :meth:`pandas.DataFrame.to_feather`, which defaults to Feather
        v2 with LZ4 compression; polars output flows through
        :meth:`polars.DataFrame.write_ipc`, which always produces
        Feather v2. Callers can override compression (``compression=
        "lz4" | "zstd" | "uncompressed"``) or chunk sizing through
        ``**kwargs``.

        Parameters
        ----------
        df
            DataFrame to persist; its runtime type has already been
            validated against ``self.backend`` by
            :meth:`DataFile.write`.
        **kwargs
            Forwarded verbatim to the backend writer (for example
            ``compression="zstd"`` or ``chunksize=65_536``).

        Returns
        -------
            ``self``, for method chaining.

        Raises
        ------
        TypeError
            If ``df`` is not an instance of the class associated with
            the requested ``self.backend``.

        See Also
        --------
        pyarrow.feather.write_feather : Arrow-level writer used indirectly.
        pandas.DataFrame.to_feather : Pandas writer invoked here.
        polars.DataFrame.write_ipc : Polars writer invoked here.
        Feather._read : Sibling reader that reverses the serialisation.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.feather import Feather
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     path = Path(tmp) / "demo.feather"
        ...     handle = Feather(path)
        ...     frame = pd.DataFrame({"id": [1, 2], "value": [3.14, 2.72]})
        ...     _ = handle.write(frame)
        ...     path.exists()
        True
        """
        if self.backend.name == "pandas":
            with may_require_extras():
                from pandas import DataFrame

            if not isinstance(df, DataFrame):
                msg = f"Expected a pandas DataFrame for writing with backend 'pandas', but got {type(df).__name__!r} instead."
                raise TypeError(
                    msg,
                )

            df.to_feather(
                path=self.path,
                **kwargs,
            )

        elif self.backend.name == "polars":
            with may_require_extras():
                import polars as pl

            if not isinstance(df, pl.DataFrame):
                msg = f"Expected a polars DataFrame for writing with backend 'polars', but got {type(df).__name__!r} instead."
                raise TypeError(
                    msg,
                )

            df.write_ipc(
                file=self.path,
                **kwargs,
            )

        return self

    def schema(
        self,
    ) -> dict[str, object]:
        """
        Return the column-to-arrow-dtype mapping from the IPC header.

        Reads only the Arrow IPC schema by requesting an empty column
        projection through :func:`pyarrow.feather.read_table`, so the
        data body is never materialised. The result preserves the
        on-disk column ordering and maps each column name to its
        :class:`pyarrow.DataType` (for example ``int64``,
        ``timestamp[us, tz=UTC]`` or ``list<item: string>``).

        Returns
        -------
            Mapping from column name to its :class:`pyarrow.DataType`.

        See Also
        --------
        pyarrow.feather.read_table : Reader used with an empty projection.
        pyarrow.ipc.open_file : Alternative opener for schema access.
        Feather.row_count : Complementary metadata helper.
        Feather.iter_chunks : Sibling method that streams the body.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.feather import Feather
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     path = Path(tmp) / "demo.feather"
        ...     pd.DataFrame({"id": [1, 2], "value": [3.14, 2.72]}).to_feather(path)
        ...     handle = Feather(path)
        ...     schema = handle.schema()
        ...     sorted(schema.keys())
        ['id', 'value']
        """
        with may_require_extras():
            from pyarrow import feather

        arrow_schema = feather.read_table(source=self.path, columns=[]).schema  # pyright: ignore[reportUnknownMemberType]

        return {name: arrow_schema.field(name).type for name in arrow_schema.names}  # pyright: ignore[reportUnknownMemberType]

    def row_count(
        self,
    ) -> int:
        """
        Return the row count from the Arrow IPC file metadata.

        Opens the Feather file via :func:`pyarrow.ipc.open_file` and
        sums the ``num_rows`` of each record batch reported in the
        footer. Only batch metadata is touched; the column buffers
        themselves are never decoded, so the call cost is dominated by
        a single footer read rather than the dataset size.

        Returns
        -------
            Total number of rows declared by the Feather file across
            all record batches.

        See Also
        --------
        pyarrow.ipc.open_file : Opener used for cheap metadata access.
        pyarrow.feather.read_table : Full-body reader used elsewhere.
        Feather.schema : Complementary metadata helper.
        Feather.iter_chunks : Sibling method that streams the body.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.feather import Feather
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     path = Path(tmp) / "demo.feather"
        ...     pd.DataFrame({"id": [1, 2, 3, 4]}).to_feather(path)
        ...     handle = Feather(path)
        ...     handle.row_count()
        4
        """
        with may_require_extras():
            import pyarrow.ipc as pa_ipc

        with pa_ipc.open_file(source=str(self.path)) as reader:
            return sum(reader.get_batch(index).num_rows for index in range(reader.num_record_batches))

    def iter_chunks(
        self,
        chunk_size: int,
        /,
        **kwargs: Any,  # noqa: ANN401
    ) -> Iterator[DataFrameType]:
        """
        Stream the Feather file as DataFrame chunks of ``chunk_size`` rows.

        Loads the full Arrow table with :func:`pyarrow.feather.read_table`
        once (Feather is a single-file IPC container, so there is no
        per-batch streaming API equivalent to
        :meth:`pyarrow.parquet.ParquetFile.iter_batches`) and then
        slices it into row windows of the requested size before
        converting each slice to the target DataFrame backend via
        :func:`pyarrow_table_to_backend`. The final chunk may be
        shorter than ``chunk_size``.

        Parameters
        ----------
        chunk_size
            Upper bound on the number of rows per yielded chunk. The
            final chunk may be smaller if the total row count is not
            an exact multiple.
        **kwargs
            Forwarded to :func:`pyarrow.feather.read_table` (for
            example ``columns=[...]`` or ``memory_map=True``).

        Yields
        ------
            Successive chunks whose concatenation equals the result of
            :meth:`_read` with the same kwargs.

        See Also
        --------
        pyarrow.feather.read_table : Arrow-level reader used here.
        pyarrow.Table.slice : Row-window helper used to split chunks.
        Feather._read : Sibling method that loads the file in one pass.
        pyarrow_table_to_backend : Helper that converts each slice.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.feather import Feather
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     path = Path(tmp) / "demo.feather"
        ...     pd.DataFrame({"id": [1, 2, 3, 4, 5]}).to_feather(path)
        ...     handle = Feather(path)
        ...     chunks = list(handle.iter_chunks(2))
        ...     [chunk.shape for chunk in chunks]
        [(2, 1), (2, 1), (1, 1)]
        """
        with may_require_extras():
            from pyarrow import feather

        table = feather.read_table(source=self.path, **kwargs)  # pyright: ignore[reportUnknownMemberType]

        for start in range(0, table.num_rows, chunk_size):
            sliced_table = table.slice(offset=start, length=chunk_size)

            if self.backend.name == "polars":
                with may_require_extras():
                    import polars as pl

                df = self.backend.cast(cast("pl.DataFrame", pl.from_arrow(data=sliced_table)))  # pyright: ignore[reportUnknownMemberType]

            df = self.backend.cast(sliced_table.to_pandas())  # pyright: ignore[reportUnknownMemberType]

            yield df


__all__ = [
    "Feather",
]
