"""
Provide a file-backed cache backend with pluggable serialisation.

Supports DataFile formats (parquet, csv, feather, xlsx), pickle, and
numpy (.npy/.npz) through a :class:`Serialiser` protocol. The
:class:`FileStore` class wraps path resolution, staleness checks, and
hit/miss tracking, with optional suffix inference from the cached object.

See Also
--------
mayutils.environment.memoisation.memory : In-memory cache backend.
mayutils.environment.memoisation.decorators : Unified ``cache``
    decorator.
mayutils.interfaces.filetypes.DataFile : Registry backing tabular
    formats.
"""

from __future__ import annotations

import contextlib
import importlib
import pickle
from collections.abc import Mapping
from functools import _CacheInfo as CacheInfo  # pyright: ignore[reportPrivateUsage]
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast, runtime_checkable

import polars as pl
from pandas import DataFrame

from mayutils.core.extras import may_require_extras
from mayutils.data import CACHE_FOLDER
from mayutils.environment.filesystem import is_file_stale
from mayutils.environment.memoisation.types import MISSING, CacheObjects, Missing
from mayutils.environment.memoisation.utilities import format_ttl
from mayutils.interfaces.filetypes import DataFile
from mayutils.objects.dataframes.backends import Backend, DataFrames, default_backend
from mayutils.objects.dictionaries import flatten_dict
from mayutils.objects.strings import String

with may_require_extras():
    import numpy as np
    import pandas as pd
    import polars as pl

if TYPE_CHECKING:
    from numpy.typing import ArrayLike

    from mayutils.objects.datetime import Duration
    from mayutils.objects.types import SQL


@runtime_checkable
class Serialiser[CacheObjectType: CacheObjects](Protocol):
    """
    Read/write arbitrary objects to a file path.

    Concrete implementations handle a specific file format such as
    pickle, numpy, or DataFile-backed tabular formats.

    See Also
    --------
    DataFileSerialiser : Serialiser for DataFile-backed formats.
    PickleSerialiser : Serialiser for pickle files.

    Examples
    --------
    >>> from mayutils.environment.memoisation.files import Serialiser, PickleSerialiser
    >>> isinstance(PickleSerialiser(), Serialiser)
    True
    """

    def read(
        self,
        path: Path,
        /,
    ) -> CacheObjectType:
        """
        Read a cached object from *path*.

        Deserialises the file at *path* using the format specific to
        the concrete serialiser.

        Parameters
        ----------
        path
            File to read from.

        See Also
        --------
        Serialiser.write : Inverse operation.

        Examples
        --------
        >>> from mayutils.environment.memoisation.files import PickleSerialiser
        >>> s = PickleSerialiser()
        >>> hasattr(s, "read")
        True
        """
        ...

    def write(
        self,
        path: Path,
        /,
        *,
        obj: CacheObjectType,
    ) -> None:
        """
        Write *obj* to *path*.

        Serialises *obj* to disk using the format specific to the
        concrete serialiser.

        Parameters
        ----------
        path
            Destination file path.
        obj
            Object to persist.

        See Also
        --------
        Serialiser.read : Inverse operation.

        Examples
        --------
        >>> from mayutils.environment.memoisation.files import PickleSerialiser
        >>> s = PickleSerialiser()
        >>> hasattr(s, "write")
        True
        """
        ...


