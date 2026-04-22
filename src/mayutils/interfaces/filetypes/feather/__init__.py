"""Feather-backed :class:`DataFile` subclass.

Uses ``pyarrow.feather`` for fast IPC round-trips and
``pyarrow.ipc.open_file`` for metadata-cheap introspection and
record-batch streaming. The backend dispatch mirrors the parquet
subclass: full reads return a pandas or polars DataFrame according to
:attr:`backend`; chunked reads convert each Arrow record batch to the
requested DataFrame library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Self, cast

from mayutils.core.extras import may_require_extras
from mayutils.interfaces.filetypes import DataFile
from mayutils.objects.dataframes import infer_backend

with may_require_extras():
    import pandas as pd
    import polars as pl
    import pyarrow as pa
    import pyarrow.ipc as pa_ipc
    from pyarrow import feather

if TYPE_CHECKING:
    from collections.abc import Iterator

    from mayutils.objects.dataframes import DataframeBackends, DataFrames


class Feather(DataFile):
    """Handle to an Arrow IPC (Feather v2) file.

    Backend dispatch for :meth:`read` and :meth:`write` goes through
    the native pandas/polars Feather helpers; metadata-level calls
    (:meth:`schema`, :meth:`row_count`, :meth:`iter_chunks`) go
    through ``pyarrow.ipc`` so they don't materialise the full file.
    """

    suffix: ClassVar[str] = ".feather"

    def read(
        self,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> DataFrames:
        """Materialise the Feather file into a DataFrame.

        Parameters
        ----------
        dataframe_backend : {"pandas", "polars"} or None, optional
            Target DataFrame library; defaults to :attr:`backend`.
        **kwargs
            Forwarded to the backend reader.

        Returns
        -------
        pandas.DataFrame or polars.DataFrame
            Fully loaded DataFrame whose concrete type matches the
            resolved backend.
        """
        backend = dataframe_backend if dataframe_backend is not None else self.backend

        if backend == "polars":
            return pl.read_ipc(source=self.path, **kwargs)

        return pd.read_feather(path=self.path, **kwargs)

    def write(
        self,
        df: DataFrames,
        /,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """Serialise a DataFrame to the Feather file.

        Parameters
        ----------
        df : pandas.DataFrame or polars.DataFrame
            DataFrame to persist.
        dataframe_backend : {"pandas", "polars"} or None, optional
            Explicit backend override; when ``None`` the backend is
            inferred from ``type(df)``.
        **kwargs
            Forwarded verbatim to the backend writer.

        Returns
        -------
        Self
            The current handle, for fluent chaining.

        Raises
        ------
        TypeError
            If the resolved backend does not match ``type(df)``.
        """
        backend = dataframe_backend if dataframe_backend is not None else infer_backend(df)

        if backend == "pandas":
            if not isinstance(df, pd.DataFrame):
                msg = f"Expected a pandas DataFrame for backend 'pandas', got {type(df)}"
                raise TypeError(msg)
            df.to_feather(path=self.path, **kwargs)
        else:
            if not isinstance(df, pl.DataFrame):
                msg = f"Expected a polars DataFrame for backend 'polars', got {type(df)}"
                raise TypeError(msg)
            df.write_ipc(file=self.path, **kwargs)

        return self

    def schema(
        self,
    ) -> dict[str, Any]:
        """Return the column-to-arrow-dtype mapping from the IPC header.

        Returns
        -------
        dict of str to Any
            Column name → :class:`pyarrow.DataType`.
        """
        arrow_schema = feather.read_table(source=self.path, columns=[]).schema  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

        return {name: arrow_schema.field(name).type for name in arrow_schema.names}  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

    def row_count(
        self,
    ) -> int:
        """Return the row count from the IPC file metadata.

        Returns
        -------
        int
            Total number of rows declared by the Feather file.
        """
        with pa_ipc.open_file(source=str(self.path)) as reader:  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
            return sum(reader.get_batch(index).num_rows for index in range(reader.num_record_batches))  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]

    def iter_chunks(
        self,
        chunk_size: int,
        /,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Iterator[DataFrames]:
        """Stream the Feather file as DataFrame chunks of ``chunk_size`` rows.

        The full Arrow table is loaded once (Feather is a single-file
        IPC container, so there is no per-batch streaming API) and
        then sliced into row windows of the requested size.

        Parameters
        ----------
        chunk_size : int
            Upper bound on the number of rows per yielded chunk. The
            final chunk may be smaller.
        dataframe_backend : {"pandas", "polars"} or None, optional
            DataFrame library to convert each chunk to; defaults to
            :attr:`backend`.
        **kwargs
            Forwarded to :func:`pyarrow.feather.read_table`.

        Yields
        ------
        pandas.DataFrame or polars.DataFrame
            Successive chunks whose concatenation equals
            :meth:`read`.
        """
        backend = dataframe_backend if dataframe_backend is not None else self.backend
        table = feather.read_table(source=self.path, **kwargs)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

        for start in range(0, table.num_rows, chunk_size):  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            yield pyarrow_table_to_backend(
                table.slice(offset=start, length=chunk_size),  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                backend=backend,
            )


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

    return table.to_pandas()  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]


__all__ = [
    "Feather",
]
