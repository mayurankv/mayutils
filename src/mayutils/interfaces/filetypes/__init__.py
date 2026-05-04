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
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Self, cast

import pandas as pd
import polars as pl

from mayutils.objects.classes import readonlyclassonlyproperty
from mayutils.objects.dataframes.backends import Backend, DataFrames

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


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


class DataFile[DataFrameType: DataFrames = pd.DataFrame](ABC):
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
        :attr:`backend`.

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
    _registry: ClassVar[dict[str, type[DataFile[Any]]]] = {}

    @readonlyclassonlyproperty
    def registry(
        cls,
    ) -> dict[str, type[DataFile[Any]]]:
        """
        Return the suffix-indexed registry of DataFile subclasses.

        Looks up the internal ``_registry`` class variable that maps
        file-extension strings to their concrete subclass types.

        Returns
        -------
            Mapping from file suffix to concrete ``DataFile`` subclass.

        See Also
        --------
        DataFile.__init_subclass__ : Populates the registry on import.
        DataFile.from_path : Consumer of the registry.
        mayutils.interfaces.filetypes.csv.Csv : Example registrant.
        pathlib.Path.suffix : Source of the registry key.

        Examples
        --------
        >>> from mayutils.environment.memoisation import register_datafile
        >>> from mayutils.interfaces.filetypes import DataFile
        >>> register_datafile("csv")
        >>> ".csv" in DataFile.registry
        True
        """
        return cls._registry

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
        backend: Backend[DataFrameType] | None = None,
    ) -> None:
        """
        Bind the handle to ``path`` and capture the default backend.

        Resolves the supplied path to a :class:`~pathlib.Path`, stores
        the backend token, and validates the suffix against the class.

        Parameters
        ----------
        path
            Filesystem location of the target file.
        backend
            Backend token for reads and writes. Defaults to :data:`PANDAS`.

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
        >>> handle.backend is PANDAS
        True
        """
        self.path = Path(path)
        self.backend = backend if backend is not None else cast("Backend[DataFrameType]", Backend(pd.DataFrame))

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
        return f"{type(self).__name__}({self.path!s}, backend={self.backend.name!r})"

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
            html: str = preview._repr_html_()  # pyright: ignore[reportUnknownVariableType, reportPrivateUsage, reportCallIssue]
        except PREVIEW_ERRORS:
            return header
        if not html:
            return header

        return f"{header}<br/>{html}"

    @classmethod
    def from_path[AltDataFrameType: DataFrames = pd.DataFrame](
        cls,
        path: Path | str,
        /,
        *,
        backend: Backend[AltDataFrameType] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> DataFile[AltDataFrameType]:
        """
        Dispatch to the registered subclass whose suffix matches ``path``.

        Looks up the path's suffix in :attr:`registry` and delegates
        construction to the matching concrete subclass.

        Parameters
        ----------
        path
            Filesystem location whose suffix selects the concrete
            subclass from :attr:`registry`.
        backend
            DataFrame backend token forwarded to the subclass
            constructor. Defaults to :data:`PANDAS`.
        **kwargs
            Extra keyword arguments forwarded to the subclass
            constructor (for example ``sheet`` for XLSX handles).

        Returns
        -------
            A concrete :class:`DataFile` instance bound to ``path``.

        Raises
        ------
        ValueError
            If no subclass is registered for the suffix of ``path``.

        See Also
        --------
        DataFile.__init_subclass__ : Populates the registry.
        DataFile.__init__ : Instance-level constructor.
        pathlib.Path.suffix : Source of the dispatch key.

        Examples
        --------
        >>> from pathlib import Path
        >>> from mayutils.environment.memoisation import register_datafile
        >>> from mayutils.interfaces.filetypes import DataFile
        >>> register_datafile("csv")
        >>> handle = DataFile.from_path(Path("events.csv"))
        >>> type(handle).__name__
        'Csv'
        """
        path = Path(path)
        key = path.suffix.lower()
        if key not in DataFile._registry:
            known = ", ".join(sorted(DataFile._registry)) or "<none>"
            msg = f"No DataFile subclass registered for suffix '{key}'. Known suffixes: {known}."
            raise ValueError(msg)

        return DataFile._registry[key](
            path,
            backend=backend if backend is not None else cast("Backend[AltDataFrameType]", Backend(pd.DataFrame)),
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
        target_cls: type[DataFile[DataFrameType]],
        /,
        *,
        path: Path | str,
        read_kwargs: Mapping[str, Any] | None = None,
        write_kwargs: Mapping[str, Any] | None = None,
        **init_kwargs: object,
    ) -> DataFile[DataFrameType]:
        """
        Read this file and write its contents to a new file of a different format.

        Materialises the current file via :meth:`read`, then persists the
        resulting DataFrame through the target subclass's :meth:`write`.

        Parameters
        ----------
        target_cls
            Concrete :class:`DataFile` subclass that handles the
            destination format.
        path
            Filesystem location for the converted output file.
        read_kwargs
            Extra keyword arguments forwarded to :meth:`read`.
        write_kwargs
            Extra keyword arguments forwarded to the target's
            :meth:`write`.
        **init_kwargs
            Extra keyword arguments forwarded to the ``target_cls``
            constructor (for example ``sheet`` for XLSX handles).

        Returns
        -------
            Handle to the newly written file.

        See Also
        --------
        DataFile.to_parquet : Parquet-specific shortcut.
        DataFile.to_csv : CSV-specific shortcut.
        DataFile.to_feather : Feather-specific shortcut.
        DataFile.to_xlsx : XLSX-specific shortcut.

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
        ...     out = handle.convert_to(Parquet, path=dst)
        ...     out.path.exists()
        True
        """
        df = self.read(**(dict(read_kwargs) if read_kwargs else {}))

        target = target_cls(
            path,
            backend=self.backend,
            **init_kwargs,
        )

        target.write(
            df,
            **(dict(write_kwargs) if write_kwargs else {}),
        )

        return target  # ty:ignore[invalid-return-type]

    def to_parquet(
        self,
        path: Path | str,
        /,
        *,
        read_kwargs: Mapping[str, Any] | None = None,
        write_kwargs: Mapping[str, Any] | None = None,
    ) -> DataFile[DataFrameType]:
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
            read_kwargs=read_kwargs,
            write_kwargs=write_kwargs,
        )

    def to_csv(
        self,
        path: Path | str,
        /,
        *,
        read_kwargs: Mapping[str, Any] | None = None,
        write_kwargs: Mapping[str, Any] | None = None,
    ) -> DataFile[DataFrameType]:
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
            read_kwargs=read_kwargs,
            write_kwargs=write_kwargs,
        )

    def to_feather(
        self,
        path: Path | str,
        /,
        *,
        read_kwargs: Mapping[str, Any] | None = None,
        write_kwargs: Mapping[str, Any] | None = None,
    ) -> DataFile[DataFrameType]:
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
            read_kwargs=read_kwargs,
            write_kwargs=write_kwargs,
        )

    def to_xlsx(
        self,
        path: Path | str,
        /,
        *,
        sheet: str = "Sheet1",
        read_kwargs: Mapping[str, Any] | None = None,
        write_kwargs: Mapping[str, Any] | None = None,
    ) -> DataFile[DataFrameType]:
        """
        Round-trip the file's contents into a new XLSX sheet.

        Shortcut for :meth:`convert_to` with the XLSX sheet subclass
        lazily imported so the base module stays importable without
        the XLSX extras installed. The ``sheet`` argument names the
        worksheet inside the workbook; any XLSX-specific options
        (engine, freeze panes) go through ``write_kwargs``.

        Parameters
        ----------
        path
            Destination XLSX path.
        sheet
            Name of the worksheet to write into.
        read_kwargs
            Extra keyword arguments forwarded to :meth:`read`.
        write_kwargs
            Extra keyword arguments forwarded to the XLSX writer.

        Returns
        -------
            Handle to the newly written XLSX file.

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
        ...     out = handle.to_xlsx(dst)
        ...     out.path.exists()
        True
        """
        from mayutils.interfaces.filetypes.xlsx import XlsxSheet  # noqa: PLC0415

        return self.convert_to(
            XlsxSheet,
            path=path,
            read_kwargs=read_kwargs,
            write_kwargs=write_kwargs,
            sheet=sheet,
        )

    @abstractmethod
    def read(
        self,
        **kwargs: Any,  # noqa: ANN401
    ) -> DataFrameType:
        """
        Read the file into a DataFrame.

        Subclasses implement the format-specific deserialization logic
        and return the contents using the configured backend.

        Parameters
        ----------
        **kwargs
            Format-specific options forwarded to the underlying reader.

        Returns
        -------
            The file contents as a DataFrame of the configured backend.

        See Also
        --------
        DataFile.write : Inverse operation.
        DataFile.iter_chunks : Streaming alternative.
        DataFile.to_pandas : Read specifically as pandas.
        DataFile.to_polars : Read specifically as polars.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "demo.csv"
        ...     pd.DataFrame({"a": [1]}).to_csv(p, index=False)
        ...     handle = Csv(p)
        ...     len(handle.read())
        1
        """
        ...

    def with_backend[AltDataFrameType: DataFrames](
        self,
        backend: Backend[AltDataFrameType],
        /,
    ) -> DataFile[AltDataFrameType]:
        """
        Return a copy of this handle bound to a different backend.

        Deep-copies the current instance and replaces its backend token
        so reads and writes dispatch through the alternate library.

        Parameters
        ----------
        backend
            Backend token to apply to the returned copy.

        Returns
        -------
            A deep copy of this handle with *backend* applied.

        See Also
        --------
        DataFile.to_pandas : Shortcut that switches to pandas.
        DataFile.to_polars : Shortcut that switches to polars.
        mayutils.objects.dataframes.backends.Backend : Backend token class.
        pathlib.Path : Path abstraction preserved in the copy.

        Examples
        --------
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> from mayutils.objects.dataframes.backends import Backend
        >>> import polars as pl
        >>> handle = Csv(Path("demo.csv"))
        >>> new = handle.with_backend(Backend(pl.DataFrame))
        >>> new.backend.name
        'polars'
        """
        new_instance = deepcopy(self)
        new_instance.backend = backend

        return cast("DataFile[AltDataFrameType]", new_instance)

    def to_pandas(
        self,
        **kwargs: Any,  # noqa: ANN401
    ) -> pd.DataFrame:
        """
        Read the file as a pandas DataFrame.

        Convenience wrapper that switches the backend to pandas before
        delegating to :meth:`read`.

        Parameters
        ----------
        **kwargs
            Format-specific options forwarded to the underlying reader.

        Returns
        -------
            The file contents as a :class:`pandas.DataFrame`.

        See Also
        --------
        DataFile.to_polars : Polars counterpart.
        DataFile.read : Backend-aware read.
        DataFile.with_backend : General backend switching.
        pandas.DataFrame : Returned type.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "demo.csv"
        ...     pd.DataFrame({"a": [1]}).to_csv(p, index=False)
        ...     handle = Csv(p)
        ...     isinstance(handle.to_pandas(), pd.DataFrame)
        True
        """
        return self.with_backend(Backend(pd.DataFrame)).read(**kwargs)

    def to_polars(
        self,
        **kwargs: Any,  # noqa: ANN401
    ) -> pl.DataFrame:
        """
        Read the file as a polars DataFrame.

        Convenience wrapper that switches the backend to polars before
        delegating to :meth:`read`.

        Parameters
        ----------
        **kwargs
            Format-specific options forwarded to the underlying reader.

        Returns
        -------
            The file contents as a :class:`polars.DataFrame`.

        See Also
        --------
        DataFile.to_pandas : Pandas counterpart.
        DataFile.read : Backend-aware read.
        DataFile.with_backend : General backend switching.
        polars.DataFrame : Returned type.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> import polars as pl
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "demo.csv"
        ...     pd.DataFrame({"a": [1]}).to_csv(p, index=False)
        ...     handle = Csv(p)
        ...     isinstance(handle.to_polars(), pl.DataFrame)
        True
        """
        return self.with_backend(Backend(pl.DataFrame)).read(**kwargs)

    @abstractmethod
    def write(
        self,
        df: DataFrameType,
        /,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """
        Write *df* to the file.

        Subclasses implement the format-specific serialization logic
        and persist the DataFrame to :attr:`path`.

        Parameters
        ----------
        df
            DataFrame to serialize and write to disk.
        **kwargs
            Format-specific options forwarded to the underlying writer.

        Returns
        -------
            ``self``, allowing fluent method chaining.

        See Also
        --------
        DataFile.read : Inverse operation.
        DataFile.convert_to : Read-then-write across formats.
        mayutils.interfaces.filetypes.csv.Csv : Concrete implementer.
        mayutils.interfaces.filetypes.parquet.Parquet : Concrete implementer.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.csv import Csv
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "out.csv"
        ...     handle = Csv(p)
        ...     result = handle.write(pd.DataFrame({"a": [1]}))
        ...     result.path.exists()
        True
        """
        ...

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
        **kwargs: object,
    ) -> Iterator[DataFrameType]:
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
