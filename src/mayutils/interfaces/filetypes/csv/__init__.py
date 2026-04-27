"""
Provide the :class:`Csv` handle for CSV-backed dataframe I/O.

Dispatches reads and writes between :mod:`pandas` and :mod:`polars`
through the standard ``DataframeBackends`` literal used elsewhere in
``mayutils``. Schema inspection is heuristic because CSVs carry no
header metadata beyond the column names: dtypes are inferred from a
small sample, and row counts are obtained by streaming the file
line-by-line. Dialect inference (delimiter, quoting, escape
characters) is delegated entirely to the underlying reader, which
sniffs the file contents before materialising rows.

See Also
--------
csv.reader : Standard-library CSV parser referenced for dialect semantics.
pandas.read_csv : Pandas backend dispatched for CSV reads.
polars.read_csv : Polars backend dispatched for CSV reads.
mayutils.interfaces.filetypes.DataFile : Shared base class for file wrappers.

Examples
--------
>>> import tempfile
>>> import pandas as pd
>>> from pathlib import Path
>>> from mayutils.interfaces.filetypes.csv import Csv
>>> with tempfile.TemporaryDirectory() as tmp:
...     p = Path(tmp) / "demo.csv"
...     pd.DataFrame({"a": [1, 2, 3]}).to_csv(p, index=False)
...     handle = Csv(p)
...     df = handle.to_pandas()
...     df.shape
(3, 1)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, cast

from mayutils.core.extras import may_require_extras
from mayutils.interfaces.filetypes import DataFile

with may_require_extras():
    import pandas as pd
    import polars as pl
    from pandas import DataFrame

if TYPE_CHECKING:
    from collections.abc import Iterator

    from mayutils.objects.dataframes import DataframeBackends, DataFrames


DEFAULT_SCHEMA_SAMPLE_ROWS = 1000


class Csv(DataFile):
    """
    Represent a CSV file with pandas/polars dispatch.

    Concrete I/O routes through :func:`pandas.read_csv` /
    :func:`polars.read_csv` and their writers depending on the
    resolved backend. Cheap metadata operations are inherently
    approximate: :meth:`schema` reads the header plus a sample
    window, :meth:`row_count` streams the file to tally line breaks,
    and :meth:`iter_chunks` uses the pandas ``chunksize`` kwarg or
    slices a fully loaded polars frame. Encoding defaults to UTF-8
    and quoting follows each backend's native sniffing rules unless
    overridden through ``**kwargs``.

    Attributes
    ----------
    suffix
        File extension used for dispatch, namely ``".csv"``.

    See Also
    --------
    csv.reader : Standard-library row iterator used by CSV tooling.
    pandas.read_csv : Pandas reader that underpins :meth:`_read`.
    polars.read_csv : Polars reader that underpins :meth:`_read`.
    mayutils.interfaces.filetypes.DataFile : Abstract base class.

    Examples
    --------
    >>> import tempfile
    >>> import pandas as pd
    >>> from pathlib import Path
    >>> from mayutils.interfaces.filetypes.csv import Csv
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     p = Path(tmp) / "sales.csv"
    ...     pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]}).to_csv(p, index=False)
    ...     csv_file = Csv(p)
    ...     frame = csv_file.read(dataframe_backend="pandas")
    ...     (frame.shape, csv_file.row_count())
    ((3, 2), 3)
    """

    suffix: ClassVar[str] = ".csv"

    def _read(
        self,
        *,
        dataframe_backend: DataframeBackends,
        **kwargs: Any,  # noqa: ANN401
    ) -> DataFrames:
        """
        Materialise the CSV file into a DataFrame.

        Dispatches to :func:`polars.read_csv` when the resolved
        backend is ``"polars"`` and :func:`pandas.read_csv`
        otherwise. Dialect inference (delimiter, quoting, escape
        characters) is handled by the chosen reader; callers can
        override via ``**kwargs`` (for example ``sep`` / ``separator``
        or ``quotechar``). Encoding defaults follow each backend,
        usually UTF-8.

        Parameters
        ----------
        dataframe_backend
            Resolved DataFrame library to return.
        **kwargs
            Forwarded verbatim to the backend reader, covering
            dialect, dtype, encoding, and NA-handling options.

        Returns
        -------
            Fully loaded DataFrame whose concrete type matches
            ``dataframe_backend``.

        See Also
        --------
        csv.reader : Row iterator that inspired the underlying API.
        pandas.read_csv : Pandas backend invoked by this method.
        polars.read_csv : Polars backend invoked by this method.
        Csv._write : Sibling writer that round-trips the output.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "demo.csv"
        ...     pd.DataFrame({"id": [1, 2], "value": [3.14, 2.72]}).to_csv(p, index=False)
        ...     csv_file = Csv(p)
        ...     pandas_frame = csv_file._read(dataframe_backend="pandas")
        ...     pandas_frame.shape
        (2, 2)
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "demo.csv"
        ...     pd.DataFrame({"id": [1, 2], "value": [3.14, 2.72]}).to_csv(p, index=False, sep=";")
        ...     csv_file = Csv(p)
        ...     polars_frame = csv_file._read(dataframe_backend="polars", separator=";")
        ...     polars_frame.shape
        (2, 2)
        """
        if dataframe_backend == "polars":
            return pl.read_csv(
                source=self.path,
                **kwargs,
            )

        return cast(
            "DataFrame",
            pd.read_csv(
                filepath_or_buffer=self.path,
                **kwargs,
            ),
        )

    def _write(
        self,
        df: DataFrames,
        /,
        *,
        dataframe_backend: DataframeBackends,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """
        Serialise a DataFrame to the CSV file.

        Writes the supplied DataFrame to :attr:`path` using the
        backend that matches its runtime type. Pandas output suppresses
        the index by default (via ``index=False``) so the file
        round-trips cleanly without a phantom unnamed column. Polars
        output defers to :meth:`polars.DataFrame.write_csv`, which
        uses UTF-8 encoding and backend-native quoting unless
        overridden in ``**kwargs``.

        Parameters
        ----------
        df
            DataFrame to persist; its runtime type has already been
            validated against ``dataframe_backend`` by
            :meth:`DataFile.write`.
        dataframe_backend
            Resolved backend that matches ``type(df)``.
        **kwargs
            Forwarded verbatim to the backend writer. For pandas,
            ``index`` defaults to ``False`` so round-tripping does
            not accidentally add an unnamed index column.

        Raises
        ------
        TypeError
            If ``df`` is not an instance of the class associated
            with the requested ``dataframe_backend``.

        See Also
        --------
        csv.writer : Standard-library row writer.
        pandas.DataFrame.to_csv : Pandas writer invoked here.
        polars.DataFrame.write_csv : Polars writer invoked here.
        Csv._read : Sibling reader that reverses the serialisation.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "out.csv"
        ...     csv_file = Csv(p)
        ...     frame = pd.DataFrame({"id": [1, 2], "value": [3.14, 2.72]})
        ...     csv_file._write(frame, dataframe_backend="pandas")
        ...     p.is_file()
        True
        >>> import tempfile
        >>> import polars as pl
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "out.csv"
        ...     csv_file = Csv(p)
        ...     frame = pl.DataFrame({"id": [1, 2], "value": [3.14, 2.72]})
        ...     csv_file._write(frame, dataframe_backend="polars", separator=";")
        ...     p.is_file()
        True
        """
        if dataframe_backend == "pandas":
            if not isinstance(df, DataFrame):
                msg = f"Expected a pandas DataFrame for writing with backend 'pandas', but got {type(df).__name__!r} instead."
                raise TypeError(
                    msg,
                )

            df.to_csv(
                path_or_buf=self.path,
                index=kwargs.pop("index", False),
                **kwargs,
            )
        elif dataframe_backend == "polars":
            if not isinstance(df, pl.DataFrame):
                msg = f"Expected a polars DataFrame for writing with backend 'polars', but got {type(df).__name__!r} instead."
                raise TypeError(
                    msg,
                )

            df.write_csv(
                file=self.path,
                **kwargs,
            )

    def schema(
        self,
        *,
        sample_rows: int = DEFAULT_SCHEMA_SAMPLE_ROWS,
    ) -> dict[str, object]:
        """
        Infer the column-to-dtype mapping from a head sample.

        Reads the first ``sample_rows`` data rows with
        :func:`pandas.read_csv` and returns pandas' inferred dtypes
        for each column. Because CSVs do not store typing metadata,
        the mapping is heuristic: wider samples improve fidelity at
        the cost of additional I/O. The result is always derived via
        pandas, regardless of :attr:`backend`, so results stay stable
        across backends.

        Parameters
        ----------
        sample_rows
            Number of data rows to sample for dtype inference. Larger
            samples trade read time for type fidelity.

        Returns
        -------
            Mapping from column name to the pandas dtype inferred for
            that column from the sampled rows.

        See Also
        --------
        pandas.read_csv : Reader used to fetch the sample.
        Csv.row_count : Complementary metadata helper.
        Csv.iter_chunks : Sibling method that streams all rows.
        polars.read_csv : Alternative reader with native schemas.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "demo.csv"
        ...     pd.DataFrame({"id": [1, 2], "value": [3.14, 2.72]}).to_csv(p, index=False)
        ...     csv_file = Csv(p)
        ...     list(csv_file.schema())
        ['id', 'value']
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "demo.csv"
        ...     pd.DataFrame({"id": [1, 2], "value": [3.14, 2.72]}).to_csv(p, index=False)
        ...     csv_file = Csv(p)
        ...     list(csv_file.schema(sample_rows=50))
        ['id', 'value']
        """
        head = pd.read_csv(filepath_or_buffer=self.path, nrows=sample_rows)

        return {column: head[column].dtype for column in head.columns}

    def row_count(
        self,
    ) -> int:
        """
        Return the data row count by streaming the file.

        Opens the file with UTF-8 encoding and increments a counter
        for each newline. Subtracts one to exclude the header row.
        The count is clamped at zero so an empty file (no header and
        no rows) still returns ``0`` rather than ``-1``. Because the
        count is line-based, embedded newlines inside quoted fields
        may cause the result to overestimate the true row count.

        Returns
        -------
            Non-negative number of data rows excluding the header.

        See Also
        --------
        csv.reader : Row iterator that would give a precise count.
        pandas.read_csv : Loads the file in full for exact counts.
        Csv.schema : Complementary metadata helper.
        Csv.iter_chunks : Sibling method for large-file streaming.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "demo.csv"
        ...     pd.DataFrame({"id": list(range(42))}).to_csv(p, index=False)
        ...     csv_file = Csv(p)
        ...     csv_file.row_count()
        42
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
        """
        Stream the CSV file as DataFrame chunks.

        Yields successive slices of the file so large datasets can be
        processed without loading the full table into memory. For the
        pandas backend the method relies on the ``chunksize`` kwarg of
        :func:`pandas.read_csv`, which iterates through the file
        without exhausting memory. The polars backend currently reads
        the full table once and yields fixed-size slices because
        :func:`polars.read_csv` does not expose a native chunking API
        that respects arbitrary reader kwargs. Dialect inference
        (delimiter, quoting, escape characters) is handled by the
        underlying reader.

        Parameters
        ----------
        chunk_size
            Upper bound on the number of rows per yielded chunk.
        dataframe_backend
            DataFrame library for each chunk; defaults to
            :attr:`backend` when ``None``.
        **kwargs
            Forwarded to the backend reader. For pandas, the
            ``chunksize`` kwarg is set by this method and should not
            be overridden; for polars, the implementation reads the
            full table and slices it, so all kwargs flow into
            :func:`polars.read_csv`.

        Yields
        ------
            Successive chunks whose concatenation equals the result
            of :meth:`_read` with the same kwargs.

        See Also
        --------
        csv.reader : Row-level iterator for line streaming.
        pandas.read_csv : Underlying reader when pandas is selected.
        polars.read_csv : Underlying reader when polars is selected.
        Csv._read : Sibling method that loads the file in one pass.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "demo.csv"
        ...     pd.DataFrame({"id": list(range(2500))}).to_csv(p, index=False)
        ...     csv_file = Csv(p)
        ...     pandas_sizes = [len(chunk) for chunk in csv_file.iter_chunks(1000, dataframe_backend="pandas")]
        ...     pandas_sizes
        [1000, 1000, 500]
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "demo.csv"
        ...     pd.DataFrame({"id": list(range(1100))}).to_csv(p, index=False)
        ...     csv_file = Csv(p)
        ...     polars_sizes = [len(chunk) for chunk in csv_file.iter_chunks(500, dataframe_backend="polars")]
        ...     polars_sizes
        [500, 500, 100]
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
