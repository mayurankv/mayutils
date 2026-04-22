"""Filetype-specific authoring and rendering helpers.

This package groups adapters that speak particular document formats
rather than third-party services — for example :mod:`.markdown` for
Mistune-backed Markdown parsing, :mod:`.pptx` for ``python-pptx``
PowerPoint authoring, and :mod:`.pdf` for PyMuPDF + Pillow rendering.
Each submodule is guarded by an optional dependency extra.

Tabular file formats (CSV, Parquet, Feather, XLSX) share a common
instance-based façade through :class:`DataFile`. Each format ships a
subclass that validates its suffix, registers itself on the base
class so :meth:`DataFile.from_path` can dispatch by extension, and
implements the abstract read/write/introspection/streaming surface.
Cross-format conversion is then a built-in round-trip through the
DataFrame layer, so new subclasses inherit conversion to and from
every registered peer for free.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, overload

from mayutils.objects.dataframes import infer_backend

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    import polars as pl
    from pandas import DataFrame

    from mayutils.objects.dataframes import DataframeBackends, DataFrames


PREVIEW_ERRORS: tuple[type[BaseException], ...] = (
    OSError,
    ValueError,
    ImportError,
    RuntimeError,
)
"""Exception classes :meth:`DataFile.__repr__` suppresses when reading the file.