class DataFileSerialiser[DataFrameType: DataFrames = pd.DataFrame]:
    """
    Serialiser for DataFile-backed formats (parquet, csv, feather, xlsx).

    Delegates read/write to the :class:`DataFile` registry, selecting the
    correct handler from the file extension.

    Parameters
    ----------
    backend
        DataFrame backend token controlling the output type.

    See Also
    --------
    Serialiser : Protocol this class satisfies.
    PickleSerialiser : Fallback serialiser for arbitrary objects.

    Examples
    --------
    >>> from mayutils.environment.memoisation.files import DataFileSerialiser
    >>> s = DataFileSerialiser()
    >>> hasattr(s, "read")
    True
    """

    backend: Backend[DataFrameType]

    def __init__(
        self,
        *,
        backend: Backend[DataFrameType] | None = None,
    ) -> None:
        """
        Initialise the serialiser with an optional backend token.

        Falls back to a pandas backend when *backend* is not supplied.

        Parameters
        ----------
        backend
            DataFrame backend token controlling the output type.

        See Also
        --------
        mayutils.objects.dataframes.backends.Backend : Backend token type.

        Examples
        --------
        >>> from mayutils.environment.memoisation.files import DataFileSerialiser
        >>> DataFileSerialiser().backend is not None
        True
        """
        self.backend = backend if backend is not None else cast("Backend[DataFrameType]", default_backend())

    def get_datafile(
        self,
        path: Path,
        /,
    ) -> DataFile[DataFrameType]:
        """
        Return the DataFile handle for *path*.

        Resolves the correct :class:`DataFile` subclass from the file
        extension and attaches the configured backend.

        Parameters
        ----------
        path
            File whose extension selects the DataFile subclass.

        Returns
        -------
            The resolved DataFile instance.

        See Also
        --------
        mayutils.interfaces.filetypes.DataFile.from_path : Factory used
            internally.

        Examples
        --------
        >>> from pathlib import Path
        >>> from mayutils.environment.memoisation.files import (
        ...     DataFileSerialiser,
        ...     register_datafile,
        ... )
        >>> register_datafile("parquet")
        >>> s = DataFileSerialiser()
        >>> df = s.get_datafile(Path("data.parquet"))
        >>> type(df).__name__
        'Parquet'
        """
        return DataFile.from_path(path, backend=self.backend)

    def read(
        self,
        path: Path,
        /,
    ) -> DataFrameType:
        """
        Read a DataFrame from *path*.

        Delegates to :meth:`get_datafile` to resolve the correct
        DataFile handler and then calls its ``read`` method.

        Parameters
        ----------
        path
            File to read a DataFrame from.

        Returns
        -------
            The DataFrame read from the file.

        See Also
        --------
        DataFileSerialiser.write : Inverse operation.

        Examples
        --------
        >>> from mayutils.environment.memoisation.files import DataFileSerialiser
        >>> s = DataFileSerialiser()
        >>> hasattr(s, "read")
        True
        """
        return self.get_datafile(path).read()

    def write(
        self,
        path: Path,
        /,
        *,
        obj: DataFrameType,
    ) -> None:
        """
        Write a DataFrame to *path*.

        Delegates to :meth:`get_datafile` to resolve the correct
        DataFile handler and then calls its ``write`` method.

        Parameters
        ----------
        path
            Destination file path.
        obj
            DataFrame to persist.

        See Also
        --------
        DataFileSerialiser.read : Inverse operation.

        Examples
        --------
        >>> from mayutils.environment.memoisation.files import DataFileSerialiser
        >>> s = DataFileSerialiser()
        >>> hasattr(s, "write")
        True
        """
        self.get_datafile(path).write(obj)


class PickleSerialiser:
    """
    Serialiser for ``.pkl`` files.

    Uses Python's built-in :mod:`pickle` module for serialisation and
    deserialisation of arbitrary objects.

    See Also
    --------
    Serialiser : Protocol this class satisfies.
    DataFileSerialiser : Serialiser for tabular formats.

    Examples
    --------
    >>> from mayutils.environment.memoisation.files import PickleSerialiser
    >>> s = PickleSerialiser()
    >>> isinstance(s, PickleSerialiser)
    True
    """

    def read(
        self,
        path: Path,
        /,
    ) -> object:
        """
        Unpickle an object from *path*.

        Opens the file in binary mode and deserialises the contents
        using :func:`pickle.load`.

        Parameters
        ----------
        path
            File to read from.

        Returns
        -------
            The deserialized object.

        See Also
        --------
        PickleSerialiser.write : Inverse operation.

        Examples
        --------
        >>> from mayutils.environment.memoisation.files import PickleSerialiser
        >>> s = PickleSerialiser()
        >>> hasattr(s, "read")
        True
        """
        with path.open(mode="rb") as file_handler:
            return pickle.load(file=file_handler)  # noqa: S301

    def write(
        self,
        path: Path,
        /,
        *,
        obj: object,
    ) -> None:
        """
        Pickle *obj* to *path*.

        Opens the file in binary mode and serialises *obj* using
        :func:`pickle.dump`.

        Parameters
        ----------
        path
            Destination file path.
        obj
            Object to persist.

        See Also
        --------
        PickleSerialiser.read : Inverse operation.

        Examples
        --------
        >>> from mayutils.environment.memoisation.files import PickleSerialiser
        >>> s = PickleSerialiser()
        >>> hasattr(s, "write")
        True
        """
        with path.open(mode="wb") as file_handler:
            pickle.dump(obj=obj, file=file_handler)


