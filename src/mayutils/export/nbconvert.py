"""Thin wrapper around the ``jupyter nbconvert`` command-line interface.

This module exposes a small, type-safe surface for discovering the
export formats and templates registered with a local Jupyter
installation and for rendering a notebook to any of those formats. The
helpers shell out to the ``jupyter`` CLI rather than using the
``nbconvert`` Python API directly so that the user's configured
kernels, extensions and template search paths are honoured exactly as
they are on the command line. All rendered artefacts are placed under
:data:`NBCONVERT_FOLDER` with an ISO-8601 UTC timestamp appended to the
stem so that repeated exports never overwrite previous runs.
"""

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mayutils.core.extras import may_require_extras
from mayutils.export import OUTPUT_FOLDER

with may_require_extras():
    from jupyter_core.paths import jupyter_path
    from nbconvert.exporters import get_export_names  # pyright: ignore[reportUnknownVariableType]
    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn


FORMAT_EXTENSIONS: dict[str, str] = {
    "asciidoc": ".asciidoc",
    "html": ".html",
    "latex": ".tex",
    "markdown": ".md",
    "notebook": ".ipynb",
    "pdf": ".pdf",
    "python": ".py",
    "qtpdf": ".pdf",
    "qtpng": ".png",
    "rst": ".rst",
    "script": ".py",
    "slides": ".slides.html",
    "webpdf": ".pdf",
}
"""Canonical file extension produced by ``jupyter nbconvert`` per format.

``jupyter nbconvert`` auto-appends the correct extension when
``--output`` is a bare stem, but silently produces doubled suffixes like
``report.markdown.md`` or ``report.slides.slides.html`` when the caller
supplies a guess that doesn't match its exporter trait. :func:`export`
therefore passes a stemless ``--output`` and consults this table to
compose the returned ``Path``. The ``"script"`` exporter's extension is
kernel-dependent; ``.py`` is the correct default for the common Python
kernel and can be overridden globally by mutating this dictionary.
"""

DEFAULT_SETTINGS: dict[str, dict[str, Any]] = {
    "asciidoc": {},
    "html": {},
    "latex": {},
    "markdown": {},
    "notebook": {},
    "pdf": {},
    "qtpdf": {},
    "qtpng": {},
    "rst": {},
    "script": {},
    "slides": {
        "no-input": None,
        "no-prompt": None,
        "SlidesExporter.reveal_scroll": "True",
        "SlidesExporter.reveal_number": "c/t",
        "SlidesExporter.reveal_theme": "night",
    },
    "webpdf": {},
}
"""Per-format default ``nbconvert`` CLI arguments.

Keys are the ``nbconvert`` export format names (the value passed via ``--to``)
and values are a mapping of CLI option → value that :func:`export` will expand
into ``--key value`` (or just ``--key`` when the value is ``None``) before
invoking ``jupyter nbconvert``. The defaults are merged with the caller-supplied
``**kwargs`` at call time so individual exports can override or extend a format's
baseline; mutate this dictionary in application-level bootstrap code to change
the defaults globally.
"""


def jupyter_bin() -> str:
    """Locate the ``jupyter`` executable on the current ``PATH``.

    The resolved absolute path is used to invoke ``nbconvert`` as a
    subprocess so that the call succeeds even when the active
    interpreter's ``Scripts``/``bin`` directory is not the first entry
    on the shell's search path.

    Returns
    -------
    str
        Absolute filesystem path to the ``jupyter`` CLI as reported by
        :func:`shutil.which`.

    Raises
    ------
    RuntimeError
        If no ``jupyter`` binary can be found on ``PATH``. The error
        message includes the ``mayutils[notebook]`` extra install
        hint so the user can remediate without further lookup.
    """
    binary = shutil.which("jupyter")
    if binary is None:
        msg = (
            "The 'jupyter' CLI is not available on PATH. "
            'Install it with: uv add "mayutils[notebook]" '
            '(or pip install "mayutils[notebook]").'
        )
        raise RuntimeError(msg)

    return binary


