"""
Provide defensive text-file reading helpers.

This submodule holds the small wrappers around
:meth:`pathlib.Path.read_text` used by ``mayutils`` when loading
configuration, template, or notebook source files. The helpers
validate that the target path is an existing regular file before
reading so callers get an actionable :class:`ValueError` instead of
a bare :class:`FileNotFoundError` (or, worse, a permission error
from trying to open a directory).

See Also
--------
mayutils.environment.filesystem.roots : Helpers that resolve the
    directories text files are typically loaded from.
pathlib.Path.read_text : Underlying stdlib primitive used to perform
    the actual read.
mayutils.data.queries.read_query : Domain-specific caller that
    relies on :func:`read_file` for loading SQL templates.

Examples
--------
>>> import tempfile
>>> from pathlib import Path
>>> from mayutils.environment.filesystem.reading import read_file
>>> with tempfile.TemporaryDirectory() as tmp:
...     p = Path(tmp) / "x.txt"
...     _ = p.write_text("hello", encoding="utf-8")
...     read_file(p)
'hello'
"""

from pathlib import Path


def read_file(
    path: Path | str,
    /,
) -> str:
    """
    Read the full text contents of a file.

    The input is coerced to :class:`~pathlib.Path` and checked to
    refer to an existing regular file before reading. Decoding uses
    the default platform text encoding via
    :meth:`pathlib.Path.read_text`, meaning callers are responsible
    for ensuring the file is encoded compatibly with the locale. The
    whole file is eagerly loaded into memory, so this helper is best
    suited to configuration, template, or notebook source files rather
    than arbitrarily large blobs.

    Parameters
    ----------
    path
        Filesystem location of the file whose contents should be read.
        Accepted as either a :class:`~pathlib.Path` or a string and
        passed positionally only.

    Returns
    -------
        Decoded text contents of the file.

    Raises
    ------
    ValueError
        If ``path`` does not resolve to an existing regular file (for
        example, because it is missing, a directory, or another
        non-file entry).

    See Also
    --------
    pathlib.Path.read_text : Underlying method used to perform the
        read, which governs encoding and error-handling semantics.
    pathlib.Path.is_file : Predicate used to confirm that ``path``
        refers to a regular file before reading.
    shutil.copyfile : Companion ``shutil`` helper for binary file
        movement when byte-for-byte copying rather than text reading
        is required.

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> from mayutils.environment.filesystem import read_file
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     p = Path(tmp) / "x.txt"
    ...     _ = p.write_text("hello", encoding="utf-8")
    ...     read_file(p)
    'hello'
    """
    path = Path(path)
    if path.is_file():
        return path.read_text()

    msg = f"File {path} could not be found"
    raise ValueError(msg)


__all__ = [
    "read_file",
]
