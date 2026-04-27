"""
Group filetype-specific authoring and rendering helpers in one package.

This package collects adapters that speak particular document formats
rather than third-party services: :mod:`.markdown` wraps Mistune-backed
Markdown parsing, :mod:`.pptx` drives ``python-pptx`` PowerPoint
authoring, and :mod:`.pdf` renders documents through PyMuPDF and
Pillow. Tabular formats (CSV, Parquet, Feather, XLSX) share a common
instance-based facade through :class:`DataFile`, so every registered
subclass inherits cross-format conversion for free once it implements
the read/write/introspection/streaming surface. Each submodule is
guarded by an optional dependency extra so minimal installs stay
lightweight.

See Also
--------
mayutils.interfaces.filetypes.csv : CSV tabular adapter.
mayutils.interfaces.filetypes.parquet : Parquet tabular adapter.
mayutils.interfaces.filetypes.feather : Feather tabular adapter.
mayutils.interfaces.filetypes.xlsx : XLSX sheet tabular adapter.
mayutils.interfaces.filetypes.pptx : PowerPoint authoring helpers.
mayutils.interfaces.filetypes.pdf : PDF rendering helpers.
mayutils.interfaces.filetypes.docx : Word authoring helpers.
mayutils.interfaces.filetypes.markdown : Markdown parsing helpers.
pathlib.Path : Standard-library path abstraction used throughout.

Examples
--------
>>> from pathlib import Path
>>> from mayutils.environment.memoisation import register_datafile
>>> from mayutils.interfaces.filetypes import DataFile
>>> register_datafile("parquet")
>>> handle = DataFile.from_path(Path("sales.parquet"))
>>> isinstance(handle.path, Path)
True
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
    """
    Represent a tabular file on disk through an instance-based handle.

    Subclasses bind a single file format (parquet, csv, feather, xlsx
    sheet, ...) and implement the abstract methods below; the concrete
    methods on this base provide path-level helpers, a suffix-indexed
    registry, and generic format conversion built on top of the read
    and write abstract methods. The class is deliberately modelled on
    the facade style used by
    :class:`mayutils.interfaces.filetypes.pptx.Presentation`: callers
    hold an instance, operate on it fluently, and reach for the
    underlying library only when necessary.

    Parameters
    ----------
    path
        Filesystem location of the target file. The path does not have
        to exist yet (it may be about to be written), but its suffix
        must match :attr:`suffix` declared on the subclass.
    backend
        Default DataFrame library to materialise reads as and to
        dispatch writes through when no explicit backend is supplied at
        call time. Passed through to the read/write implementations as
        ``dataframe_backend``.

    Attributes
    ----------
    path
        Resolved path to the file.
    backend
        Default backend captured at construction.
    suffix
        File extension that identifies the format (``".parquet"``,
        ``".csv"``, ...). Must be declared as a :class:`ClassVar` on
        every concrete subclass.

    Raises
    ------
    ValueError
        If the supplied ``path`` has a suffix that does not match the
        subclass's :attr:`suffix`.

    See Also
    --------
    mayutils.interfaces.filetypes.csv.Csv : CSV subclass.
    mayutils.interfaces.filetypes.parquet.Parquet : Parquet subclass.
    mayutils.interfaces.filetypes.feather.Feather : Feather subclass.
    mayutils.interfaces.filetypes.xlsx.XlsxSheet : XLSX sheet subclass.
    pathlib.Path : Path abstraction used for ``path``.

    Examples
    --------
    >>> from pathlib import Path
    >>> from mayutils.environment.memoisation import register_datafile
    >>> from mayutils.interfaces.filetypes import DataFile
    >>> register_datafile("csv")
    >>> handle = DataFile.from_path(Path("customers.csv"))
    >>> handle.path.suffix
    '.csv'
    """

    suffix: ClassVar[str]
    _registry: ClassVar[dict[str, type[DataFile]]] = {}

    def __init_subclass__(
        cls,
        *,
        register: bool = True,
        **kwargs: object,
    ) -> None:
        """
        Register concrete subclasses in the suffix-indexed dispatch table.

        Runs automatically when a subclass body finishes executing, so
        importing :mod:`mayutils.interfaces.filetypes.parquet` is all
        that is needed to make ``DataFile.from_path("foo.parquet")``
        resolve correctly. The ``register`` flag lets an advanced
        subclass opt out when its suffix would otherwise collide with
        an existing entry (for example an alternate view of parquet).

        Parameters
        ----------
        register
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

        See Also
        --------
        DataFile.from_path : Consumer of the populated registry.
        mayutils.interfaces.filetypes.csv.Csv : Example registrant.
        mayutils.interfaces.filetypes.parquet.Parquet : Example registrant.
        pathlib.Path.suffix : Source of the suffix used as the key.

        Examples
        --------
        >>> from mayutils.environment.memoisation import register_datafile
        >>> from mayutils.interfaces.filetypes import DataFile
        >>> register_datafile("csv")
        >>> ".csv" in DataFile._registry
        True
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
        """
        Bind the handle to ``path`` and capture the default backend.

        No I/O happens here: the constructor merely validates that
        ``path`` has the suffix expected by the subclass and stashes
        the default backend for later use. Actual reads and writes are
        deferred until :meth:`read`, :meth:`write`, :meth:`schema`,
        :meth:`row_count`, or :meth:`iter_chunks` is called, which
        keeps construction cheap and lets callers build handles for
        files that do not yet exist.

        Parameters
        ----------
        path
            Filesystem location of the target file. A string is
            normalised to :class:`pathlib.Path`. The file is not opened
            here; I/O happens lazily on :meth:`read`, :meth:`write`,
            :meth:`schema`, :meth:`row_count`, and :meth:`iter_chunks`.
        backend
            Default DataFrame backend for reads and for dispatching
            writes when the caller does not override it.

        Raises
        ------
        ValueError
            If ``path`` has a suffix that does not match the
            subclass's :attr:`suffix`.

        See Also
        --------
        DataFile.from_path : Factory that dispatches by suffix.
        mayutils.interfaces.filetypes.csv.Csv : Concrete subclass.
        mayutils.interfaces.filetypes.parquet.Parquet : Concrete subclass.
        pathlib.Path : Path abstraction used for ``path``.

        Examples
        --------
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> handle = Csv(Path("events.csv"))
        >>> handle.backend
        'pandas'
        """
        self.path = Path(path)
        self.backend: DataframeBackends = backend

        if self.path.suffix.lower() != self.suffix.lower():
            msg = f"{type(self).__name__} expects a '{self.suffix}' file; got '{self.path.suffix}'."
            raise ValueError(msg)

    def _identity(
        self,
    ) -> str:
        """
        Return the identity line used as a header in :meth:`__repr__`.

        Formats the handle as ``"<Class>(<path>, backend=<backend>)"``
        so that even when a preview fails, callers can still see which
        file the handle is bound to. Subclasses override this to inject
        extra state (for example :class:`XlsxSheet` appends the bound
        sheet name) while keeping the enclosing ``repr`` layout stable.

        Returns
        -------
            ``"<Class>(<path>, backend=<backend>)"`` by default.

        See Also
        --------
        DataFile.__repr__ : Consumer of this identity line.
        DataFile._repr_html_ : HTML counterpart.
        mayutils.interfaces.filetypes.xlsx.XlsxSheet : Override example.
        pathlib.Path : Path type rendered into the output.

        Examples
        --------
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> handle = Csv(Path("demo.csv"))
        >>> "demo.csv" in handle._identity()
        True
        """
        return f"{type(self).__name__}({self.path!s}, backend={self.backend!r})"

    def __repr__(
        self,
    ) -> str:
        """
        Return an identity header followed by a small file preview.

        Renders the header via :meth:`_identity` and appends the
        DataFrame's own ``repr`` for a cheap first-look when the file
        exists and can be read. Any :data:`PREVIEW_ERRORS` raised along
        the way fall back to the identity line alone so ``repr`` is
        safe to call from debuggers, loggers, and notebooks even when
        extras are missing or the file is malformed.

        Returns
        -------
            Multi-line string: identity line, then a newline, then
            the rendered preview. A single line if no preview is
            available.

        See Also
        --------
        DataFile._identity : Produces the header line.
        DataFile._repr_html_ : HTML counterpart for rich front-ends.
        mayutils.interfaces.filetypes.csv.Csv : Concrete subclass.
        pathlib.Path.is_file : Existence check used here.

        Examples
        --------
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> handle = Csv(Path("missing.csv"))
        >>> repr(handle).startswith("Csv(")
        True
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
        """
        Render an identity header and a small HTML preview of the file.

        Delegates the table-level rendering to the DataFrame's own
        ``_repr_html_`` (pandas and polars both provide it), so the
        resulting markup matches whatever the front-end normally
        produces for the resolved backend. The identity line is wrapped
        in ``<code>`` tags so Jupyter and Quarto render it in a
        monospace style, and any preview failure falls back to just
        that header.

        Returns
        -------
            HTML string that front-ends can embed inline.

        See Also
        --------
        DataFile.__repr__ : Plain-text counterpart.
        DataFile._identity : Produces the header line.
        mayutils.interfaces.filetypes.xlsx.XlsxSheet : Sheet-aware override.
        pathlib.Path.is_file : Existence check used here.

        Examples
        --------
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> handle = Csv(Path("missing.csv"))
        >>> handle._repr_html_().startswith("<code>")
        True
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
        """
        Build the appropriate subclass for ``path`` via suffix dispatch.

        Looks up the lower-cased suffix of ``path`` in the registry
        populated by :meth:`__init_subclass__` and instantiates the
        matching subclass. The returned object is an instance of
        whichever concrete :class:`DataFile` subclass registered itself
        for the given suffix at import time, making this the preferred
        entry point when the concrete format is only known at runtime.

        Parameters
        ----------
        path
            Path whose suffix selects the concrete subclass. The
            resolved suffix is lower-cased before lookup.
        backend
            Forwarded to the subclass's ``__init__`` as the default
            DataFrame backend.
        **kwargs
            Forwarded verbatim to the subclass's ``__init__``. Use
            this to pass subclass-specific options such as ``sheet``
            for :class:`XlsxSheet`.

        Returns
        -------
            A newly constructed instance of the registered subclass
            bound to ``path``.

        Raises
        ------
        ValueError
            If no subclass has been registered for the suffix of
            ``path``; usually this means the relevant subclass module
            has not been imported.

        See Also
        --------
        DataFile.__init_subclass__ : Populates the registry.
        mayutils.interfaces.filetypes.csv.Csv : Concrete subclass.
        mayutils.interfaces.filetypes.parquet.Parquet : Concrete subclass.
        pathlib.Path.suffix : Source of the dispatch key.

        Examples
        --------
        >>> from pathlib import Path
        >>> from mayutils.environment.memoisation import register_datafile
        >>> from mayutils.interfaces.filetypes import DataFile
        >>> register_datafile("feather")
        >>> handle = DataFile.from_path(Path("orders.feather"))
        >>> handle.suffix
        '.feather'
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
        """
        Return whether the underlying file exists on disk.

        Thin wrapper around :meth:`pathlib.Path.is_file` so downstream
        code can test for the file without knowing whether ``path`` is
        a string or a :class:`~pathlib.Path`. Directories, broken
        symlinks, and absent paths all return ``False``, matching the
        stricter semantics callers need when deciding whether a preview
        read is safe to attempt.

        Returns
        -------
            ``True`` iff :attr:`path` resolves to a regular file; a
            directory, a symlink to a missing target, or an absent
            path all return ``False``.

        See Also
        --------
        DataFile.size : Companion helper built on top of ``path.stat``.
        DataFile.__repr__ : Consumer that skips preview on ``False``.
        mayutils.interfaces.filetypes.csv.Csv : Concrete subclass.
        pathlib.Path.is_file : Underlying existence check.

        Examples
        --------
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> handle = Csv(Path("missing.csv"))
        >>> handle.exists()
        False
        """
        return self.path.is_file()

    def size(
        self,
    ) -> int:
        """
        Return the file size in bytes.

        Reports whatever :meth:`pathlib.Path.stat` returns for
        ``st_size`` so this works uniformly for local files, network
        mounts, and file-like paths that back onto ``os.stat``. Useful
        as a quick sanity check before converting to another format or
        for logging the footprint of an input file without touching its
        contents.

        Returns
        -------
            Number of bytes reported by ``path.stat().st_size``.

        See Also
        --------
        DataFile.exists : Companion helper that checks for presence.
        DataFile.row_count : Row-level counterpart.
        mayutils.interfaces.filetypes.parquet.Parquet : Concrete subclass.
        pathlib.Path.stat : Underlying ``stat`` call.

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
        ...     handle.size() > 0
        True
        """
        return self.path.stat().st_size

    def columns(
        self,
    ) -> list[str]:
        """
        Return the column names declared by the file.

        Thin convenience wrapper over :meth:`schema` that discards
        dtype information, so subclasses only need to implement schema
        extraction once and every caller that just wants header names
        can avoid manually peeling the keys out. Handy when building
        SELECT lists or validating against an expected column set
        before a full read.

        Returns
        -------
            Column names in declaration order.

        See Also
        --------
        DataFile.schema : Underlying column-to-dtype mapping.
        DataFile.dtypes : Alias returning the full mapping.
        mayutils.interfaces.filetypes.csv.Csv : Concrete subclass.
        pathlib.Path : Path abstraction used for the file location.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "customers.csv"
        ...     pd.DataFrame({"id": [1], "name": ["Ada"], "email": ["a@b.c"]}).to_csv(p, index=False)
        ...     handle = Csv(p)
        ...     handle.columns()
        ['id', 'name', 'email']
        """
        return list(self.schema())

    def dtypes(
        self,
    ) -> dict[str, object]:
        """
        Return the column-to-dtype mapping declared by the file.

        This is a straight alias for :meth:`schema` kept for symmetry
        with the pandas ``DataFrame.dtypes`` attribute that most
        callers reach for first. Subclasses do not need to override it
        because the delegation is unconditional, which keeps the
        surface area every concrete format has to implement small and
        focused on :meth:`schema`.

        Returns
        -------
            Column name to dtype mapping as returned by
            :meth:`schema`.

        See Also
        --------
        DataFile.schema : Underlying implementation.
        DataFile.columns : Column-name-only counterpart.
        mayutils.interfaces.filetypes.parquet.Parquet : Concrete subclass.
        pathlib.Path : Path abstraction used for the file location.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "events.csv"
        ...     pd.DataFrame({"id": [1], "ts": ["2024-01-01"], "payload": ["x"]}).to_csv(p, index=False)
        ...     handle = Csv(p)
        ...     list(handle.dtypes())
        ['id', 'ts', 'payload']
        """
        return self.schema()

    def convert_to(
        self,
        target_cls: type[DataFile],
        /,
        path: Path | str,
        *,
        backend: DataframeBackends | None = None,
        read_kwargs: Mapping[str, object] | None = None,
        write_kwargs: Mapping[str, object] | None = None,
        **init_kwargs: object,
    ) -> DataFile:
        """
        Round-trip the file's contents into another registered format.

        Materialises the current file into a DataFrame via
        :meth:`read`, constructs a ``target_cls`` handle bound to
        ``path``, and writes the DataFrame through its
        :meth:`write`. The returned handle is the newly constructed
        target, so subsequent reads can chain directly off the call.

        Parameters
        ----------
        target_cls
            Concrete :class:`DataFile` subclass to construct at
            ``path`` and populate from ``self``.
        path
            Destination path for the converted file. Passed to
            ``target_cls(path, ...)``.
        backend
            DataFrame backend for both the intermediate read and
            write. When ``None``, falls back to :attr:`backend`.
        read_kwargs
            Extra keyword arguments forwarded to :meth:`read`.
        write_kwargs
            Extra keyword arguments forwarded to the target's
            :meth:`write`.
        **init_kwargs
            Extra keyword arguments forwarded to ``target_cls``'s
            ``__init__`` (for example ``sheet=...`` when converting to
            an :class:`XlsxSheet`).

        Returns
        -------
            Handle to the newly written file in the target format.

        See Also
        --------
        DataFile.to_parquet : Shortcut for parquet targets.
        DataFile.to_csv : Shortcut for CSV targets.
        mayutils.interfaces.filetypes.feather.Feather : Example target.
        pathlib.Path : Path abstraction used for ``path``.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> from mayutils.interfaces.filetypes.parquet import Parquet
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     src = Path(tmp) / "source.csv"
        ...     dst = Path(tmp) / "sink.parquet"
        ...     pd.DataFrame({"a": [1, 2]}).to_csv(src, index=False)
        ...     handle = Csv(src)
        ...     converted = handle.convert_to(Parquet, path=dst)
        ...     converted.path.exists()
        True
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
        read_kwargs: Mapping[str, object] | None = None,
        write_kwargs: Mapping[str, object] | None = None,
    ) -> DataFile:
        """
        Round-trip the file's contents into a new parquet file.

        Thin shortcut for :meth:`convert_to` with the parquet subclass
        lazily imported so the base module stays usable without the
        parquet extras installed. The write happens through the target
        subclass, so any parquet-specific options (partition columns,
        compression codecs) go through ``write_kwargs`` and end up as
        keyword arguments to the underlying writer.

        Parameters
        ----------
        path
            Destination parquet path.
        backend
            DataFrame backend for the intermediate round-trip;
            defaults to :attr:`backend`.
        read_kwargs
            Extra keyword arguments forwarded to :meth:`read`.
        write_kwargs
            Extra keyword arguments forwarded to the parquet writer
            (for example ``partition_cols=...``).

        Returns
        -------
            Handle to the newly written parquet file.

        See Also
        --------
        DataFile.convert_to : Underlying generic converter.
        mayutils.interfaces.filetypes.parquet.Parquet : Target subclass.
        mayutils.interfaces.filetypes.csv.Csv : Common source format.
        pathlib.Path : Path abstraction used for ``path``.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     src = Path(tmp) / "source.csv"
        ...     dst = Path(tmp) / "sink.parquet"
        ...     pd.DataFrame({"a": [1, 2]}).to_csv(src, index=False)
        ...     handle = Csv(src)
        ...     out = handle.to_parquet(dst)
        ...     out.path.exists()
        True
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
        read_kwargs: Mapping[str, object] | None = None,
        write_kwargs: Mapping[str, object] | None = None,
    ) -> DataFile:
        """
        Round-trip the file's contents into a new CSV file.

        Shortcut for :meth:`convert_to` with the CSV subclass lazily
        imported so the base module stays importable without the CSV
        extras installed. CSV is lossy compared with binary formats
        (dtypes are stringified on write), so this is typically used
        for inspection, manual editing, or hand-off to tools that only
        understand CSV.

        Parameters
        ----------
        path
            Destination CSV path.
        backend
            DataFrame backend for the intermediate round-trip;
            defaults to :attr:`backend`.
        read_kwargs
            Extra keyword arguments forwarded to :meth:`read`.
        write_kwargs
            Extra keyword arguments forwarded to the CSV writer.

        Returns
        -------
            Handle to the newly written CSV file.

        See Also
        --------
        DataFile.convert_to : Underlying generic converter.
        mayutils.interfaces.filetypes.csv.Csv : Target subclass.
        mayutils.interfaces.filetypes.parquet.Parquet : Common source format.
        pathlib.Path : Path abstraction used for ``path``.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.parquet import Parquet
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     src = Path(tmp) / "source.parquet"
        ...     dst = Path(tmp) / "sink.csv"
        ...     pd.DataFrame({"a": [1, 2]}).to_parquet(src)
        ...     handle = Parquet(src)
        ...     out = handle.to_csv(dst)
        ...     out.path.exists()
        True
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
        read_kwargs: Mapping[str, object] | None = None,
        write_kwargs: Mapping[str, object] | None = None,
    ) -> DataFile:
        """
        Round-trip the file's contents into a new Feather file.

        Shortcut for :meth:`convert_to` with the Feather subclass
        lazily imported so the base module stays importable without
        the Feather extras installed. Feather is a good fit for
        short-lived on-disk caches between a producer and consumer in
        the same process tree because it preserves Arrow-native dtypes
        and reads back quickly.

        Parameters
        ----------
        path
            Destination Feather path.
        backend
            DataFrame backend for the intermediate round-trip;
            defaults to :attr:`backend`.
        read_kwargs
            Extra keyword arguments forwarded to :meth:`read`.
        write_kwargs
            Extra keyword arguments forwarded to the Feather writer.

        Returns
        -------
            Handle to the newly written Feather file.

        See Also
        --------
        DataFile.convert_to : Underlying generic converter.
        mayutils.interfaces.filetypes.feather.Feather : Target subclass.
        mayutils.interfaces.filetypes.parquet.Parquet : Long-term counterpart.
        pathlib.Path : Path abstraction used for ``path``.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     src = Path(tmp) / "source.csv"
        ...     dst = Path(tmp) / "sink.feather"
        ...     pd.DataFrame({"a": [1, 2]}).to_csv(src, index=False)
        ...     handle = Csv(src)
        ...     out = handle.to_feather(dst)
        ...     out.path.exists()
        True
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
        read_kwargs: Mapping[str, object] | None = None,
        write_kwargs: Mapping[str, object] | None = None,
    ) -> DataFile:
        """
        Round-trip the file's contents into a single sheet of a new XLSX file.

        Shortcut for :meth:`convert_to` with the XLSX sheet subclass
        lazily imported so the base module stays importable without
        the ``openpyxl``/``xlsxwriter`` extras installed. The ``sheet``
        argument is forwarded to the subclass constructor so callers
        can control which tab is written; existing sheets at the same
        path are preserved when the underlying writer supports it.

        Parameters
        ----------
        path
            Destination XLSX path.
        sheet
            Name of the sheet to create or replace inside the XLSX
            workbook.
        backend
            DataFrame backend for the intermediate round-trip;
            defaults to :attr:`backend`.
        read_kwargs
            Extra keyword arguments forwarded to :meth:`read`.
        write_kwargs
            Extra keyword arguments forwarded to the XLSX writer.

        Returns
        -------
            Handle to the newly written sheet.

        See Also
        --------
        DataFile.convert_to : Underlying generic converter.
        mayutils.interfaces.filetypes.xlsx.XlsxSheet : Target subclass.
        mayutils.interfaces.filetypes.csv.Csv : Common source format.
        pathlib.Path : Path abstraction used for ``path``.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     src = Path(tmp) / "source.csv"
        ...     dst = Path(tmp) / "sink.xlsx"
        ...     pd.DataFrame({"a": [1, 2]}).to_csv(src, index=False)
        ...     handle = Csv(src)
        ...     out = handle.to_xlsx(dst, sheet="Customers")
        ...     out.path.exists()
        True
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
    def read(  # numpydoc ignore=GL08
        self,
        *,
        dataframe_backend: Literal["pandas"],
        **kwargs: object,
    ) -> DataFrame: ...

    @overload
    def read(  # numpydoc ignore=GL08
        self,
        *,
        dataframe_backend: Literal["polars"],
        **kwargs: object,
    ) -> pl.DataFrame: ...

    @overload
    def read(  # numpydoc ignore=GL08
        self,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: object,
    ) -> DataFrames: ...

    def read(
        self,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: object,
    ) -> DataFrames:
        """
        Materialise the file into a DataFrame.

        Resolves ``dataframe_backend`` against :attr:`backend` when
        unset and dispatches to the format-specific :meth:`_read`
        hook; concrete subclasses only implement ``_read``. This keeps
        the backend-resolution logic in one place so every format
        inherits the same ``None``-means-default semantics without
        reimplementing it.

        Parameters
        ----------
        dataframe_backend
            DataFrame library to return. When ``None``, falls back to
            :attr:`backend`.
        **kwargs
            Format-specific options forwarded verbatim to the
            underlying reader.

        Returns
        -------
            Fully loaded DataFrame whose concrete type matches the
            resolved ``dataframe_backend``.

        See Also
        --------
        DataFile._read : Format-specific hook dispatched to.
        DataFile.write : Symmetric writer counterpart.
        mayutils.interfaces.filetypes.csv.Csv : Example reader target.
        pathlib.Path : Path abstraction for the on-disk file.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "events.csv"
        ...     pd.DataFrame({"a": [1, 2, 3]}).to_csv(p, index=False)
        ...     handle = Csv(p)
        ...     df = handle.read(dataframe_backend="pandas")
        ...     df.shape
        (3, 1)
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
        **kwargs: object,
    ) -> DataFrames:
        """
        Dispatch the format-specific read invoked by :meth:`read`.

        The backend has already been resolved against :attr:`backend`,
        so implementations receive a concrete
        :data:`~mayutils.objects.dataframes.DataframeBackends` literal
        and must return the matching DataFrame type. Keeping this as
        an abstract method forces every concrete subclass to make the
        choice explicit for its format rather than silently falling
        back to whichever library happens to be installed.

        Parameters
        ----------
        dataframe_backend
            Resolved DataFrame library to return.
        **kwargs
            Format-specific options forwarded verbatim from
            :meth:`read`.

        Returns
        -------
            Fully loaded DataFrame whose concrete type matches
            ``dataframe_backend``.

        See Also
        --------
        DataFile.read : Public entry point.
        DataFile._write : Symmetric writer hook.
        mayutils.interfaces.filetypes.parquet.Parquet : Example implementer.
        pathlib.Path : Path abstraction for the on-disk file.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.parquet import Parquet
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "events.parquet"
        ...     pd.DataFrame({"a": [1, 2, 3]}).to_parquet(p)
        ...     handle = Parquet(p)
        ...     handle._read(dataframe_backend="pandas").shape
        (3, 1)
        """

    def to_pandas(
        self,
        **read_kwargs: object,
    ) -> DataFrame:
        """
        Read the file as a :class:`pandas.DataFrame` regardless of backend.

        Convenience shortcut for call sites that always want a
        :class:`pandas.DataFrame` regardless of the handle's default
        backend. Because it forwards straight through to :meth:`read`,
        any format-specific options are still available through
        ``**read_kwargs`` without having to go through the broader
        backend-selecting signature.

        Parameters
        ----------
        **read_kwargs
            Extra keyword arguments forwarded to :meth:`read`.

        Returns
        -------
            Fully loaded DataFrame.

        See Also
        --------
        DataFile.read : Underlying implementation.
        DataFile.to_polars : Polars counterpart.
        mayutils.interfaces.filetypes.csv.Csv : Example reader target.
        pathlib.Path : Path abstraction for the on-disk file.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "events.csv"
        ...     pd.DataFrame({"a": [1, 2]}).to_csv(p, index=False)
        ...     handle = Csv(p)
        ...     df = handle.to_pandas()
        ...     isinstance(df, pd.DataFrame)
        True
        """
        return self.read(
            dataframe_backend="pandas",
            **read_kwargs,
        )

    def to_polars(
        self,
        **read_kwargs: object,
    ) -> pl.DataFrame:
        """
        Read the file as a :class:`polars.DataFrame` regardless of backend.

        Convenience shortcut for call sites that always want a
        :class:`polars.DataFrame` regardless of the handle's default
        backend. Because it forwards straight through to :meth:`read`,
        any format-specific options are still available through
        ``**read_kwargs`` without having to go through the broader
        backend-selecting signature.

        Parameters
        ----------
        **read_kwargs
            Extra keyword arguments forwarded to :meth:`read`.

        Returns
        -------
            Fully loaded DataFrame.

        See Also
        --------
        DataFile.read : Underlying implementation.
        DataFile.to_pandas : Pandas counterpart.
        mayutils.interfaces.filetypes.parquet.Parquet : Example reader target.
        pathlib.Path : Path abstraction for the on-disk file.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> import polars as pl
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.parquet import Parquet
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "events.parquet"
        ...     pd.DataFrame({"a": [1, 2]}).to_parquet(p)
        ...     handle = Parquet(p)
        ...     df = handle.to_polars()
        ...     isinstance(df, pl.DataFrame)
        True
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
        """
        Resolve the write backend and validate it matches ``type(df)``.

        Subclasses implementing :meth:`write` must call this at the
        top of the method so the contract that ``df`` and the resolved
        backend agree is enforced uniformly across every format rather
        than reimplemented per subclass. When an explicit backend is
        supplied that disagrees with the DataFrame's runtime type, the
        helper raises rather than silently coercing, which matches the
        guard rails the rest of the I/O layer expects.

        Parameters
        ----------
        df
            DataFrame the caller intends to persist.
        dataframe_backend
            Explicit backend override supplied to :meth:`write`. When
            ``None``, the backend is inferred from ``type(df)``.

        Returns
        -------
            The resolved backend, guaranteed to match ``type(df)``.

        Raises
        ------
        TypeError
            If an explicit ``dataframe_backend`` is supplied and does
            not match ``type(df)``.

        See Also
        --------
        DataFile.write : Primary caller of this helper.
        mayutils.objects.dataframes.infer_backend : Inference helper.
        mayutils.interfaces.filetypes.parquet.Parquet : Example writer.
        pathlib.Path : Path abstraction for the on-disk file.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.interfaces.filetypes import DataFile
        >>> DataFile.resolve_write_backend(pd.DataFrame(), None)
        'pandas'
        """
        inferred = infer_backend(df)
        if dataframe_backend is None:
            return inferred

        if inferred != dataframe_backend:
            msg = f"Expected a {dataframe_backend} DataFrame for backend '{dataframe_backend}', got {type(df).__name__}"
            raise TypeError(msg)

        return dataframe_backend

    @overload
    def write(  # numpydoc ignore=GL08
        self,
        df: DataFrame,
        /,
        *,
        dataframe_backend: Literal["pandas"] | None = None,
        **kwargs: object,
    ) -> Self: ...

    @overload
    def write(  # numpydoc ignore=GL08
        self,
        df: pl.DataFrame,
        /,
        *,
        dataframe_backend: Literal["polars"] | None = None,
        **kwargs: object,
    ) -> Self: ...

    @overload
    def write(  # numpydoc ignore=GL08
        self,
        df: DataFrames,
        /,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: object,
    ) -> Self: ...

    def write(
        self,
        df: DataFrames,
        /,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: object,
    ) -> Self:
        """
        Serialise a DataFrame into the file at :attr:`path`.

        Routes through :meth:`resolve_write_backend` before
        dispatching to the format-specific :meth:`_write` hook, so
        every subclass inherits the ``df``/backend type-match check
        without having to reimplement it. Returning ``self`` lets
        callers chain further operations after the write, for example
        asserting on :meth:`row_count` without rebinding the handle.

        Parameters
        ----------
        df
            DataFrame to persist. The concrete type is authoritative
            when ``dataframe_backend`` is ``None``.
        dataframe_backend
            Explicit backend override for dispatch. When ``None``, the
            writer inspects ``type(df)``.
        **kwargs
            Format-specific options forwarded verbatim to the
            underlying writer.

        Returns
        -------
            The current handle, enabling fluent chaining.

        See Also
        --------
        DataFile._write : Format-specific hook dispatched to.
        DataFile.resolve_write_backend : Validation helper.
        mayutils.interfaces.filetypes.csv.Csv : Example writer target.
        pathlib.Path : Path abstraction for the on-disk file.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "out.csv"
        ...     handle = Csv(p)
        ...     _ = handle.write(pd.DataFrame({"id": [1]}))
        ...     p.exists()
        True
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
        **kwargs: object,
    ) -> None:
        """
        Dispatch the format-specific write invoked by :meth:`write`.

        By the time ``_write`` is called, the base class has already
        verified that ``type(df)`` agrees with ``dataframe_backend``,
        so implementations can dispatch on ``dataframe_backend``
        without re-checking the DataFrame's runtime type. This keeps
        per-format writers short and focused on library-specific
        serialisation details.

        Parameters
        ----------
        df
            DataFrame to persist.
        dataframe_backend
            Resolved backend that matches ``type(df)``.
        **kwargs
            Format-specific options forwarded verbatim from
            :meth:`write`.

        See Also
        --------
        DataFile.write : Public entry point.
        DataFile._read : Symmetric reader hook.
        mayutils.interfaces.filetypes.parquet.Parquet : Example implementer.
        pathlib.Path : Path abstraction for the on-disk file.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.parquet import Parquet
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "out.parquet"
        ...     handle = Parquet(p)
        ...     handle._write(pd.DataFrame({"id": [1]}), dataframe_backend="pandas")
        ...     p.exists()
        True
        """

    @abstractmethod
    def schema(
        self,
    ) -> dict[str, object]:
        """
        Return the column-name-to-dtype mapping declared by the file.

        Subclasses should read metadata cheaply where the format
        allows (parquet footer, feather IPC header, xlsx dimensions);
        when the format exposes no schema separately from the body
        (CSV), a small header sample is acceptable with documented
        heuristics. The returned mapping is used by :meth:`columns`
        and :meth:`dtypes` so callers never have to touch the format
        metadata directly.

        Returns
        -------
            Column name to dtype mapping; dtype values are
            format-specific (numpy dtype objects, polars type
            instances, or their string representations).

        See Also
        --------
        DataFile.columns : Column-name-only wrapper.
        DataFile.dtypes : Full-mapping alias.
        mayutils.interfaces.filetypes.parquet.Parquet : Example implementer.
        pathlib.Path : Path abstraction for the on-disk file.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.parquet import Parquet
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "events.parquet"
        ...     pd.DataFrame({"id": [1, 2]}).to_parquet(p)
        ...     handle = Parquet(p)
        ...     list(handle.schema())
        ['id']
        """

    @abstractmethod
    def row_count(
        self,
    ) -> int:
        """
        Return the number of data rows in the file (excluding headers).

        Subclasses should prefer metadata reads over body scans when
        the format supports it; streaming counts are acceptable
        fallbacks. This exists so callers can gate conversions,
        log sizes, or decide between :meth:`read` and :meth:`iter_chunks`
        without paying to materialise the whole file into memory.

        Returns
        -------
            Non-negative number of rows.

        See Also
        --------
        DataFile.size : Byte-level counterpart.
        DataFile.iter_chunks : Streaming alternative to full reads.
        mayutils.interfaces.filetypes.parquet.Parquet : Example implementer.
        pathlib.Path : Path abstraction for the on-disk file.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.parquet import Parquet
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "events.parquet"
        ...     pd.DataFrame({"a": [1, 2, 3]}).to_parquet(p)
        ...     handle = Parquet(p)
        ...     handle.row_count()
        3
        """

    @abstractmethod
    def iter_chunks(
        self,
        chunk_size: int,
        /,
        *,
        dataframe_backend: DataframeBackends | None = None,
        **kwargs: object,
    ) -> Iterator[DataFrames]:
        """
        Stream the file as an iterator of DataFrame chunks.

        Gives callers a memory-bounded alternative to :meth:`read` for
        files larger than RAM. Implementations may yield a smaller
        final chunk and are free to use whichever chunking primitive
        the underlying library provides (``pyarrow`` record batches,
        ``polars`` streaming chunks, pandas ``chunksize`` iteration).

        Parameters
        ----------
        chunk_size
            Upper bound on the number of rows per yielded DataFrame.
            Implementations may yield a smaller final chunk.
        dataframe_backend
            DataFrame library for each yielded chunk; defaults to
            :attr:`backend`.
        **kwargs
            Format-specific options forwarded verbatim.

        Yields
        ------
            Successive chunks whose concatenation equals
            :meth:`read`.

        See Also
        --------
        DataFile.read : Full-materialisation counterpart.
        DataFile.row_count : Size hint for sizing ``chunk_size``.
        mayutils.interfaces.filetypes.parquet.Parquet : Example implementer.
        pathlib.Path : Path abstraction for the on-disk file.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.parquet import Parquet
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "events.parquet"
        ...     pd.DataFrame({"a": [1, 2, 3, 4]}).to_parquet(p)
        ...     handle = Parquet(p)
        ...     total = sum(len(chunk) for chunk in handle.iter_chunks(2))
        ...     total
        4
        """


__all__ = [
    "DataFile",
]
