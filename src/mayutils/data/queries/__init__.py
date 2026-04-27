"""
Locate and interpolate SQL query files shipped with the project.

This module exposes helpers for locating, loading, and interpolating
SQL query files that live either inside the host project or inside
installed sibling packages. It builds a deterministic search path
rooted at the project directory, exposes it as a module-level constant,
and provides convenience functions that resolve a query by name and
optionally substitute placeholders via :meth:`str.format`. The search
path lets a host project override query text shipped by upstream
packages simply by placing a file with the same relative name in its
own ``queries/`` directory.

See Also
--------
mayutils.data.read : Consumer utilities that turn query text into
    DataFrames via SQLAlchemy engines.
mayutils.environment.filesystem.read_file : Primitive used here to
    read the resolved query text from disk.
sqlalchemy.text : Typical wrapper applied to the string produced by
    :func:`format_query` before execution.
string.Template : Alternative placeholder mechanism whose ``$name``
    syntax differs from the ``{name}`` braces used here.

Examples
--------
Resolve the default search path, read a query by bare name, and
interpolate a pair of placeholders:

>>> from mayutils.data.queries import QUERIES_FOLDERS
>>> isinstance(QUERIES_FOLDERS, tuple)
True
>>> from mayutils.data.queries import format_query
>>> sql = format_query(  # doctest: +SKIP
...     "revenue",
...     schema="analytics",
...     start_date="2024-01-01",
... )
>>> print(sql)  # doctest: +SKIP
SELECT * FROM analytics.revenue WHERE dt >= '2024-01-01'
"""

from pathlib import Path

from mayutils.environment.filesystem import (
    get_root,
    read_file,
)
from mayutils.objects.types import SupportsStr