class NumpySerialiser:
    """
    Serialiser for ``.npy`` files (single array).

    Uses :func:`numpy.load` and :func:`numpy.save` for persistence of
    individual arrays.

    See Also
    --------
    Serialiser : Protocol this class satisfies.
    NpzSerialiser : Variant for multiple arrays.

    Examples
    --------
    >>> from mayutils.environment.memoisation.files import NumpySerialiser
    >>> s = NumpySerialiser()
    >>> isinstance(s, NumpySerialiser)
    True
    """

    def read(
        self,
        path: Path,
        /,
    ) -> ArrayLike:
        """
        Load a single array from *path*.

        Delegates to :func:`numpy.load` to deserialise the ``.npy``
        file.

        Parameters
        ----------
        path
            File to read the array from.

        Returns
        -------
            The loaded array.

        See Also
        --------
        NumpySerialiser.write : Inverse operation.

        Examples
        --------
        >>> from mayutils.environment.memoisation.files import NumpySerialiser
        >>> s = NumpySerialiser()
        >>> hasattr(s, "read")
        True
        """
        return np.load(file=str(path))

    def write(
        self,
        path: Path,
        /,
        *,
        obj: ArrayLike,
    ) -> None:
        """
        Save *obj* as a ``.npy`` file at *path*.

        Delegates to :func:`numpy.save` to serialise the array to
        disk.

        Parameters
        ----------
        path
            Destination file path.
        obj
            Array to persist.

        See Also
        --------
        NumpySerialiser.read : Inverse operation.

        Examples
        --------
        >>> from mayutils.environment.memoisation.files import NumpySerialiser
        >>> s = NumpySerialiser()
        >>> hasattr(s, "write")
        True
        """
        np.save(
            file=str(path),
            allow_pickle=True,
            arr=obj,
        )


class NpzSerialiser:
    """
    Serialiser for ``.npz`` files (multiple arrays).

    Uses :func:`numpy.load` and :func:`numpy.savez` for persistence of
    named array collections.

    See Also
    --------
    Serialiser : Protocol this class satisfies.
    NumpySerialiser : Variant for a single array.

    Examples
    --------
    >>> from mayutils.environment.memoisation.files import NpzSerialiser
    >>> s = NpzSerialiser()
    >>> isinstance(s, NpzSerialiser)
    True
    """

    def read(
        self,
        path: Path,
        /,
    ) -> Mapping[str, ArrayLike]:
        """
        Load a mapping of arrays from *path*.

        Delegates to :func:`numpy.load` to deserialise the ``.npz``
        archive.

        Parameters
        ----------
        path
            File to read the array mapping from.

        Returns
        -------
            A mapping of array names to arrays.

        See Also
        --------
        NpzSerialiser.write : Inverse operation.

        Examples
        --------
        >>> from mayutils.environment.memoisation.files import NpzSerialiser
        >>> s = NpzSerialiser()
        >>> hasattr(s, "read")
        True
        """
        return np.load(file=str(path))

    def write(
        self,
        path: Path,
        /,
        *,
        obj: Mapping[str, ArrayLike],
    ) -> None:
        """
        Save *obj* as a ``.npz`` archive at *path*.

        Delegates to :func:`numpy.savez` to serialise the named array
        collection to disk.

        Parameters
        ----------
        path
            Destination file path.
        obj
            Mapping of array names to arrays.

        See Also
        --------
        NpzSerialiser.read : Inverse operation.

        Examples
        --------
        >>> from mayutils.environment.memoisation.files import NpzSerialiser
        >>> s = NpzSerialiser()
        >>> hasattr(s, "write")
        True
        """
        np.savez(
            file=str(path),
            allow_pickle=True,
            **obj,
        )