def list_formats() -> tuple[str, ...]:
    """Enumerate every export format currently registered with ``nbconvert``.

    Delegates to :func:`nbconvert.exporters.get_export_names`, which
    reflects both the built-in exporters and any third-party exporters
    installed as entry points in the active environment. The result is
    used by :func:`export` to validate the ``to`` argument before
    spawning the subprocess.

    Returns
    -------
    tuple of str
        Names of the available export formats in the order reported by
        ``nbconvert``, suitable for passing via ``--to``.
    """
    exporters: list[str] = get_export_names()  # pyright: ignore[reportUnknownVariableType]

    return tuple(str(name) for name in exporters)


def list_templates(
    *,
    extra_basedirs: tuple[Path, ...] = (),
) -> tuple[str, ...]:
    """Enumerate the ``nbconvert`` templates available to the current user.

    Walks every ``<data>/nbconvert/templates/`` directory reported by
    :func:`jupyter_core.paths.jupyter_path` and treats any immediate
    child directory that contains a ``conf.json`` file as a template.
    The same discovery rule is applied to each entry in
    ``extra_basedirs`` so the function exactly mirrors the resolution
    order used by ``nbconvert`` itself when
    ``--TemplateExporter.extra_template_basedirs`` is supplied.

    Parameters
    ----------
    extra_basedirs : tuple of Path, optional
        Additional roots to include in the template search, beyond the
        Jupyter data paths. Each entry is searched both directly and
        under its ``nbconvert/templates`` subdirectory so the argument
        can accept either a Jupyter-style data root or a bespoke
        templates directory. Defaults to the empty tuple, which
        restricts discovery to the standard Jupyter data paths.

    Returns
    -------
    tuple of str
        Alphabetically sorted, de-duplicated collection of every
        template name discoverable from the combined search paths.
        Each entry can be passed verbatim as ``--template`` to
        ``jupyter nbconvert``.
    """
    search_dirs: list[Path] = [Path(path) for path in jupyter_path("nbconvert", "templates")]
    for basedir in extra_basedirs:
        search_dirs.extend((Path(basedir) / "nbconvert" / "templates", Path(basedir)))

    found: set[str] = set()
    for directory in search_dirs:
        if not directory.is_dir():
            continue
        for child in directory.iterdir():
            if child.is_dir() and (child / "conf.json").exists():
                found.add(child.name)

    return tuple(sorted(found))


