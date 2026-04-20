"""SQL query discovery and templating utilities.

This module exposes helpers for locating, loading, and interpolating
SQL query files that live either inside the host project or inside
installed sibling packages. It builds a deterministic search path
rooted at the project directory, exposes it as a module-level constant,
and provides convenience functions that resolve a query by name and
optionally substitute placeholders via :meth:`str.format`.
"""

from pathlib import Path

from mayutils.environment.filesystem import (
    get_root,
    read_file,
)
from mayutils.objects.types import SupportsStr


def get_queries_folders() -> tuple[Path, ...]:
    """Build the ordered search path used to resolve bundled SQL query files.

    The resulting tuple chains together, in priority order, the
    project's top-level ``queries/`` directory, a ``data/queries``
    directory for every package found under ``src/``, and finally the
    directory containing this module. Earlier entries take precedence
    when the same query filename exists in multiple locations, which
    lets a host project override queries shipped by installed
    packages.

    Returns
    -------
    tuple[pathlib.Path, ...]
        Directories to scan for query files, ordered from highest to
        lowest precedence. The returned paths are not guaranteed to
        exist on disk; callers should treat missing directories as
        simply contributing no candidate queries.
    """
    root = get_root()

    return (
        root / "queries",
        *[root / "src" / module.name / "data" / "queries" for module in (root / "src").iterdir() if module.is_dir()],
        Path(__file__).parent,
    )


QUERIES_FOLDERS = get_queries_folders()


def read_query(
    path: Path | str,
    /,
    *,
    queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
    default_suffix: str = "sql",
) -> str:
    """Load the raw text of a named SQL query from the search path.

    The input is first normalised to a :class:`~pathlib.Path`. If it
    carries no file extension, ``default_suffix`` is appended so that
    callers can reference queries by bare name (``"my_query"``) rather
    than by filename. An already-resolvable absolute or relative path
    is read directly; otherwise each directory in ``queries_folders``
    is checked in order and the first match wins.

    Parameters
    ----------
    path : pathlib.Path or str
        Query identifier. May be a bare name such as ``"revenue"``
        (resolved against the search path with ``default_suffix``
        applied), a relative path containing subdirectories, or a
        full path pointing directly at an existing file.
    queries_folders : tuple[pathlib.Path, ...], optional
        Directories to scan when ``path`` is not directly resolvable.
        Defaults to :data:`QUERIES_FOLDERS`, the project-wide search
        path computed at import time.
    default_suffix : str, optional
        File extension, without leading dot, to append when ``path``
        has no suffix. Defaults to ``"sql"``, matching the conventional
        extension for query files.

    Returns
    -------
    str
        The raw textual contents of the resolved query file, read via
        :func:`mayutils.environment.filesystem.read_file`.

    Raises
    ------
    ValueError
        If the query cannot be located at the direct path nor within
        any directory in ``queries_folders``. The error message lists
        every folder that was searched.
    """
    path = Path(path)

    if path.suffix == "":
        path = path.with_suffix(suffix=f".{default_suffix}")

    if path.exists():
        return read_file(path)

    for queries_folder in queries_folders:
        possible_query_path = queries_folder / path
        if possible_query_path.exists():
            return read_file(possible_query_path)

    msg = f"No query {path} found including in the query folders {', '.join(list(map(str, queries_folders)))}"
    raise ValueError(msg)


def format_query(
    path: Path | str,
    /,
    *,
    queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
    default_suffix: str = "sql",
    **format_kwargs: SupportsStr,
) -> str:
    """Load a named SQL query and interpolate placeholders via :meth:`str.format`.

    This is a thin convenience wrapper around :func:`read_query`: it
    resolves the query text using the same rules and then applies
    ``str.format`` with ``format_kwargs`` to substitute named
    placeholders of the form ``{name}`` embedded in the SQL.

    Parameters
    ----------
    path : pathlib.Path or str
        Query identifier, interpreted exactly as in :func:`read_query`.
    queries_folders : tuple[pathlib.Path, ...], optional
        Search path forwarded to :func:`read_query`. Defaults to
        :data:`QUERIES_FOLDERS`.
    default_suffix : str, optional
        Extension forwarded to :func:`read_query` for queries
        referenced by bare name. Defaults to ``"sql"``.
    **format_kwargs : SupportsStr
        Keyword substitutions passed to :meth:`str.format`. Each value
        must be stringifiable; at format time Python inserts its
        string representation at the matching placeholder.

    Returns
    -------
    str
        The query text after placeholder substitution, ready to be
        submitted to a database driver.

    Raises
    ------
    ValueError
        If :func:`read_query` cannot resolve the query file.
    KeyError
        If the query template references a placeholder for which no
        matching keyword was supplied in ``format_kwargs``.
    IndexError
        If the query template contains positional placeholders (``{0}``)
        without corresponding positional arguments, since only keyword
        substitutions are accepted here.
    """
    unformatted_query = read_query(
        path,
        queries_folders=queries_folders,
        default_suffix=default_suffix,
    )

    return unformatted_query.format(**format_kwargs)