SERIALISER_MAP: dict[str, type[Serialiser[Any]]] = {
    ".pkl": PickleSerialiser,
    ".npy": NumpySerialiser,
    ".npz": NpzSerialiser,
}


def register_datafile(
    suffix: str,
    /,
) -> None:
    """
    Ensure the :class:`DataFile` subclass matching *suffix* is loaded.

    Attempts to import the corresponding ``mayutils.interfaces.filetypes``
    module so its subclass is registered.

    Parameters
    ----------
    suffix
        File extension, with or without leading ``"."``.

    See Also
    --------
    get_serialiser : Uses this to ensure the format is available.

    Examples
    --------
    >>> from mayutils.environment.memoisation.files import register_datafile
    >>> register_datafile("parquet")
    """
    key = suffix.lstrip(".").lower()

    if f".{key}" in DataFile.registry:
        return

    with contextlib.suppress(ImportError):
        importlib.import_module(name=f"mayutils.interfaces.filetypes.{key}")


def get_serialiser[DataFrameType: DataFrames = pd.DataFrame](
    suffix: str,
    /,
    *,
    backend: Backend[DataFrameType] | None = None,
) -> Serialiser[Any]:
    """
    Resolve the right serialiser for *suffix*.

    Falls back to :class:`DataFileSerialiser` when *suffix* is not one
    of the built-in non-tabular formats.

    Parameters
    ----------
    suffix
        File extension (e.g. ``"parquet"``, ``".pkl"``, ``".npy"``).
    backend
        Backend token passed to :class:`DataFileSerialiser`.

    Returns
    -------
        The serialiser instance for the given suffix.

    See Also
    --------
    register_datafile : Ensures the format module is loaded.
    infer_suffix : Determines the suffix from an object's type.

    Examples
    --------
    >>> from mayutils.environment.memoisation.files import get_serialiser
    >>> isinstance(get_serialiser(".pkl"), Serialiser)
    True
    """
    normalised = suffix if suffix.startswith(".") else f".{suffix}"

    cls = SERIALISER_MAP.get(normalised)
    if cls is not None:
        return cls()

    register_datafile(normalised)

    backend = backend if backend is not None else cast("Backend[DataFrameType]", default_backend())

    return DataFileSerialiser(backend=backend)


def infer_suffix(
    obj: CacheObjects,
    /,
) -> str:
    """
    Infer a file suffix from an object's type.

    Maps DataFrames to parquet, ndarrays to npy, dict-of-arrays to npz,
    and everything else to pickle.

    Parameters
    ----------
    obj
        The object to inspect.

    Returns
    -------
    str
        ``".parquet"`` for DataFrames, ``".npy"`` for ndarrays,
        ``".npz"`` for dicts of arrays, ``".pkl"`` otherwise.

    See Also
    --------
    get_serialiser : Resolves a serialiser from the inferred suffix.

    Examples
    --------
    >>> infer_suffix({"a": 1})
    '.pkl'
    """
    try:
        if isinstance(obj, DataFrame):
            return ".parquet"
    except ImportError:
        pass

    try:
        if isinstance(obj, pl.DataFrame):
            return ".parquet"
    except ImportError:
        pass

    if isinstance(obj, np.ndarray):
        return ".npy"

    if isinstance(obj, Mapping):
        mapping = cast("Mapping[object, object]", obj)
        if all(isinstance(value, np.ndarray) for value in mapping.values()):
            return ".npz"

    return ".pkl"