def export(
    file: Path,
    /,
    *,
    to: str = "pdf",
    title: str | None = None,
    output_dir: Path | None = None,
    template: str | None = None,
    extra_template_basedirs: tuple[Path, ...] = (),
    **kwargs: str | bool | Path,
) -> Path:
    """Render a Jupyter notebook via ``jupyter nbconvert``.

    Builds and runs a ``jupyter nbconvert`` command line against
    ``file`` and writes the result into ``output_dir``. The output
    stem is composed from ``title`` (falling back to ``file.stem``)
    and the current UTC timestamp in ISO-8601 form so that repeated
    invocations never clobber a prior export. Both the requested
    output format and any template name are validated up front so
    that invalid inputs fail fast with a list of legal values rather
    than via an opaque non-zero exit from the child process.

    Parameters
    ----------
    file : Path
        Notebook on disk to render. Forwarded to ``nbconvert`` as-is,
        so any kernel and path resolution rules applied by the CLI
        also apply here.
    to : NbconvertFormat, optional
        Target export format. Must appear in :func:`list_formats`;
        selects the corresponding ``nbconvert`` exporter and therefore
        determines the file extension and rendering pipeline of the
        output. Defaults to ``"pdf"``.
    title : str or None, optional
        Stem used for the output filename before the timestamp suffix
        is appended. When ``None`` the stem of ``file`` is used, which
        keeps the output name aligned with the source notebook.
    output_dir : Path, optional
        Directory into which the rendered artefact is written. The
        directory is not created automatically; callers must ensure it
        exists. Defaults to :data:`NBCONVERT_FOLDER`.
    template : str or None, optional
        Name of an ``nbconvert`` template to apply, forwarded as
        ``--template``. When provided it is validated against
        :func:`list_templates` (including ``extra_template_basedirs``)
        so that a typo fails before the subprocess is launched. When
        ``None`` the exporter's default template is used.
    extra_template_basedirs : tuple of Path, optional
        Additional template search roots. Passed through one
        ``--TemplateExporter.extra_template_basedirs=<path>`` flag per
        entry, and also consulted when validating ``template``.
        Defaults to the empty tuple.
    **kwargs
        Additional ``nbconvert`` options. Each ``key=value`` pair is
        expanded to ``--key value`` on the command line (and to a
        bare ``--key`` flag when ``value`` is ``None``). Caller-
        supplied kwargs are layered on top of
        ``DEFAULT_SETTINGS[to]`` so callers can override or extend
        format-specific defaults without touching the global table.
        Non-identifier CLI names (e.g. ``no-input`` or dotted
        traitlets options such as ``TemplateExporter.exclude_input``)
        can be passed by splatting a dictionary:
        ``export(file, **{"no-input": None})``.

    Returns
    -------
    Path
        Absolute path of the rendered artefact with the extension
        resolved via :data:`FORMAT_EXTENSIONS` — i.e. the filename
        actually produced by ``jupyter nbconvert`` on disk, not the
        stemless value passed to ``--output``.

    Raises
    ------
    RuntimeError
        If the ``jupyter`` CLI cannot be located on ``PATH`` when
        :func:`_jupyter_bin` is consulted.
    ValueError
        If ``to`` is not among the formats returned by
        :func:`list_formats`, or if ``template`` is supplied and is
        not discoverable via :func:`list_templates` with the given
        ``extra_template_basedirs``.
    subprocess.CalledProcessError
        If the ``jupyter nbconvert`` invocation exits with a
        non-zero status, propagated from :func:`subprocess.run` under
        ``check=True``.
    """
    jupyter = jupyter_bin()

    available_formats = list_formats()
    if to not in available_formats:
        msg = f"Unknown nbconvert format {to!r}. Available: {available_formats}."
        raise ValueError(msg)

    if template is not None:
        available_templates = list_templates(extra_basedirs=extra_template_basedirs)
        if template not in available_templates:
            msg = f"Unknown nbconvert template {template!r}. Available: {available_templates}."
            raise ValueError(msg)

    if output_dir is None:
        output_dir = OUTPUT_FOLDER / to.title().replace("Pdf", "PDF")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_stem = output_dir / f"{title or file.stem}_{datetime.now(tz=UTC).isoformat()}"
    extension = FORMAT_EXTENSIONS.get(to, f".{to}")
    output_path = Path(f"{output_stem}{extension}")

    settings: dict[str, Any] = DEFAULT_SETTINGS.get(to, {}) | kwargs

    args: list[str | Path] = [
        jupyter,
        "nbconvert",
        file,
        "--output",
        output_stem,
        "--to",
        to,
    ]
    if template is not None:
        args.extend(("--template", template))
    args.extend(f"--TemplateExporter.extra_template_basedirs={basedir}" for basedir in extra_template_basedirs)
    for key, value in settings.items():
        args.append(f"--{key}")
        if value is not None:
            args.append(str(value))

    with Progress(
        SpinnerColumn(),
        TextColumn(text_format="[progress.description]{task.description}"),
        TimeElapsedColumn(),
        transient=True,
    ) as progress:
        progress.add_task(
            description="[white]Exporting...[/]",
            total=None,
        )
        subprocess.run(
            args=args,
            check=True,
        )

    return output_path
