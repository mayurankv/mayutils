"""CSV-backed :class:`DataFile` subclass.

Dispatches reads and writes between :mod:`pandas` and :mod:`polars`
through the standard ``DataframeBackends`` literal used elsewhere in
``mayutils``. Schema inspection is heuristic because CSVs carry no
header metadata beyond the column names: dtypes are inferred from a
small sample, and row counts are obtained by streaming the file
line-by-line.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Self

from mayutils.core.extras import may_require_extras
from mayutils.interfaces.filetypes import DataFile
from mayutils.objects.dataframes import DataframeBackends, DataFrames, infer_backend

with may_require_extras():
    import pandas as pd
    import polars as pl

if TYPE_CHECKING:
    from collections.abc import Iterator


DEFAULT_SCHEMA_SAMPLE_ROWS = 1000


class Csv(DataFile):
    """Handle to a CSV file with pandas/polars dispatch.

    Concrete I/O routes through :func:`pandas.read_csv` /
    :meth:`polars.read_csv` and their writers depending on the
    resolved backend. Cheap metadata operations are inherently
    approximate: :meth:`schema` reads the header plus a sample
    window, :meth:`row_count` streams the file to tally line breaks,
    and :meth:`iter_chunks` uses the pandas ``chunksize`` / polars
    ``batch_reader`` facilities.
    """

    suffix: ClassVar[str] = ".csv"

    def read(
        self,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> DataFrames:
        """Materialise the CSV file into a DataFrame.

        Parameters
        ----------
        dataframe_backend : {"pandas", "polars"} or None, optional
            Target DataFrame library; defaults to :attr:`backend`.
        **kwargs
            Forwarded verbatim to the backend reader.

        Returns
        -------
        pandas.DataFrame or polars.DataFrame
            Fully loaded DataFrame whose concrete type matches the
            resolved backend.
        """
        backend = dataframe_backend if dataframe_backend is not None else self.backend

        if backend == "polars":
            return pl.read_csv(source=self.path, **kwargs)

        return pd.read_csv(filepath_or_buffer=self.path, **kwargs)  # pyright: ignore[reportUnknownVariableType]

    def write(
        self,
        df: DataFrames,
        /,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """Serialise a DataFrame to the CSV file.

        Parameters
        ----------
        df : pandas.DataFrame or polars.DataFrame
            DataFrame to persist.
        dataframe_backend : {"pandas", "polars"} or None, optional
            Explicit backend override. When ``None``, dispatch is
            inferred from ``type(df)``.
        **kwargs
            Forwarded verbatim to the backend writer. For pandas,
            ``index`` defaults to ``False`` so round-tripping does not
            accidentally add an unnamed index column.

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

            df.to_csv(
                path_or_buf=self.path,
                index=kwargs.pop("index", False),
                **kwargs,
            )

        else:
            if not isinstance(df, pl.DataFrame):
                msg = f"Expected a polars DataFrame for backend 'polars', got {type(df)}"
                raise TypeError(msg)

            df.write_csv(
                file=self.path,
                **kwargs,
            )

        return self

    def schema(
        self,
        *,
        sample_rows: int = DEFAULT_SCHEMA_SAMPLE_ROWS,
    ) -> dict[str, Any]:
        """Infer the column-to-dtype mapping from a head sample.

        Parameters
        ----------
        sample_rows : int, default ``1000``
            Number of data rows to sample for dtype inference. Larger
            samples trade read time for type fidelity.

        Returns
        -------
        dict of str to Any
            Column name → pandas dtype. The mapping reflects pandas'
            inference, not polars', so the result is stable regardless
            of :attr:`backend`.
        """
        head = pd.read_csv(filepath_or_buffer=self.path, nrows=sample_rows)

        return {column: head[column].dtype for column in head.columns}

    def row_count(
        self,
    ) -> int:
        """Return the data row count by streaming the file.

        Assumes the first line is a header row; subtracts one from
        the total line count.

        Returns
        -------
        int
            Non-negative number of data rows.
        """
        with self.path.open(encoding="utf-8") as file:
            total_lines = sum(1 for _ in file)

        return max(total_lines - 1, 0)

    def iter_chunks(
        self,
        chunk_size: int,
        /,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Iterator[DataFrames]:
        """Stream the CSV file as DataFrame chunks.

        Parameters
        ----------
        chunk_size : int
            Upper bound on the number of rows per yielded chunk.
        dataframe_backend : {"pandas", "polars"} or None, optional
            DataFrame library for each chunk; defaults to
            :attr:`backend`.
        **kwargs
            Forwarded to the backend reader. For pandas, the
            ``chunksize`` kwarg is set by this method and should not
            be overridden; for polars, the implementation reads the
            full table and slices it, so all kwargs flow into
            :meth:`polars.read_csv`.

        Yields
        ------
        pandas.DataFrame or polars.DataFrame
            Successive chunks whose concatenation equals
            :meth:`read`.
        """
        backend = dataframe_backend if dataframe_backend is not None else self.backend

        if backend == "pandas":
            with pd.read_csv(filepath_or_buffer=self.path, chunksize=chunk_size, **kwargs) as reader:
                yield from reader

            return

        frame = pl.read_csv(source=self.path, **kwargs)
        for start in range(0, frame.height, chunk_size):
            yield frame.slice(offset=start, length=chunk_size)


__all__ = [
    "Csv",
]