Covers the realistic failure modes when previewing an on-disk file:
filesystem errors (:class:`OSError`), malformed-data errors
(:class:`ValueError`, which is also the base of ``pyarrow.ArrowInvalid``),
missing optional backends (:class:`ImportError`), and runtime parser
issues (:class:`RuntimeError`). Anything else (interrupts, assertion
errors, unexpected bugs) propagates so it stays visible.
"""


class DataFile(ABC):
    """Abstract instance-based handle for a tabular file on disk.

    Subclasses bind a single file format (parquet, csv, feather, xlsx
    sheet, ...) and implement the abstract methods below; the concrete
    methods on this base provide path-level helpers, a suffix-indexed
    registry, and generic format conversion built on top of the read
    and write abstract methods. The class is deliberately modelled on
    the façade style used by
    :class:`mayutils.interfaces.filetypes.pptx.Presentation`: callers
    hold an instance, operate on it fluently, and reach for the
    underlying library only when necessary.

    Parameters
    ----------
    path : pathlib.Path or str
        Filesystem location of the target file. The path does not have
        to exist yet (it may be about to be written), but its suffix
        must match :attr:`suffix` declared on the subclass.
    backend : {"pandas", "polars"}, default ``"pandas"``
        Default DataFrame library to materialise reads as and to
        dispatch writes through when no explicit backend is supplied at
        call time. Passed through to the read/write implementations as
        ``dataframe_backend``.

    Attributes
    ----------
    path : pathlib.Path
        Resolved path to the file.
    backend : mayutils.objects.dataframes.DataframeBackends
        Default backend captured at construction.
    suffix : str
        File extension that identifies the format (``".parquet"``,
        ``".csv"``, ...). Must be declared as a :class:`ClassVar` on
        every concrete subclass.

    Raises
    ------
    ValueError
        If the supplied ``path`` has a suffix that does not match the
        subclass's :attr:`suffix`.
    """

    suffix: ClassVar[str]
    _registry: ClassVar[dict[str, type[DataFile]]] = {}

    def __init_subclass__(
        cls,
        *,
        register: bool = True,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Register concrete subclasses in the suffix-indexed dispatch table.

        Parameters
        ----------
        register : bool, default ``True``
            Whether to add ``cls`` to :attr:`DataFile._registry` under
            its :attr:`suffix`. Pass ``register=False`` in the class
            definition to opt out (useful for alternate views of a
            format that would otherwise collide on suffix).
        **kwargs
            Forwarded to :meth:`object.__init_subclass__` so
            cooperative multiple inheritance keeps working.

        Raises
        ------
        TypeError
            If ``register`` is ``True`` and ``cls`` does not declare a
            :attr:`suffix` class attribute.
        """
        super().__init_subclass__(**kwargs)
        if not register:
            return
        if not hasattr(cls, "suffix"):
            msg = f"{cls.__name__} must declare a `suffix` class attribute to register on DataFile."
            raise TypeError(msg)

        DataFile._registry[cls.suffix.lower()] = cls

    def __init__(
        self,
        path: Path | str,
        /,
        *,
        backend: DataframeBackends = "pandas",
    ) -> None:
        """Bind the handle to ``path`` and capture the default backend.

        Parameters
        ----------
        path : pathlib.Path or str
            Filesystem location of the target file. A string is
            normalised to :class:`pathlib.Path`. The file is not opened
            here; I/O happens lazily on :meth:`read`, :meth:`write`,
            :meth:`schema`, :meth:`row_count`, and :meth:`iter_chunks`.
        backend : {"pandas", "polars"}, default ``"pandas"``
            Default DataFrame backend for reads and for dispatching
            writes when the caller does not override it.

        Raises
        ------
        ValueError
            If ``path`` has a suffix that does not match the
            subclass's :attr:`suffix`.
        """
        self.path = Path(path)
        self.backend: DataframeBackends = backend

        if self.path.suffix.lower() != self.suffix.lower():
            msg = f"{type(self).__name__} expects a '{self.suffix}' file; got '{self.path.suffix}'."
            raise ValueError(msg)

    def _identity(
        self,
    ) -> str:
        """Return the identity line used as a header in :meth:`__repr__`.

        Subclasses override this to include extra state (for example
        :class:`XlsxSheet` includes the bound sheet name).

        Returns
        -------
        str
            ``"<Class>(<path>, backend=<backend>)"`` by default.
        """
        return f"{type(self).__name__}({self.path!s}, backend={self.backend!r})"

    def __repr__(
        self,
    ) -> str:
        """Return an identity header followed by a small file preview.

        When the file exists and can be read, the first
        :data:`_PREVIEW_ROWS` rows are included via the underlying
        DataFrame's own ``repr``. Failures (missing extras, unreadable
        file) fall back to the identity line alone so ``repr`` never
        raises.

        Returns
        -------
        str
            Multi-line string: identity line, then a newline, then
            the rendered preview. A single line if no preview is
            available.
        """
        header = self._identity()
        if not self.exists():
            return header
        try:
            preview = self.read()
        except PREVIEW_ERRORS:
            return header

        return f"{header}\n{preview!r}"

    def _repr_html_(
        self,
    ) -> str:
        """Render an identity header and a small HTML preview of the file.

        Delegates the table-level rendering to the DataFrame's own
        ``_repr_html_`` (pandas and polars both provide it), so the
        resulting markup matches whatever the front-end normally
        produces for the resolved backend. Falls back to the identity
        line on any error.

        Returns
        -------
        str
            HTML string that front-ends can embed inline.
        """
        header = f"<code>{self._identity()}</code>"
        if not self.exists():
            return header
        try:
            preview = self.read()
            html: str = preview._repr_html_()  # pyright: ignore[reportUnknownVariableType, reportPrivateUsage, reportCallIssue]  # ty:ignore[call-non-callable]
        except PREVIEW_ERRORS:
            return header
        if not html:
            return header

        return f"{header}<br/>{html}"

    @classmethod
    def from_path(
        cls,
        path: Path | str,
        /,
        *,
        backend: DataframeBackends = "pandas",
        **kwargs: Any,  # noqa: ANN401
    ) -> DataFile:
        """Build the appropriate subclass for ``path`` via suffix dispatch.

        The returned object is an instance of whichever concrete
        :class:`DataFile` subclass registered itself for the given
        suffix at import time.

        Parameters
        ----------
        path : pathlib.Path or str
            Path whose suffix selects the concrete subclass. The
            resolved suffix is lower-cased before lookup.
        backend : {"pandas", "polars"}, default ``"pandas"``
            Forwarded to the subclass's ``__init__`` as the default
            DataFrame backend.
        **kwargs
            Forwarded verbatim to the subclass's ``__init__``. Use
            this to pass subclass-specific options such as ``sheet``
            for :class:`XlsxSheet`.

        Returns
        -------
        DataFile
            A newly constructed instance of the registered subclass
            bound to ``path``.

        Raises
        ------
        ValueError
            If no subclass has been registered for the suffix of
            ``path``; usually this means the relevant subclass module
            has not been imported.
        """
        path = Path(path)
        key = path.suffix.lower()
        if key not in DataFile._registry:
            known = ", ".join(sorted(DataFile._registry)) or "<none>"
            msg = f"No DataFile subclass registered for suffix '{key}'. Known suffixes: {known}."
            raise ValueError(msg)

        return DataFile._registry[key](
            path,
            backend=backend,
            **kwargs,
        )

    def exists(
        self,
    ) -> bool:
        """Return whether the underlying file exists on disk.

        Returns
        -------
        bool
            ``True`` iff :attr:`path` resolves to a regular file; a
            directory, a symlink to a missing target, or an absent
            path all return ``False``.
        """
        return self.path.is_file()

    def size(
        self,
    ) -> int:
        """Return the file size in bytes.

        Returns
        -------
        int
            Number of bytes reported by ``path.stat().st_size``.

        Raises
        ------
        FileNotFoundError
            If :attr:`path` does not exist.
        """
        return self.path.stat().st_size

    def columns(
        self,
    ) -> list[str]:
        """Return the column names declared by the file.

        Derived from :meth:`schema` so subclasses only need to
        implement schema extraction once.

        Returns
        -------
        list of str
            Column names in declaration order.
        """
        return list(self.schema())

    def dtypes(
        self,
    ) -> dict[str, Any]:
        """Return the column-to-dtype mapping declared by the file.

        This is a straight alias for :meth:`schema` kept for symmetry
        with the pandas ``DataFrame.dtypes`` attribute that most
        callers reach for first.

        Returns
        -------
        dict of str to Any
            Column name → dtype mapping as returned by
            :meth:`schema`.
        """
        return self.schema()

    def convert_to(
        self,
        target_cls: type[DataFile],
        /,
        path: Path | str,
        *,
        backend: DataframeBackends | None = None,
        read_kwargs: Mapping[str, Any] | None = None,
        write_kwargs: Mapping[str, Any] | None = None,
        **init_kwargs: Any,  # noqa: ANN401
    ) -> DataFile:
        """Round-trip the file's contents into another registered format.

        Materialises the current file into a DataFrame via
        :meth:`read`, constructs a ``target_cls`` handle bound to
        ``path``, and writes the DataFrame through its
        :meth:`write`. The returned handle is the newly constructed
        target, so subsequent reads can chain directly off the call.

        Parameters
        ----------
        target_cls : type[DataFile]
            Concrete :class:`DataFile` subclass to construct at
            ``path`` and populate from ``self``.
        path : pathlib.Path or str
            Destination path for the converted file. Passed to
            ``target_cls(path, ...)``.
        backend : {"pandas", "polars"} or None, optional
            DataFrame backend for both the intermediate read and
            write. When ``None``, falls back to :attr:`backend`.
        read_kwargs : Mapping[str, Any] or None, optional
            Extra keyword arguments forwarded to :meth:`read`.
        write_kwargs : Mapping[str, Any] or None, optional
            Extra keyword arguments forwarded to the target's
            :meth:`write`.
        **init_kwargs
            Extra keyword arguments forwarded to ``target_cls``'s
            ``__init__`` (for example ``sheet=...`` when converting to
            an :class:`XlsxSheet`).

        Returns
        -------
        DataFile
            Handle to the newly written file in the target format.
        """
        effective_backend = backend if backend is not None else self.backend
        df = self.read(
            dataframe_backend=effective_backend,
            **(dict(read_kwargs) if read_kwargs else {}),
        )
        target = target_cls(
            path,
            backend=effective_backend,
            **init_kwargs,
        )
        target.write(
            df,
            dataframe_backend=effective_backend,
            **(dict(write_kwargs) if write_kwargs else {}),
        )

        return target

    def to_parquet(
        self,
        path: Path | str,
        /,
        *,
        backend: DataframeBackends | None = None,
        read_kwargs: Mapping[str, Any] | None = None,
        write_kwargs: Mapping[str, Any] | None = None,
    ) -> DataFile:
        """Round-trip the file's contents into a new parquet file.

        Thin shortcut for :meth:`convert_to` with the parquet subclass
        lazily imported so the base module stays usable without the
        parquet extras installed.

        Parameters
        ----------
        path : pathlib.Path or str
            Destination parquet path.
        backend : {"pandas", "polars"} or None, optional
            DataFrame backend for the intermediate round-trip;
            defaults to :attr:`backend`.
        read_kwargs : Mapping[str, Any] or None, optional
            Extra keyword arguments forwarded to :meth:`read`.
        write_kwargs : Mapping[str, Any] or None, optional
            Extra keyword arguments forwarded to the parquet writer
            (for example ``partition_cols=...``).

        Returns
        -------
        DataFile
            Handle to the newly written parquet file.
        """
        from mayutils.interfaces.filetypes.parquet import Parquet  # noqa: PLC0415

        return self.convert_to(
            Parquet,
            path=path,
            backend=backend,
            read_kwargs=read_kwargs,
            write_kwargs=write_kwargs,
        )

    def to_csv(
        self,
        path: Path | str,
        /,
        *,
        backend: DataframeBackends | None = None,
        read_kwargs: Mapping[str, Any] | None = None,
        write_kwargs: Mapping[str, Any] | None = None,
    ) -> DataFile:
        """Round-trip the file's contents into a new CSV file.

        Parameters
        ----------
        path : pathlib.Path or str
            Destination CSV path.
        backend : {"pandas", "polars"} or None, optional
            DataFrame backend for the intermediate round-trip;
            defaults to :attr:`backend`.
        read_kwargs : Mapping[str, Any] or None, optional
            Extra keyword arguments forwarded to :meth:`read`.
        write_kwargs : Mapping[str, Any] or None, optional
            Extra keyword arguments forwarded to the CSV writer.

        Returns
        -------
        DataFile
            Handle to the newly written CSV file.
        """
        from mayutils.interfaces.filetypes.csv import Csv  # noqa: PLC0415

        return self.convert_to(
            Csv,
            path=path,
            backend=backend,
            read_kwargs=read_kwargs,
            write_kwargs=write_kwargs,
        )

    def to_feather(
        self,
        path: Path | str,
        /,
        *,
        backend: DataframeBackends | None = None,
        read_kwargs: Mapping[str, Any] | None = None,
        write_kwargs: Mapping[str, Any] | None = None,
    ) -> DataFile:
        """Round-trip the file's contents into a new Feather file.

        Parameters
        ----------
        path : pathlib.Path or str
            Destination Feather path.
        backend : {"pandas", "polars"} or None, optional
            DataFrame backend for the intermediate round-trip;
            defaults to :attr:`backend`.
        read_kwargs : Mapping[str, Any] or None, optional
            Extra keyword arguments forwarded to :meth:`read`.
        write_kwargs : Mapping[str, Any] or None, optional
            Extra keyword arguments forwarded to the Feather writer.

        Returns
        -------
        DataFile
            Handle to the newly written Feather file.
        """
        from mayutils.interfaces.filetypes.feather import Feather  # noqa: PLC0415

        return self.convert_to(
            Feather,
            path=path,
            backend=backend,
            read_kwargs=read_kwargs,
            write_kwargs=write_kwargs,
        )

    def to_xlsx(
        self,
        path: Path | str,
        /,
        *,
        sheet: str = "Sheet1",
        backend: DataframeBackends | None = None,
        read_kwargs: Mapping[str, Any] | None = None,
        write_kwargs: Mapping[str, Any] | None = None,
    ) -> DataFile:
        """Round-trip the file's contents into a single sheet of a new XLSX file.

        Parameters
        ----------
        path : pathlib.Path or str
            Destination XLSX path.
        sheet : str, default ``"Sheet1"``
            Name of the sheet to create or replace inside the XLSX
            workbook.
        backend : {"pandas", "polars"} or None, optional
            DataFrame backend for the intermediate round-trip;
            defaults to :attr:`backend`.
        read_kwargs : Mapping[str, Any] or None, optional
            Extra keyword arguments forwarded to :meth:`read`.
        write_kwargs : Mapping[str, Any] or None, optional
            Extra keyword arguments forwarded to the XLSX writer.

        Returns
        -------
        DataFile
            Handle to the newly written sheet.
        """
        from mayutils.interfaces.filetypes.xlsx import XlsxSheet  # noqa: PLC0415

        return self.convert_to(
            XlsxSheet,
            path=path,
            backend=backend,
            read_kwargs=read_kwargs,
            write_kwargs=write_kwargs,
            sheet=sheet,
        )

    @overload
    def read(
        self,
        *,
        dataframe_backend: Literal["pandas"],
        **kwargs: Any,  # noqa: ANN401
    ) -> DataFrame: ...

    @overload
    def read(
        self,
        *,
        dataframe_backend: Literal["polars"],
        **kwargs: Any,  # noqa: ANN401
    ) -> pl.DataFrame: ...

    @overload
    def read(
        self,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> DataFrames: ...

    def read(
        self,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: Any,
    ) -> DataFrames:
        """Materialise the file into a DataFrame.

        Resolves ``dataframe_backend`` against :attr:`backend` when
        unset and dispatches to the format-specific :meth:`_read`
        hook; concrete subclasses only implement ``_read``.

        Parameters
        ----------
        dataframe_backend : {"pandas", "polars"} or None, optional
            DataFrame library to return. When ``None``, falls back to
            :attr:`backend`.
        **kwargs
            Format-specific options forwarded verbatim to the
            underlying reader.

        Returns
        -------
        pandas.DataFrame or polars.DataFrame
            Fully loaded DataFrame whose concrete type matches the
            resolved ``dataframe_backend``.
        """
        resolved_backend = dataframe_backend if dataframe_backend is not None else self.backend

        return self._read(
            dataframe_backend=resolved_backend,
            **kwargs,
        )

    @abstractmethod
    def _read(
        self,
        *,
        dataframe_backend: DataframeBackends,
        **kwargs: Any,  # noqa: ANN401
    ) -> DataFrames:
        """Format-specific read hook invoked by :meth:`read`.

        The backend has already been resolved against :attr:`backend`,
        so implementations receive a concrete
        :data:`~mayutils.objects.dataframes.DataframeBackends` literal
        and must return the matching DataFrame type.

        Parameters
        ----------
        dataframe_backend : {"pandas", "polars"}
            Resolved DataFrame library to return.
        **kwargs
            Format-specific options forwarded verbatim from
            :meth:`read`.

        Returns
        -------
        pandas.DataFrame or polars.DataFrame
            Fully loaded DataFrame whose concrete type matches
            ``dataframe_backend``.
        """

    def to_pandas(
        self,
        **read_kwargs: Any,  # noqa: ANN401
    ) -> DataFrame:
        """Alias :meth:`read` with ``dataframe_backend="pandas"``.

        Parameters
        ----------
        read_kwargs : Mapping[str, Any] or None, optional
            Extra keyword arguments forwarded to :meth:`read`.

        Returns
        -------
        pandas.DataFrame
            Fully loaded DataFrame.
        """
        return self.read(
            dataframe_backend="pandas",
            **read_kwargs,
        )

    def to_polars(
        self,
        **read_kwargs: Any,  # noqa: ANN401
    ) -> pl.DataFrame:
        """Alias :meth:`read` with ``dataframe_backend="polars"``.

        Parameters
        ----------
        read_kwargs : Mapping[str, Any] or None, optional
            Extra keyword arguments forwarded to :meth:`read`.

        Returns
        -------
        polars.DataFrame
            Fully loaded DataFrame.
        """
        return self.read(
            dataframe_backend="polars",
            **read_kwargs,
        )

    @staticmethod
    def resolve_write_backend(
        df: DataFrames,
        dataframe_backend: DataframeBackends | None,
    ) -> DataframeBackends:
        """Resolve the write backend and validate it matches ``type(df)``.

        Subclasses implementing :meth:`write` must call this at the
        top of the method so the contract that ``df`` and the resolved
        backend agree is enforced uniformly across every format rather
        than reimplemented per subclass.

        Parameters
        ----------
        df : pandas.DataFrame or polars.DataFrame
            DataFrame the caller intends to persist.
        dataframe_backend : {"pandas", "polars"} or None
            Explicit backend override supplied to :meth:`write`. When
            ``None``, the backend is inferred from ``type(df)``.

        Returns
        -------
        {"pandas", "polars"}
            The resolved backend, guaranteed to match ``type(df)``.

        Raises
        ------
        TypeError
            If an explicit ``dataframe_backend`` is supplied and does
            not match ``type(df)``.
        """
        inferred = infer_backend(df)
        if dataframe_backend is None:
            return inferred

        if inferred != dataframe_backend:
            msg = f"Expected a {dataframe_backend} DataFrame for backend '{dataframe_backend}', got {type(df).__name__}"
            raise TypeError(msg)

        return dataframe_backend

    @overload
    def write(
        self,
        df: DataFrame,
        /,
        *,
        dataframe_backend: Literal["pandas"] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self: ...

    @overload
    def write(
        self,
        df: pl.DataFrame,
        /,
        *,
        dataframe_backend: Literal["polars"] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self: ...

    @overload
    def write(
        self,
        df: DataFrames,
        /,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self: ...

    def write(
        self,
        df: DataFrames,
        /,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: Any,
    ) -> Self:
        """Serialise a DataFrame into the file at :attr:`path`.

        Routes through :meth:`_resolve_write_backend` before dispatching
        to the format-specific :meth:`_write` hook, so every subclass
        inherits the ``df``/backend type-match check without having to
        reimplement it.

        Parameters
        ----------
        df : pandas.DataFrame or polars.DataFrame
            DataFrame to persist. The concrete type is authoritative
            when ``dataframe_backend`` is ``None``.
        dataframe_backend : {"pandas", "polars"} or None, optional
            Explicit backend override for dispatch. When ``None``, the
            writer inspects ``type(df)``.
        **kwargs
            Format-specific options forwarded verbatim to the
            underlying writer.

        Returns
        -------
        Self
            The current handle, enabling fluent chaining.

        Raises
        ------
        TypeError
            If ``dataframe_backend`` is supplied and does not match
            ``type(df)``.
        """
        resolved_backend = self.resolve_write_backend(df, dataframe_backend)

        self._write(
            df,
            dataframe_backend=resolved_backend,
            **kwargs,
        )

        return self

    @abstractmethod
    def _write(
        self,
        df: DataFrames,
        /,
        *,
        dataframe_backend: DataframeBackends,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Format-specific write hook invoked by :meth:`write`.

        By the time ``_write`` is called, the base class has already
        verified that ``type(df)`` agrees with ``dataframe_backend``,
        so implementations can dispatch on ``dataframe_backend``
        without re-checking the DataFrame's runtime type.

        Parameters
        ----------
        df : pandas.DataFrame or polars.DataFrame
            DataFrame to persist.
        dataframe_backend : {"pandas", "polars"}
            Resolved backend that matches ``type(df)``.
        **kwargs
            Format-specific options forwarded verbatim from
            :meth:`write`.
        """

    @abstractmethod
    def schema(
        self,
    ) -> dict[str, Any]:
        """Return the column-name-to-dtype mapping declared by the file.

        Subclasses should read metadata cheaply where the format
        allows (parquet footer, feather IPC header, xlsx dimensions);
        when the format exposes no schema separately from the body
        (CSV), a small header sample is acceptable with documented
        heuristics.

        Returns
        -------
        dict of str to Any
            Column name → dtype mapping; dtype values are
            format-specific (numpy dtype objects, polars type
            instances, or their string representations).
        """

    @abstractmethod
    def row_count(
        self,
    ) -> int:
        """Return the number of data rows in the file (excluding headers).

        Subclasses should prefer metadata reads over body scans when
        the format supports it; streaming counts are acceptable
        fallbacks.

        Returns
        -------
        int
            Non-negative number of rows.
        """

    @abstractmethod
    def iter_chunks(
        self,
        chunk_size: int,
        /,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Iterator[DataFrames]:
        """Stream the file as an iterator of DataFrame chunks.

        Parameters
        ----------
        chunk_size : int
            Upper bound on the number of rows per yielded DataFrame.
            Implementations may yield a smaller final chunk.
        dataframe_backend : {"pandas", "polars"} or None, optional
            DataFrame library for each yielded chunk; defaults to
            :attr:`backend`.
        **kwargs
            Format-specific options forwarded verbatim.

        Yields
        ------
        pandas.DataFrame or polars.DataFrame
            Successive chunks whose concatenation equals
            :meth:`read`.
        """


__all__ = [
    "DataFile",
]
