"""Filesystem and repository-aware path utilities.

This module collects small helpers for locating paths on disk in a way
that is aware of the surrounding git repository and of the calling
Python module. It also provides a lightweight URL-safe codec for
serialising filesystem paths as single filename components and a
defensive text-file reader. The git-related helpers import
``gitpython`` lazily so the rest of the module is usable even when the
``filesystem`` optional dependency group is not installed.
"""

import inspect
import urllib.parse
from pathlib import Path


def get_root() -> Path:
    """Resolve the root directory of the enclosing git repository.

    The current working directory is walked upwards until a ``.git``
    directory is found, and the working tree of that repository is
    returned. When ``gitpython`` is not installed, or the current
    working directory is not part of any git repository, the function
    falls back to the current working directory. This makes it safe to
    call from scripts that may or may not be run from inside a
    checkout.

    Returns
    -------
    Path
        Working-tree root of the repository that contains the current
        working directory, or the current working directory itself
        when no repository is detected or ``gitpython`` is unavailable.
    """
    try:
        from git import InvalidGitRepositoryError, Repo  # noqa: PLC0415
    except ImportError:
        return Path.cwd()

    try:
        return Path(
            Repo(
                path=".",
                search_parent_directories=True,
            ).working_dir
        )
    except InvalidGitRepositoryError:
        return Path.cwd()


def get_module_root() -> Path:
    """Resolve the directory of the module that invoked this function.

    The caller's frame is introspected to determine the source file of
    the module issuing the call, and the directory containing that
    file is returned. When the calling context is not associated with
    a source file (for example, an interactive REPL or an
    eval-generated frame), the repository root returned by
    :func:`get_root` is used instead.

    Returns
    -------
    Path
        Directory containing the source file of the caller, or the
        repository root when no caller source file can be determined.
    """
    defining_module = inspect.getmodule(inspect.currentframe())
    return Path(defining_module.__file__).parent if defining_module is not None and defining_module.__file__ is not None else get_root()


def get_module_path(
    module: object,
    /,
) -> Path:
    """Return the filesystem directory backing a package module.

    The first entry of the module's ``__path__`` attribute is
    returned. This attribute is populated by the Python import machinery
    for package modules, so this helper is intended for packages rather
    than plain modules.

    Parameters
    ----------
    module : object
        Imported module (typically a package) whose on-disk location
        should be resolved. Must expose a non-empty ``__path__``
        attribute.

    Returns
    -------
    Path
        Directory from which ``module`` was loaded.

    Raises
    ------
    ValueError
        If ``module`` has no ``__path__`` attribute, indicating it is
        not a package, or if ``__path__`` is present but empty and so
        does not point at any directory.
    """
    paths = getattr(module, "__path__", None)
    if paths is None:
        msg = f"Module {module} does not have a __path__ attribute."
        raise ValueError(msg)

    try:
        return Path(paths[0])
    except IndexError as err:
        msg = f"Module {module} does not have a valid path."
        raise ValueError(msg) from err


def read_file(
    path: Path | str,
    /,
) -> str:
    """Read the full text contents of a file.

    The input is coerced to :class:`~pathlib.Path` and checked to refer
    to an existing regular file before reading. Decoding uses the
    default platform text encoding via :meth:`Path.read_text`.

    Parameters
    ----------
    path : Path or str
        Filesystem location of the file whose contents should be read.
        Accepted as either a :class:`~pathlib.Path` or a string and
        passed positionally only.

    Returns
    -------
    str
        Decoded text contents of the file.

    Raises
    ------
    ValueError
        If ``path`` does not resolve to an existing regular file (for
        example, because it is missing, a directory, or another
        non-file entry).
    """
    path = Path(path)
    if path.is_file():
        return path.read_text()

    msg = f"File {path} could not be found"
    raise ValueError(msg)


def encode_path(
    path: Path | str,
    /,
) -> str:
    """Encode a filesystem path as a single URL-safe filename component.

    Forward slashes in the string representation of ``path`` are first
    replaced with ``#`` so that hierarchical path structure survives
    URL quoting without introducing ``/`` characters into the result.
    The rewritten string is then passed through
    :func:`urllib.parse.quote`, yielding a representation suitable for
    use as an individual filename on filesystems that forbid ``/``.

    Parameters
    ----------
    path : Path or str
        Source path to be flattened into a single filename-safe token.

    Returns
    -------
    str
        URL-encoded representation in which path separators have been
        remapped to ``#`` before quoting, producing an opaque
        round-trippable token.
    """
    return urllib.parse.quote(string=str(path).replace("/", "#"))


def decode_path(
    encoded_path: str,
    /,
) -> Path:
    """Decode a token produced by :func:`encode_path` back into a path.

    The input is URL-unquoted and every ``#`` is mapped back to ``/``,
    reversing the substitution applied during encoding. This is the
    exact inverse of :func:`encode_path` for inputs produced by that
    function.

    Parameters
    ----------
    encoded_path : str
        Token previously produced by :func:`encode_path` that should be
        restored to its original path form.

    Returns
    -------
    Path
        Reconstructed filesystem path corresponding to the original
        value that was passed to :func:`encode_path`.
    """
    return Path(urllib.parse.unquote(string=encoded_path).replace("#", "/"))
