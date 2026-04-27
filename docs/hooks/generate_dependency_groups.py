"""
Regenerate the optional-extras table inside the dependency-groups guide.

Parse ``[project.optional-dependencies]`` from the repository's
``pyproject.toml`` and splice a freshly rendered Markdown table into
``docs/guides/dependency-groups.md`` between a pair of sentinel HTML
comments. The module is loaded by MkDocs as a build hook and exposes
``on_pre_build`` so the guide is refreshed before MkDocs reads any
files for the build. Writes are performed only when the surrounding
markers are present and only if the rendered table differs from what
is already on disk, keeping the hook idempotent across repeated
``mkdocs build`` runs.

See Also
--------
mkdocs.plugins : Defines the ``on_pre_build`` event hooked here.
docs.hooks.readme_to_index : Sibling ``on_pre_build`` hook that regenerates ``docs/index.md``.
docs.gen_ref_pages : Companion reference-page generator executed via ``mkdocs-gen-files``.
mkdocstrings : Renders the per-module stubs emitted by ``docs.gen_ref_pages``.

Examples
--------
Wire the module in as a hook in ``mkdocs.yml``:

>>> # mkdocs.yml
>>> # hooks:
>>> #   - docs/hooks/generate_dependency_groups.py

Running a build then rewrites the sentinel-bounded block in place:

>>> # $ mkdocs build
>>> # $ grep -A3 "BEGIN AUTO-GENERATED" docs/guides/dependency-groups.md
"""  # noqa: INP001

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig

MARKER_START = "<!-- BEGIN AUTO-GENERATED GROUPS TABLE -->"
MARKER_END = "<!-- END AUTO-GENERATED GROUPS TABLE -->"


def _render_table(
    pyproject: Path,
) -> str:
    """
    Render the optional-extras Markdown table from ``pyproject.toml``.

    Load the TOML file at ``pyproject``, pull ``[project.optional-dependencies]``,
    then build a three-column Markdown table listing the extra name, a
    copy-pasteable ``uv add`` command, and each declared distribution
    formatted via :func:`_format_distribution`. Extras are emitted in
    sorted order so builds are deterministic and diff-friendly. The
    function is pure: it reads only the given path and returns the
    rendered string without touching the docs tree itself.

    Parameters
    ----------
    pyproject
        Filesystem path to the ``pyproject.toml`` whose
        ``[project.optional-dependencies]`` table should be rendered.

    Returns
    -------
        Markdown table text with header, separator and one row per
        declared extra. Rows are newline-delimited without a trailing
        newline so callers can splice the result between sentinels.

    See Also
    --------
    _format_distribution : Helper used to stringify each dependency spec.
    on_pre_build : Caller that splices the returned table into the guide.
    mkdocs.plugins : Framework that ultimately drives the build hook.

    Examples
    --------
    Called indirectly by MkDocs during ``on_pre_build``:

    >>> # mkdocs.yml
    >>> # hooks:
    >>> #   - docs/hooks/generate_dependency_groups.py

    Invoked implicitly via a standard build:

    >>> # $ mkdocs build  # runs on_pre_build, which calls _render_table
    """
    data = tomllib.loads(pyproject.read_text())
    optional: dict[str, list[str]] = data.get("project", {}).get("optional-dependencies", {}) or {}

    lines = ["| Extra | Install | Distributions |", "| ----- | ------- | ------------- |"]
    for name in sorted(optional):
        dists = optional[name]
        rendered_dists = ", ".join(_format_distribution(spec=spec) for spec in dists)
        install = f'`uv add "mayutils[{name}]"`'
        lines.append(f"| `{name}` | {install} | {rendered_dists} |")

    return "\n".join(lines)