def make_cache_stem(
    query: SQL | Path,
    /,
    *,
    cache_description: str | None,
    ttl: Duration | None,
    format_kwargs: Mapping[str, object],
    cache_extra: Mapping[str, object] | None,
    key: str,
) -> str:
    """
    Build a human-readable, parsable filename stem for a cache entry.

    Format: ``{description}--{kwargs}--{extras}--ttl_{label}--{hash}``

    Each ``--`` section is independently parsable. The hash is the full
    digest to guarantee uniqueness.

    Parameters
    ----------
    query
        The original query argument (Path or SQL string).
    cache_description
        Explicit description overriding the auto-generated one.
    ttl
        Cache TTL, embedded in the filename when set.
    format_kwargs
        Template substitutions passed to the query.
    cache_extra
        Additional cache key values.
    key
        The hash digest for uniqueness.

    Returns
    -------
    str
        Filename stem like
        ``loans_by_region--region_london--ttl_6h--a3f8c1d2``.

    See Also
    --------
    FileStore : Uses this to construct file paths for cache entries.

    Examples
    --------
    >>> from mayutils.environment.memoisation.files import make_cache_stem
    >>> from mayutils.objects.types import SQL
    >>> make_cache_stem(
    ...     SQL("SELECT * FROM loans"),
    ...     cache_description=None,
    ...     ttl=None,
    ...     format_kwargs={},
    ...     cache_extra=None,
    ...     key="abc123",
    ... )
    'select_from--abc123'
    """
    sections: list[str] = []

    if cache_description is not None:
        sections.append(String.to_slug(cache_description))
    elif isinstance(query, Path):
        sections.append(String.to_slug(str(query.with_suffix(suffix=""))))
    else:
        sections.append(String.to_slug(" ".join(query.split()[:3])))

    if format_kwargs:
        sections.append(String.to_slug("_".join(flatten_dict(format_kwargs))))

    if cache_extra:
        sections.append(String.to_slug("_".join(flatten_dict(cache_extra))))

    if ttl is not None:
        sections.append(format_ttl(ttl))

    sections.append(key)

    return "--".join(sections)


