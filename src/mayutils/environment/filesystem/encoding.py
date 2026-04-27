"""
Provide URL-safe serialisation helpers for filesystem paths.

This submodule pairs :func:`encode_path` and :func:`decode_path`,
which round-trip a :class:`~pathlib.Path` through a filename-safe
token. Path separators are remapped to ``#`` before URL quoting so
that hierarchical structure survives percent-encoding without
introducing ``/`` characters into the resulting string, producing
values suitable for use as individual filenames on filesystems that
forbid separators.

See Also
--------
urllib.parse.quote : Standard-library percent-encoding routine used
    to escape characters reserved by URLs.
urllib.parse.unquote : Standard-library percent-decoding routine
    used by the inverse helper.
mayutils.environment.filesystem.metadata : File metadata queries on
    the paths typically derived from these tokens.

Examples
--------
>>> from pathlib import Path
>>> from mayutils.environment.filesystem.encoding import encode_path, decode_path
>>> token = encode_path(Path("a/b/c.txt"))
>>> decode_path(token) == Path("a/b/c.txt")
True
"""

import urllib.parse
from pathlib import Path


def encode_path(
    path: Path | str,
    /,
) -> str:
    """
    Encode a filesystem path as a URL-safe filename component.

    Forward slashes in the string representation of ``path`` are
    first replaced with ``#`` so that hierarchical path structure
    survives URL quoting without introducing ``/`` characters into
    the result. The rewritten string is then passed through
    :func:`urllib.parse.quote`, yielding a representation suitable
    for use as an individual filename on filesystems that forbid
    ``/``. Symlinks are not resolved; the path is serialised as
    given, so callers wanting a canonicalised target should resolve
    the path before encoding.

    Parameters
    ----------
    path
        Source path to be flattened into a single filename-safe
        token. Passed positionally only.

    Returns
    -------
        URL-encoded representation in which path separators have
        been remapped to ``#`` before quoting, producing an opaque
        round-trippable token.

    See Also
    --------
    decode_path : Inverse helper that reconstructs the original
        :class:`~pathlib.Path` from the encoded token.
    urllib.parse.quote : Underlying percent-encoding routine used
        to escape characters reserved by URLs.
    pathlib.Path : Path abstraction accepted as input and produced
        by the inverse decoder.

    Examples
    --------
    >>> from pathlib import Path
    >>> from mayutils.environment.filesystem import encode_path
    >>> encode_path(Path("data/raw/file.csv"))
    'data%23raw%23file.csv'
    >>> encode_path("logs/2026-04-22.log")
    'logs%232026-04-22.log'
    """
    return urllib.parse.quote(string=str(path).replace("/", "#"))


def decode_path(
    encoded_path: str,
    /,
) -> Path:
    """
    Decode a token produced by :func:`encode_path` back into a path.

    The input is URL-unquoted and every ``#`` is mapped back to
    ``/``, reversing the substitution applied during encoding. This
    is the exact inverse of :func:`encode_path` for inputs produced
    by that function. The returned :class:`~pathlib.Path` is not
    resolved against the filesystem, so symbolic links and missing
    parents are not checked; the value is purely a reconstruction of
    the original serialised string.

    Parameters
    ----------
    encoded_path
        Token previously produced by :func:`encode_path` that should
        be restored to its original path form. Passed positionally
        only.

    Returns
    -------
        Reconstructed filesystem path corresponding to the original
        value that was passed to :func:`encode_path`.

    See Also
    --------
    encode_path : Forward helper whose output this function reverses.
    urllib.parse.unquote : Underlying percent-decoding routine used
        to reverse URL escaping before re-inserting path separators.
    pathlib.Path : Path abstraction used to wrap the returned value.

    Examples
    --------
    >>> from mayutils.environment.filesystem import decode_path, encode_path
    >>> decode_path("data%23raw%23file.csv")
    PosixPath('data/raw/file.csv')
    >>> original = "logs/2026-04-22.log"
    >>> str(decode_path(encode_path(original))) == original
    True
    """
    return Path(urllib.parse.unquote(string=encoded_path).replace("#", "/"))


__all__ = [
    "decode_path",
    "encode_path",
]
