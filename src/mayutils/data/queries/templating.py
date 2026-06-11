"""
Render SQL query templates with Jinja2.

Single home for the Jinja environment used by
:func:`mayutils.data.queries.format_query` and
:func:`mayutils.data.read.render_query`. Environments are cached per
``queries_folders`` tuple and use a :class:`jinja2.FileSystemLoader`
over those folders so ``{% include %}`` honours the same
project-overrides-package precedence as query resolution itself.

See Also
--------
mayutils.data.queries : Filesystem lookup of SQL templates.
jinja2.Environment : Underlying rendering engine.

Examples
--------
>>> from mayutils.data.queries.templating import render_template
>>> render_template("SELECT * FROM {{ table }}", jinja_kwargs={"table": "loans"})
'SELECT * FROM loans'
"""

from __future__ import annotations

import warnings
from functools import cache
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, StrictUndefined

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


class TemplateStyleWarning(UserWarning):
    """
    Warn when a rendered query still contains ``{kwarg}``-style placeholders.

    Emitted by :func:`render_template` when the original template text
    contains at least one ``{name}`` substring that matches a key that
    was passed in ``jinja_kwargs``. This indicates an unmigrated
    :meth:`str.format` template — the placeholder was never expanded
    because Jinja2 does not recognise single-brace syntax, so the
    caller's intent was likely not fulfilled.

    See Also
    --------
    render_template : Function that emits this warning.

    Examples
    --------
    >>> import warnings
    >>> from mayutils.data.queries.templating import TemplateStyleWarning, render_template
    >>> with warnings.catch_warnings(record=True) as w:
    ...     warnings.simplefilter("always")
    ...     render_template("SELECT * FROM {table}", jinja_kwargs={"table": "loans"})
    ...     assert issubclass(w[0].category, TemplateStyleWarning)
    'SELECT * FROM {table}'
    """


@cache
def get_environment(
    queries_folders: tuple[Path, ...],
    /,
) -> Environment:
    """
    Build and cache a Jinja2 :class:`~jinja2.Environment` for *queries_folders*.

    Constructs an :class:`~jinja2.Environment` backed by a
    :class:`~jinja2.FileSystemLoader` whose search path is the ordered
    sequence of directories in *queries_folders*. The environment uses
    :class:`~jinja2.StrictUndefined` so that any template variable not
    supplied at render time raises :class:`~jinja2.exceptions.UndefinedError`
    immediately rather than silently expanding to an empty string.
    Results are memoised via :func:`functools.cache` keyed on the
    *queries_folders* tuple so repeated calls with the same search path
    return the same object without rebuilding the loader.

    Parameters
    ----------
    queries_folders
        Ordered tuple of directories passed to
        :class:`~jinja2.FileSystemLoader`. Earlier entries take precedence
        when the same template name exists in multiple locations, matching
        the project-overrides-package convention used by
        :func:`mayutils.data.queries.get_queries_folders`.

    Returns
    -------
        A fully configured :class:`~jinja2.Environment` whose loader
        resolves ``{% include %}`` and ``{% extends %}`` directives
        against *queries_folders*.

    See Also
    --------
    render_template : Primary consumer that calls this function.
    mayutils.data.queries.get_queries_folders : Produces the default
        search path suitable for passing here.

    Examples
    --------
    >>> from pathlib import Path
    >>> from mayutils.data.queries.templating import get_environment
    >>> env = get_environment(())
    >>> env is get_environment(())
    True
    """
    return Environment(
        loader=FileSystemLoader(searchpath=[str(folder) for folder in queries_folders]),
        undefined=StrictUndefined,
        autoescape=False,  # noqa: S701
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template(
    text: str,
    /,
    *,
    queries_folders: tuple[Path, ...] = (),
    jinja_kwargs: Mapping[str, object] | None = None,
) -> str:
    """
    Render a Jinja2 SQL template string and return the expanded text.

    Compiles *text* as a Jinja2 template using the environment returned
    by :func:`get_environment` for *queries_folders*, then renders it
    by forwarding all entries in *jinja_kwargs* as template variables.
    The environment uses :class:`~jinja2.StrictUndefined`, so referencing
    a variable not present in *jinja_kwargs* immediately raises
    :class:`~jinja2.exceptions.UndefinedError`. The original template
    *text* is also scanned for ``{name}`` substrings matching any key
    in *jinja_kwargs*; when any are found a
    :class:`TemplateStyleWarning` is emitted to signal an unmigrated
    :meth:`str.format` template.

    Parameters
    ----------
    text
        Raw SQL template string. May contain any Jinja2 syntax:
        ``{{ variable }}``, ``{% for %}``, ``{% if %}``,
        ``{% include 'fragment.sql' %}``, etc.
    queries_folders
        Ordered tuple of directories used to resolve ``{% include %}``
        and ``{% extends %}`` directives. Forwarded verbatim to
        :func:`get_environment`. Defaults to an empty tuple, which
        disables file-based includes.
    jinja_kwargs
        Mapping of template variable names to their values. When
        ``None`` or omitted the template is rendered with no variables,
        which is only valid for templates that contain no variable
        references (otherwise :class:`~jinja2.exceptions.UndefinedError`
        is raised).

    Returns
    -------
        The fully rendered SQL string with all Jinja2 directives
        expanded and all ``{{ variable }}`` placeholders substituted.
        :class:`~jinja2.exceptions.UndefinedError` propagates from the
        Jinja2 engine when the template references a variable not
        present in *jinja_kwargs*.

    Warns
    -----
    TemplateStyleWarning
        When the original template *text* contains ``{name}`` for a
        key that was supplied in *jinja_kwargs*, indicating an
        unmigrated :meth:`str.format`-style placeholder.

    See Also
    --------
    get_environment : Constructs the cached Jinja2 environment used here.
    mayutils.data.queries.format_query : Higher-level helper that
        resolves a query by name before rendering.
    mayutils.data.read.render_query : Reader-layer wrapper that
        additionally executes the rendered SQL.

    Examples
    --------
    Substitute a single variable:

    >>> from mayutils.data.queries.templating import render_template
    >>> render_template("SELECT * FROM {{ table }}", jinja_kwargs={"table": "loans"})
    'SELECT * FROM loans'

    Static templates pass through unchanged:

    >>> render_template("SELECT 1")
    'SELECT 1'

    Conditionals collapse absent values:

    >>> render_template(
    ...     "SELECT 1{% if flag %} WHERE flag{% endif %}",
    ...     jinja_kwargs={"flag": None},
    ... )
    'SELECT 1'
    """
    jinja_kwargs = dict(jinja_kwargs or {})

    rendered = get_environment(queries_folders).from_string(source=text).render(**jinja_kwargs)

    legacy = [name for name in jinja_kwargs if f"{{{name}}}" in text]
    if legacy:
        warnings.warn(
            message=f"Rendered query still contains str.format-style placeholders {legacy}; "
            f"migrate the template to Jinja syntax ({{{{ name }}}}).",
            category=TemplateStyleWarning,
            stacklevel=2,
        )

    return rendered


__all__ = [
    "TemplateStyleWarning",
    "get_environment",
    "render_template",
]