def _format_distribution(
    spec: str,
) -> str:
    """
    Format a single PEP 508 dependency specifier for the extras table.

    Strip any PEP 508 environment marker after ``;``, then drop the
    version specifier and extras suffix to isolate the bare distribution
    name. Self-references of the form ``mayutils[foo,bar]`` are rendered
    as a human-readable list of sub-extras prefixed with ``meta:`` so
    meta-extras advertise their contents; every other distribution is
    returned as an inline-code Markdown span. The helper performs no I/O
    and is safe to call from ``_render_table`` inside ``on_pre_build``.

    Parameters
    ----------
    spec
        A PEP 508 requirement string as it appears in
        ``[project.optional-dependencies]`` (for example
        ``"pandas>=2.0; python_version>='3.11'"`` or
        ``"mayutils[io,viz]"``).

    Returns
    -------
        Markdown fragment suitable for the "Distributions" column of
        the extras table: either an inline-code span wrapping the
        distribution name, or a ``meta:``-prefixed list of sub-extras
        for self-referential meta extras.

    See Also
    --------
    _render_table : Caller that joins formatted specs into a full row.
    on_pre_build : Top-level hook ultimately responsible for invocation.
    mkdocs.plugins : Event framework that schedules the surrounding hook.

    Examples
    --------
    Invoked during a MkDocs build configured with this hook:

    >>> # mkdocs.yml
    >>> # hooks:
    >>> #   - docs/hooks/generate_dependency_groups.py

    The build rewrites the guide without manual intervention:

    >>> # $ mkdocs build
    """
    without_marker = spec.split(";", maxsplit=1)[0].strip()
    head = (
        without_marker.split("[", maxsplit=1)[0]
        .split(">", maxsplit=1)[0]
        .split("<", maxsplit=1)[0]
        .split("=", maxsplit=1)[0]
        .split("!", maxsplit=1)[0]
        .split("~", maxsplit=1)[0]
        .strip()
    )
    dist_key = head.replace("_", "-").lower()

    if dist_key == "mayutils" and "[" in without_marker:
        sub_extras = without_marker.split("[", maxsplit=1)[1].rsplit("]", maxsplit=1)[0]
        parts = [f"`{extra.strip()}`" for extra in sub_extras.split(",") if extra.strip()]
        return "meta: " + " + ".join(parts)

    return f"`{head}`"


def on_pre_build(
    config: MkDocsConfig,
    **_kwargs: object,
) -> None:
    """
    Regenerate the optional-extras table before the docs build starts.

    Resolve ``docs/guides/dependency-groups.md`` and the sibling
    ``pyproject.toml`` from ``config['docs_dir']``, bail out quietly if
    either is missing or the guide does not contain both marker
    comments, then replace the text between ``MARKER_START`` and
    ``MARKER_END`` with a freshly rendered table. The file is written
    only when its content actually changes, so repeated builds do not
    touch the filesystem. MkDocs fires this callback at the
    ``on_pre_build`` phase, which runs after configuration is loaded
    but before any source files are read or plugins enumerate pages.

    Parameters
    ----------
    config
        Fully resolved MkDocs configuration object supplied by the
        framework; only ``config['docs_dir']`` is consulted.
    **_kwargs
        Additional keyword arguments that MkDocs may pass to
        ``on_pre_build`` in future releases; ignored by this hook.

    See Also
    --------
    mkdocs.plugins : Defines the ``on_pre_build`` event contract.
    docs.hooks.readme_to_index : Sibling hook that regenerates the landing page.
    _render_table : Helper that produces the Markdown table body.
    _format_distribution : Helper invoked per dependency specifier.

    Examples
    --------
    Register the module as a hook so MkDocs invokes ``on_pre_build``:

    >>> # mkdocs.yml
    >>> # hooks:
    >>> #   - docs/hooks/generate_dependency_groups.py

    Trigger the hook from the command line:

    >>> # $ mkdocs build    # or: mkdocs serve
    """
    doc = Path(config["docs_dir"]) / "guides" / "dependency-groups.md"  # pyright: ignore[reportUnknownArgumentType]
    pyproject = Path(config["docs_dir"]).parent / "pyproject.toml"  # pyright: ignore[reportUnknownArgumentType]
    if not doc.is_file() or not pyproject.is_file():
        return

    content = doc.read_text()
    if MARKER_START not in content or MARKER_END not in content:
        return

    before, _, tail = content.partition(MARKER_START)
    _, _, after = tail.partition(MARKER_END)

    table = _render_table(pyproject=pyproject)
    new_content = before + MARKER_START + "\n\n" + table + "\n\n" + MARKER_END + after

    if new_content != content:
        doc.write_text(new_content)
