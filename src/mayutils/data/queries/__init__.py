"""
Locate and render Jinja SQL query templates shipped with the project.

This module exposes helpers for locating, loading, and rendering
SQL query files that live either inside the host project or inside
installed sibling packages. It builds a deterministic search path
rooted at the project directory, exposes it as a module-level constant,
and provides convenience functions that resolve a query by name and
optionally render it with Jinja2 via ``template_kwargs``. The search
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
mayutils.data.queries.templating : Jinja2 rendering engine used by
    :func:`format_query`.

Examples
--------
Resolve the default search path, read a query by bare name, and
render a pair of Jinja placeholders:

>>> from mayutils.data.queries import QUERIES_FOLDERS
>>> isinstance(QUERIES_FOLDERS, tuple)
True
>>> import tempfile
>>> from pathlib import Path
>>> from mayutils.data.queries import format_query
>>> with tempfile.TemporaryDirectory() as tmp:
...     folder = Path(tmp)
...     _ = (folder / "revenue.sql").write_text(
...         "SELECT * FROM {{ schema }}.revenue WHERE dt >= '{{ start_date }}'",
...         encoding="utf-8",
...     )
...     format_query(
...         "revenue",
...         queries_folders=(folder,),
...         template_kwargs={"schema": "analytics", "start_date": "2024-01-01"},
...     )
"SELECT * FROM analytics.revenue WHERE dt >= '2024-01-01'"
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mayutils.data.queries.templating import render_template
from mayutils.environment.filesystem import (
    get_root,
    read_file,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


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
    format_query : Sibling helper that resolves and renders a
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
    downstream Jinja rendering via :func:`format_query` remains
    predictable.

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
        Jinja rendering on the text returned here.
    get_queries_folders : Producer of the default ``queries_folders``
        search path.
    mayutils.environment.filesystem.read_file : Low-level primitive
        responsible for actually opening the file.
    sqlalchemy.text : Typical destination for the returned string
        when passing it to a database engine.

    Examples
    --------
    Load a query by bare name from an explicit search folder, with the
    ``.sql`` suffix supplied automatically:

    >>> import tempfile
    >>> from pathlib import Path
    >>> from mayutils.data.queries import read_query
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     folder = Path(tmp)
    ...     _ = (folder / "loans_summary.sql").write_text(
    ...         "SELECT loan_id, amount, status FROM loans_summary",
    ...         encoding="utf-8",
    ...     )
    ...     read_query("loans_summary", queries_folders=(folder,))
    'SELECT loan_id, amount, status FROM loans_summary'

    A query that cannot be resolved raises :class:`ValueError` naming
    every folder that was searched:

    >>> try:
    ...     read_query("missing", queries_folders=())
    ... except ValueError as error:
    ...     print(error)
    No query missing.sql found including in the query folders
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
    template_kwargs: Mapping[str, object] | None = None,
) -> str:
    """
    Load a named SQL query and render its Jinja2 placeholders.

    Act as a thin convenience wrapper around :func:`read_query`: the
    query text is resolved using the same rules and then passed to
    :func:`~mayutils.data.queries.templating.render_template` with
    ``template_kwargs`` to substitute ``{{ name }}`` Jinja2 placeholders.
    The environment uses :class:`~jinja2.StrictUndefined`, so
    referencing a template variable not present in ``template_kwargs``
    raises :class:`~jinja2.exceptions.UndefinedError`. Because
    substitution is performed via Jinja2 and not via SQL parameter
    binding, only values safe for literal interpolation (schema names,
    table names, date literals) should be passed; user-supplied values
    intended as query parameters must still be bound by the driver
    downstream. Full Jinja2 syntax — ``{% for %}``, ``{% if %}``,
    ``{% include %}``, etc. — is supported.

    Parameters
    ----------
    path
        Query identifier, interpreted exactly as in :func:`read_query`.
    queries_folders
        Search path forwarded to :func:`read_query` and also to
        :func:`~mayutils.data.queries.templating.render_template` so
        that ``{% include %}`` directives resolve against the same
        directories. Defaults to :data:`QUERIES_FOLDERS`.
    default_suffix
        Extension forwarded to :func:`read_query` for queries
        referenced by bare name. Defaults to ``"sql"``.
    template_kwargs
        Mapping of Jinja2 variable names to their values, forwarded
        to :func:`~mayutils.data.queries.templating.render_template`.
        When ``None`` or omitted the template is rendered with no
        variables, which is only valid for templates that contain no
        variable references; otherwise
        :class:`~jinja2.exceptions.UndefinedError` is raised.

    Returns
    -------
        The fully rendered SQL string with all Jinja2 directives
        expanded and all ``{{ variable }}`` placeholders substituted.
        :class:`ValueError` propagates from :func:`read_query` when
        the template cannot be located.
        :class:`~jinja2.exceptions.UndefinedError` propagates from the
        Jinja2 engine when the template references a variable not
        present in ``template_kwargs``.

    See Also
    --------
    read_query : Underlying loader that locates the template text.
    mayutils.data.queries.templating.render_template : Jinja2
        rendering function invoked after the template is loaded.
    get_queries_folders : Producer of the default search path used
        to resolve ``path``.
    sqlalchemy.text : Typical next step for the returned SQL string
        prior to execution against an engine.

    Examples
    --------
    Render a single Jinja2 placeholder in a query loaded from an
    explicit search folder:

    >>> import tempfile
    >>> from pathlib import Path
    >>> from mayutils.data.queries import format_query
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     folder = Path(tmp)
    ...     _ = (folder / "loans_by_region.sql").write_text(
    ...         "SELECT * FROM loans WHERE region = '{{ region }}'",
    ...         encoding="utf-8",
    ...     )
    ...     format_query(
    ...         "loans_by_region",
    ...         queries_folders=(folder,),
    ...         template_kwargs={"region": "London"},
    ...     )
    "SELECT * FROM loans WHERE region = 'London'"

    A placeholder with no matching variable propagates
    :class:`~jinja2.exceptions.UndefinedError`:

    >>> from jinja2.exceptions import UndefinedError
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     folder = Path(tmp)
    ...     _ = (folder / "needs_arg.sql").write_text(
    ...         "SELECT * FROM {{ schema }}.t",
    ...         encoding="utf-8",
    ...     )
    ...     try:
    ...         format_query("needs_arg", queries_folders=(folder,))
    ...     except UndefinedError as error:
    ...         print(error)
    'schema' is undefined
    """
    unformatted_query = read_query(
        path,
        queries_folders=queries_folders,
        default_suffix=default_suffix,
    )

    return render_template(
        unformatted_query,
        queries_folders=queries_folders,
        template_kwargs=template_kwargs,
    )