def get_queries_folders() -> tuple[Path, ...]:
    """
    Build the ordered search path used to resolve bundled SQL query files.

    The resulting tuple chains together, in priority order, the
    project's top-level ``queries/`` directory, a ``data/queries``
    directory for every package found under ``src/``, and finally the
    directory containing this module. Earlier entries take precedence
    when the same query filename exists in multiple locations, which
    lets a host project override queries shipped by installed
    packages. The function is evaluated once at import time to
    populate :data:`QUERIES_FOLDERS`, but callers may invoke it
    explicitly after adding a new ``src/`` package to pick up the
    change without restarting the interpreter.

    Returns
    -------
        Directories to scan for query files, ordered from highest to
        lowest precedence. The returned paths are not guaranteed to
        exist on disk; callers should treat missing directories as
        simply contributing no candidate queries.

    See Also
    --------
    read_query : Primary consumer of the returned search path.
    format_query : Sibling helper that resolves and interpolates a
        query using this search path.
    mayutils.environment.filesystem.get_root : Supplies the project
        root anchor used to derive the folders.

    Examples
    --------
    Inspect the folders that will be searched for bundled SQL files:

    >>> from mayutils.data.queries import get_queries_folders
    >>> folders = get_queries_folders()
    >>> isinstance(folders, tuple)
    True
    >>> len(folders) >= 0
    True
    >>> all(hasattr(folder, "name") for folder in folders)
    True
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
    """
    Load the raw text of a named SQL query from the search path.

    The input is first normalised to a :class:`~pathlib.Path`. If it
    carries no file extension, ``default_suffix`` is appended so that
    callers can reference queries by bare name (``"my_query"``) rather
    than by filename. An already-resolvable absolute or relative path
    is read directly; otherwise each directory in ``queries_folders``
    is checked in order and the first match wins. The returned string
    preserves the file's original whitespace and line endings so that
    downstream formatting with :meth:`str.format` remains predictable.

    Parameters
    ----------
    path
        Query identifier. May be a bare name such as ``"revenue"``
        (resolved against the search path with ``default_suffix``
        applied), a relative path containing subdirectories, or a
        full path pointing directly at an existing file.
    queries_folders
        Directories to scan when ``path`` is not directly resolvable.
        Defaults to :data:`QUERIES_FOLDERS`, the project-wide search
        path computed at import time.
    default_suffix
        File extension, without leading dot, to append when ``path``
        has no suffix. Defaults to ``"sql"``, matching the conventional
        extension for query files.

    Returns
    -------
        The raw textual contents of the resolved query file, read via
        :func:`mayutils.environment.filesystem.read_file`.

    Raises
    ------
    ValueError
        If the query cannot be located at the direct path nor within
        any directory in ``queries_folders``. The error message lists
        every folder that was searched.

    See Also
    --------
    format_query : Convenience wrapper that additionally performs
        placeholder substitution on the text returned here.
    get_queries_folders : Producer of the default ``queries_folders``
        search path.
    mayutils.environment.filesystem.read_file : Low-level primitive
        responsible for actually opening the file.
    sqlalchemy.text : Typical destination for the returned string
        when passing it to a database engine.

    Examples
    --------
    Load a query shipped alongside the project by bare name:

    >>> from mayutils.data.queries import read_query
    >>> sql = read_query("loans_summary")  # doctest: +SKIP
    >>> print(sql)  # doctest: +SKIP
    SELECT loan_id, amount, status FROM loans_summary

    Load a query using an explicit path:

    >>> from pathlib import Path
    >>> sql = read_query(Path("queries/revenue.sql"))  # doctest: +SKIP
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
    """
    Load a named SQL query and interpolate placeholders via ``str.format``.

    Act as a thin convenience wrapper around :func:`read_query`: the
    query text is resolved using the same rules and then passed
    through :meth:`str.format` with ``format_kwargs`` to substitute
    named placeholders of the form ``{name}`` embedded in the SQL.
    Because substitution is performed with :meth:`str.format` and not
    with SQL parameter binding, only values safe for literal
    interpolation (schema names, table names, date literals) should
    be passed; user-supplied values intended as query parameters must
    still be bound by the driver downstream.

    Parameters
    ----------
    path
        Query identifier, interpreted exactly as in :func:`read_query`.
    queries_folders
        Search path forwarded to :func:`read_query`. Defaults to
        :data:`QUERIES_FOLDERS`.
    default_suffix
        Extension forwarded to :func:`read_query` for queries
        referenced by bare name. Defaults to ``"sql"``.
    **format_kwargs
        Keyword substitutions passed to :meth:`str.format`. Each value
        must be stringifiable; at format time Python inserts its
        string representation at the matching placeholder.

    Returns
    -------
        The query text after placeholder substitution, ready to be
        submitted to a database driver. :class:`ValueError` propagates
        from :func:`read_query` when the template cannot be located,
        :class:`KeyError` propagates from :meth:`str.format` when a
        referenced placeholder has no matching keyword, and
        :class:`IndexError` propagates when a template uses positional
        ``{0}`` placeholders without positional arguments (only
        keyword substitution is supported here).

    See Also
    --------
    read_query : Underlying loader that locates the template text.
    get_queries_folders : Producer of the default search path used
        to resolve ``path``.
    sqlalchemy.text : Typical next step for the returned SQL string
        prior to execution against an engine.
    string.Template : Alternative placeholder mechanism if callers
        prefer ``$name`` syntax to the ``{name}`` used here.

    Examples
    --------
    Interpolate a schema name and date bound into a bundled query:

    >>> from mayutils.data.queries import format_query
    >>> sql = format_query(  # doctest: +SKIP
    ...     "loans_by_region",
    ...     region="London",
    ... )
    >>> print(sql)  # doctest: +SKIP
    SELECT * FROM loans WHERE region = 'London'

    Pass multiple substitutions:

    >>> sql = format_query(  # doctest: +SKIP
    ...     "revenue",
    ...     schema="analytics",
    ...     start_date="2024-01-01",
    ... )
    """
    unformatted_query = read_query(
        path,
        queries_folders=queries_folders,
        default_suffix=default_suffix,
    )

    return unformatted_query.format(**format_kwargs)