class FileStore[CacheObjectType: CacheObjects]:
    """
    File-backed cache: one file per call signature under a function folder.

    When ``suffix`` is ``None`` (the default), the format is inferred
    from the first object written via :func:`infer_suffix`.

    Parameters
    ----------
    func_name
        Name used for the per-function subdirectory.
    cache_folder
        Root directory for cache files.
    suffix
        File extension selecting the serialisation format. ``None``
        defers to :func:`infer_suffix` on the first :meth:`put`.
    ttl
        Lifetime of each cached file (mtime-based).
    backend
        DataFrame backend token for DataFile-backed formats.

    See Also
    --------
    mayutils.environment.memoisation.memory : In-memory cache backend.
    mayutils.environment.memoisation.decorators : Unified ``cache``
        decorator.

    Examples
    --------
    >>> import tempfile
    >>> from mayutils.environment.memoisation.files import FileStore, MISSING
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     store = FileStore("test", cache_folder=tmp, suffix=".pkl")
    ...     store.get("k") is MISSING
    True
    """

    def __init__(
        self,
        func_name: str,
        /,
        *,
        cache_folder: Path | str = CACHE_FOLDER,
        suffix: str | None = None,
        ttl: Duration | None = None,
        backend: Backend[Any] | None = None,
    ) -> None:
        """
        Initialise the file store for a single cached function.

        Sets up the cache folder, normalises the suffix, and eagerly
        resolves the serialiser when the suffix is known up front.

        Parameters
        ----------
        func_name
            Name used for the per-function subdirectory.
        cache_folder
            Root directory for cache files.
        suffix
            File extension selecting the serialisation format.
        ttl
            Lifetime of each cached file (mtime-based).
        backend
            DataFrame backend token for DataFile-backed formats.

        See Also
        --------
        FileStore.resolve : Deferred resolution on first put.

        Examples
        --------
        >>> import tempfile
        >>> from mayutils.environment.memoisation.files import FileStore
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     store = FileStore("myfunc", cache_folder=tmp, suffix=".pkl")
        ...     store.func_name
        'myfunc'
        """
        self.func_name = func_name
        self.cache_folder = Path(cache_folder)
        self.ttl = ttl
        self.hits = 0
        self.misses = 0

        self.suffix = (suffix if suffix.startswith(".") else f".{suffix}") if suffix is not None else None

        if self.suffix is not None:
            register_datafile(self.suffix)

        self.backend: Backend[Any] | Literal[False] | None = backend if self.suffix is None or self.suffix in DataFile.registry else False

        self.serialiser: Serialiser[CacheObjectType] | None = (
            None
            if self.suffix is None or self.backend is None
            else get_serialiser(
                self.suffix,
                backend=self.backend if self.backend is not False else None,
            )
        )
        self._resolved = self.serialiser is not None

    def resolve(
        self,
        obj: CacheObjectType,
        /,
    ) -> None:
        """
        Infer suffix, backend and serialiser from *obj* on first put.

        Called automatically by :meth:`put` when the suffix was not
        provided at construction time.

        Parameters
        ----------
        obj
            The first cached object, used for type-based inference.

        See Also
        --------
        infer_suffix : Determines the suffix from the object type.

        Examples
        --------
        >>> import tempfile
        >>> from mayutils.environment.memoisation.files import FileStore
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     store = FileStore("test", cache_folder=tmp)
        ...     store.resolve({"key": "value"})
        ...     store.suffix
        '.pkl'
        """
        if self.suffix is None:
            self.suffix = infer_suffix(obj)
            register_datafile(self.suffix)

        if self.backend is None:
            self.backend = Backend.infer(cast("Any", obj)) if self.suffix in DataFile.registry else False

        self.serialiser = get_serialiser(
            self.suffix,
            backend=self.backend if self.backend is not False else None,
        )
        self._resolved = True

    @property
    def function_folder(
        self,
    ) -> Path:
        """
        Per-function subdirectory under ``cache_folder``.

        Computes the path by joining the root cache folder with the
        function name.

        Returns
        -------
            The per-function cache directory path.

        See Also
        --------
        FileStore.get_path : Full file path for a specific key.

        Examples
        --------
        >>> import tempfile
        >>> from mayutils.environment.memoisation.files import FileStore
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     store = FileStore("myfunc", cache_folder=tmp, suffix=".pkl")
        ...     store.function_folder.name
        'myfunc'
        """
        return self.cache_folder / self.func_name

    def get_path(
        self,
        key: str,
        /,
    ) -> Path:
        """
        Compute the cache file path for *key*.

        Joins the function folder with the key and the resolved
        suffix to produce the full file path.

        Parameters
        ----------
        key
            Cache key.

        Returns
        -------
            The resolved file path for *key*.

        Raises
        ------
        RuntimeError
            When the suffix has not been resolved yet (no prior
            ``put``).

        See Also
        --------
        FileStore.function_folder : Parent directory of the returned
            path.

        Examples
        --------
        >>> import tempfile
        >>> from mayutils.environment.memoisation.files import FileStore
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     store = FileStore("f", cache_folder=tmp, suffix=".pkl")
        ...     store.get_path("abc").name
        'abc.pkl'
        """
        if self.suffix is None:
            msg = "Suffix not resolved — call put() first or pass suffix= to __init__"
            raise RuntimeError(msg)

        return self.function_folder / f"{key}{self.suffix}"

    def get(
        self,
        key: str,
        /,
    ) -> CacheObjectType | Missing:
        """
        Read the cached value for *key*, returning :data:`MISSING` on miss.

        Checks file existence and staleness before reading the cached
        value through the resolved serialiser.

        Parameters
        ----------
        key
            Cache key.

        Returns
        -------
            The cached value, or :data:`MISSING` if absent or stale.

        Raises
        ------
        RuntimeError
            When the serialiser has not been resolved.

        See Also
        --------
        FileStore.put : Write a value into the cache.

        Examples
        --------
        >>> import tempfile
        >>> from mayutils.environment.memoisation.files import FileStore, MISSING
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     store = FileStore("test", cache_folder=tmp, suffix=".pkl")
        ...     store.get("k") is MISSING
        True
        """
        if not self._resolved:
            self.misses += 1
            return MISSING

        path = self.get_path(key)

        if path.is_file() and not is_file_stale(path, ttl=self.ttl):
            self.hits += 1
            if self.serialiser is None:
                msg = "Serialiser not resolved — call put() first or pass suffix= to __init__"
                raise RuntimeError(msg)

            return self.serialiser.read(path)

        self.misses += 1

        return MISSING

    def put(
        self,
        key: str,
        /,
        *,
        value: CacheObjectType,
    ) -> None:
        """
        Write *value* to the cache file for *key*.

        If ``suffix`` was not set at init time, it is inferred from
        *value* on the first call.

        Parameters
        ----------
        key
            Cache key.
        value
            Object to persist.

        Raises
        ------
        RuntimeError
            When the serialiser has not been resolved.

        See Also
        --------
        FileStore.get : Read the value back from the cache.

        Examples
        --------
        >>> import tempfile
        >>> from mayutils.environment.memoisation.files import FileStore
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     store = FileStore("test", cache_folder=tmp, suffix=".pkl")
        ...     store.put("k", value={"a": 1})
        ...     store.get("k")
        {'a': 1}
        """
        if not self._resolved:
            self.resolve(value)

        path = self.get_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.serialiser is None:
            msg = "Serialiser not resolved — call put() first or pass suffix= to __init__"
            raise RuntimeError(msg)

        self.serialiser.write(path, obj=value)

    def delete(
        self,
        key: str,
        /,
    ) -> bool:
        """
        Remove the cache file for *key*.

        Returns ``False`` without error when the serialiser has not
        been resolved or the file does not exist.

        Parameters
        ----------
        key
            Cache key.

        Returns
        -------
            ``True`` if the file was removed, ``False`` otherwise.

        See Also
        --------
        FileStore.clear : Remove all files for this function.

        Examples
        --------
        >>> import tempfile
        >>> from mayutils.environment.memoisation.files import FileStore
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     store = FileStore("test", cache_folder=tmp, suffix=".pkl")
        ...     store.delete("nonexistent")
        False
        """
        if not self._resolved:
            return False

        path = self.get_path(key)
        if path.is_file():
            path.unlink()

            return True

        return False

    def clear(
        self,
    ) -> None:
        """
        Remove all cache files for this function and reset counters.

        Globs the function folder for files matching the resolved
        suffix and deletes each one.

        See Also
        --------
        FileStore.delete : Remove a single cache entry.

        Examples
        --------
        >>> import tempfile
        >>> from mayutils.environment.memoisation.files import FileStore
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     store = FileStore("test", cache_folder=tmp, suffix=".pkl")
        ...     store.clear()
        ...     store.hits
        0
        """
        if self._resolved and self.function_folder.is_dir():
            for file in self.function_folder.glob(f"*{self.suffix}"):
                file.unlink()

        self.hits = 0
        self.misses = 0

    def cache_info(
        self,
    ) -> CacheInfo:
        """
        Return ``(hits, misses, maxsize, currsize)``.

        Counts files matching the resolved suffix in the function
        folder to compute *currsize*.

        Returns
        -------
            Named tuple with cache statistics.

        See Also
        --------
        FileStore.clear : Resets the hit/miss counters.

        Examples
        --------
        >>> import tempfile
        >>> from mayutils.environment.memoisation.files import FileStore
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     store = FileStore("test", cache_folder=tmp, suffix=".pkl")
        ...     info = store.cache_info()
        ...     info.hits
        0
        """
        currsize = 0
        if self._resolved and self.function_folder.is_dir():
            currsize = sum(1 for _ in self.function_folder.glob(f"*{self.suffix}"))
        return CacheInfo(
            hits=self.hits,
            misses=self.misses,
            maxsize=None,
            currsize=currsize,
        )


__all__ = [
    "DataFileSerialiser",
    "FileStore",
    "NpzSerialiser",
    "NumpySerialiser",
    "PickleSerialiser",
    "Serialiser",
    "get_serialiser",
    "infer_suffix",
    "make_cache_stem",
]
