"""
Wrap the ``quarto render`` command-line interface with typed helpers.

This module exposes a small, type-safe surface for discovering the
output formats and extensions registered with a local Quarto
installation and for rendering a notebook or ``.qmd`` source to any of
those formats. The helpers shell out to the ``quarto`` binary bundled
by the ``quarto_cli`` Python distribution rather than using a higher-
level Python API, so the caller's configured engines, extensions and
rendering behaviour are honoured exactly as they are on the command
line. All rendered artefacts are placed under a per-format folder
beneath :data:`mayutils.export.OUTPUT_FOLDER` with an ISO-8601 UTC
timestamp appended to the stem so that repeated exports never
overwrite previous runs.

See Also
--------
quarto-cli : Upstream Quarto command-line interface whose ``render`` and
    ``list`` subcommands back every helper exposed here.
mayutils.export.nbconvert : Sibling module that converts notebooks via
    ``nbconvert`` when Quarto is not required.
subprocess.run : Standard library primitive used to invoke the
    ``quarto`` binary located by :func:`quarto_bin`.

Examples
--------
Render a notebook to self-contained HTML using the defaults baked into
:data:`DEFAULT_METADATA` and :data:`DEFAULT_SETTINGS`:

>>> import io
>>> import tempfile
>>> from contextlib import redirect_stderr, redirect_stdout
>>> from pathlib import Path
>>> from unittest.mock import patch, MagicMock
>>> from mayutils.export.quarto import export
>>> patcher = patch("mayutils.export.quarto.subprocess.run")
>>> run = patcher.start()
>>> run.return_value = MagicMock(returncode=0)
>>> _buffer = io.StringIO()
>>> with redirect_stdout(_buffer), redirect_stderr(_buffer), tempfile.TemporaryDirectory() as tmp:
...     nb = Path(tmp) / "report.ipynb"
...     _ = nb.write_text("{}", encoding="utf-8")
...     output_dir = Path(tmp) / "out"
...     try:
...         _ = export(nb, to="html", output_dir=output_dir)
...     except RuntimeError:
...         pass
>>> run.called
True
>>> _ = patcher.stop()

Override the Quarto YAML front-matter ``title`` via ``-M``:

>>> import io
>>> import tempfile
>>> from contextlib import redirect_stderr, redirect_stdout
>>> from pathlib import Path
>>> from unittest.mock import patch, MagicMock
>>> from mayutils.export.quarto import export
>>> patcher = patch("mayutils.export.quarto.subprocess.run")
>>> run = patcher.start()
>>> run.return_value = MagicMock(returncode=0)
>>> _buffer = io.StringIO()
>>> with redirect_stdout(_buffer), redirect_stderr(_buffer), tempfile.TemporaryDirectory() as tmp:
...     nb = Path(tmp) / "report.ipynb"
...     _ = nb.write_text("{}", encoding="utf-8")
...     output_dir = Path(tmp) / "out"
...     try:
...         _ = export(nb, to="pdf", metadata={"title": "Q1 Review"}, output_dir=output_dir)
...     except RuntimeError:
...         pass
>>> run.called
True
>>> _ = patcher.stop()
"""

import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from mayutils.core.extras import may_require_extras
from mayutils.export import OUTPUT_FOLDER

with may_require_extras():
    import quarto_cli as quarto  # pyright: ignore[reportMissingTypeStubs]
    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn


DEFAULT_METADATA: dict[str, dict[str, str]] = {
    "html": {
        "theme.light": "cyborg",
        "respect-user-color-scheme": "true",
        "embed-resources": "true",
        "code-fold": "true",
        "code-tools": "true",
    },
    "pdf": {
        "pdf-engine": "xelatex",
        "toc": "true",
        "number-sections": "true",
        "colorlinks": "true",
        "fig-pos": "H",
        "highlight-style": "github",
    },
    "docx": {
        "toc": "true",
        "number-sections": "true",
        "highlight-style": "github",
    },
    "pptx": {},
    "revealjs": {
        "theme": "black",
        "code-fold": "true",
        "code-tools": "true",
    },
}
"""Per-format default ``-M key=value`` render metadata.

Keys are Quarto output format names (the value passed via ``--to``) and
values are a mapping of Quarto metadata key → value that :func:`export`
will expand into ``-M key=value`` pairs before invoking
``quarto render``. The defaults are merged with the caller-supplied
``metadata`` at call time so individual exports can override or extend a
format's baseline; mutate this dictionary in application-level bootstrap
code to change the defaults globally.
"""

DEFAULT_SETTINGS: dict[str, dict[str, object]] = {
    "asciidoc": {},
    "beamer": {},
    "context": {},
    "docx": {},
    "epub": {},
    "gfm": {},
    "html": {},
    "ipynb": {},
    "jats": {},
    "latex": {},
    "markdown": {},
    "odt": {},
    "pdf": {},
    "plain": {},
    "pptx": {},
    "revealjs": {},
    "rst": {},
    "rtf": {},
    "typst": {},
}
"""Per-format default ``quarto render`` CLI arguments.

Keys are the Quarto output format names (the value passed via ``--to``)
and values are a mapping of CLI option → value that :func:`export` will
expand into ``--key value`` (or just ``--key`` when the value is
``None``) before invoking ``quarto render``. The defaults are merged
with the caller-supplied ``**kwargs`` at call time so individual exports
can override or extend a format's baseline; mutate this dictionary in
application-level bootstrap code to change the defaults globally.
"""


def quarto_bin() -> Path:
    """
    Locate the ``quarto`` executable bundled inside the ``quarto_cli`` wheel.

    Inspects the ``quarto_cli`` package's ``__file__`` and ``__path__``
    attributes to enumerate candidate installation roots, then returns
    the first existing ``bin/quarto`` entry found beneath one of those
    roots. Resolution is performed lazily on every call so that a
    mid-session reinstall of the optional dependency is picked up
    without requiring a module reload. The returned path is the binary
    driven by :func:`subprocess.run` in :func:`list_extensions` and
    :func:`export`.

    Returns
    -------
        Absolute filesystem path to the bundled ``quarto`` binary,
        suitable for use as the first element of a
        :func:`subprocess.run` argument list.

    Raises
    ------
    RuntimeError
        If neither ``quarto_cli.__file__`` nor ``quarto_cli.__path__``
        yields a directory containing a ``bin/quarto`` executable. The
        error message includes the ``mayutils[notebook]`` extra install
        hint so the user can remediate without further lookup.

    See Also
    --------
    quarto-cli : Upstream Quarto CLI distribution whose ``bin/quarto``
        entry point is resolved here.
    mayutils.export.nbconvert : Sibling module that does not require the
        Quarto binary and therefore bypasses this helper.
    subprocess.run : Consumer of the returned path when spawning
        ``quarto render`` or ``quarto list extensions``.
    list_extensions : Sibling helper that relies on this resolution to
        call ``quarto list extensions``.
    export : Sibling helper that relies on this resolution to call
        ``quarto render`` against an input notebook or ``.qmd``.

    Examples
    --------
    Resolve the bundled binary and confirm the result is a path-like
    handle that ends in ``quarto``:

    >>> from pathlib import Path
    >>> from mayutils.export.quarto import quarto_bin
    >>> try:
    ...     binary = quarto_bin()
    ... except RuntimeError:
    ...     binary = None
    >>> binary is None or (isinstance(binary, Path) and binary.name == "quarto")
    True
    """
    package_file = getattr(quarto, "__file__", None)
    roots: list[Path] = []
    if package_file is not None:
        roots.append(Path(package_file).parent)

    roots.extend(Path(path) for path in getattr(quarto, "__path__", []))

    for root in roots:
        candidate = root / "bin" / "quarto"
        if candidate.exists():
            return candidate

    msg = (
        "The bundled 'quarto' binary could not be located within the quarto_cli package. "
        'Install it with: uv add "mayutils[notebook]" '
        '(or pip install "mayutils[notebook]").'
    )
    raise RuntimeError(msg)


def list_formats() -> tuple[str, ...]:
    """
    Enumerate every Quarto output format accepted by :func:`export`.

    Reflects the keys of :data:`DEFAULT_SETTINGS`, which are kept in
    sync with Quarto's built-in Pandoc output targets. The result is
    used by :func:`export` to validate the ``to`` argument before
    spawning the subprocess. Returning a tuple keeps the list
    immutable at the call site so downstream consumers can rely on a
    stable ordering when presenting choices to the user.

    Returns
    -------
        Format identifier strings (``"html"``, ``"pdf"``, ``"pptx"``,
        ``"revealjs"``, ...) that may be passed to :func:`export` as
        the ``to`` argument.

    See Also
    --------
    quarto-cli : Upstream Quarto CLI whose ``--to`` flag accepts the
        same identifiers surfaced here.
    mayutils.export.nbconvert : Sibling module that exposes an
        equivalent enumeration for the ``nbconvert`` backend.
    subprocess.run : Primitive invoked by :func:`export` once the
        format validated by this helper is accepted.
    export : Consumer that validates user input against the returned
        tuple before calling ``quarto render``.
    list_extensions : Companion discovery helper that introspects the
        installed Quarto extensions rather than supported formats.

    Examples
    --------
    Pick a format interactively before rendering:

    >>> from mayutils.export.quarto import list_formats
    >>> "html" in list_formats()
    True
    >>> sorted(list_formats())[:3]
    ['asciidoc', 'beamer', 'context']
    """
    return tuple(DEFAULT_SETTINGS)


def list_extensions() -> tuple[dict[str, str], ...]:
    r"""
    Enumerate the Quarto extensions installed for the active project.

    Invokes ``quarto list extensions`` via :func:`subprocess.run` and
    parses the fixed three-column table (``Id``, ``Version``,
    ``Contributes``) written by Quarto to stdout or stderr. Whitespace-
    only lines are ignored and the header row is used to detect the
    "no extensions installed" case, in which an empty tuple is
    returned rather than a row describing the header. Parsing is done
    in pure Python rather than via a Quarto JSON flag to stay
    compatible with the shipping CLI, whose plain-text output is the
    only stable contract across point releases.

    Returns
    -------
        One mapping per installed extension. Each mapping carries an
        ``id`` key holding the fully qualified extension identifier, a
        ``version`` key holding the semver string (or an empty string
        if the CLI omits it), and a ``contributes`` key listing the
        comma separated contribution types (``formats``, ``filters``,
        ...). Empty if Quarto reports no installed extensions.

    See Also
    --------
    quarto-cli : Upstream Quarto CLI whose ``list extensions``
        subcommand is shelled out here.
    mayutils.export.nbconvert : Sibling module whose ``nbconvert``
        backend does not require Quarto extensions.
    subprocess.run : Standard library primitive used to execute
        ``quarto list extensions``.
    quarto_bin : Helper that locates the binary passed as the first
        argument to :func:`subprocess.run`.
    list_formats : Companion discovery helper that enumerates
        supported output formats rather than installed extensions.

    Examples
    --------
    Discover installed extensions before driving :func:`export`:

    >>> from unittest.mock import patch, MagicMock
    >>> from mayutils.export.quarto import list_extensions
    >>> stdout = "Id                          Version  Contributes\\nquarto-ext/fontawesome      1.0.0    shortcodes\\n"
    >>> bin_patcher = patch("mayutils.export.quarto.quarto_bin")
    >>> run_patcher = patch("mayutils.export.quarto.subprocess.run")
    >>> bin_ = bin_patcher.start()
    >>> run = run_patcher.start()
    >>> bin_.return_value = "/fake/quarto"
    >>> run.return_value = MagicMock(returncode=0, stdout=stdout, stderr="")
    >>> installed = list_extensions()
    >>> run.called
    True
    >>> any(ext["id"].startswith("quarto-ext/") for ext in installed)
    True
    >>> _ = bin_patcher.stop()
    >>> _ = run_patcher.stop()
    """
    binary = quarto_bin()
    result = subprocess.run(
        args=[binary, "list", "extensions"],
        check=True,
        capture_output=True,
        text=True,
    )
    raw = result.stdout or result.stderr
    lines = [line.rstrip() for line in raw.splitlines() if line.strip()]
    if not lines or lines[0].split()[:2] != ["Id", "Version"]:
        return ()

    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        parts = line.split(maxsplit=2)
        if not parts:
            continue
        rows.append(
            {
                "id": parts[0],
                "version": parts[1] if len(parts) > 1 else "",
                "contributes": parts[2].strip() if len(parts) > 2 else "",  # noqa: PLR2004
            },
        )
    return tuple(rows)


def export(
    file: Path,
    /,
    *,
    to: str = "html",
    title: str | None = None,
    output_dir: Path | None = None,
    metadata: dict[str, str] | None = None,
    **kwargs: str | bool | Path,
) -> Path:
    """
    Render a notebook or Quarto document via ``quarto render``.

    Builds and runs a ``quarto render`` command line against ``file``
    and writes the result into ``output_dir``. The output stem is
    composed from ``title`` (falling back to ``file.stem``) and the
    current UTC timestamp in ISO-8601 form so that repeated invocations
    never clobber a prior export. The requested output format is
    validated up front so that invalid inputs fail fast with a list of
    legal values rather than via an opaque non-zero exit from the child
    process. Rendering runs inside a symlink-populated temporary
    directory so that Quarto's YAML front matter, sidecar assets and
    per-notebook caches resolve exactly as they would on disk without
    polluting the source tree.

    Parameters
    ----------
    file
        Source notebook (``.ipynb``) or Quarto markdown document
        (``.qmd``) to render. Forwarded to ``quarto render`` as the
        positional input, so any engine and path resolution rules
        applied by the CLI also apply here.
    to
        Target output format. Must appear in :func:`list_formats`;
        drives both the ``--to`` flag and the selection of per-format
        metadata defaults. Defaults to ``"html"``.
    title
        Stem used for the output filename before the timestamp suffix
        is appended. When ``None`` the stem of ``file`` is used, which
        keeps the output name aligned with the source.
    output_dir
        Directory into which the rendered artefact is written. The
        directory is not created automatically; callers must ensure it
        exists. When ``None`` the destination is derived from ``to``
        under :data:`mayutils.export.OUTPUT_FOLDER` so each format lands
        in its own subfolder.
    metadata
        Caller-supplied ``-M key=value`` overrides layered on top of
        :data:`DEFAULT_METADATA` for the chosen ``to``. Pass an empty
        mapping to keep only the format defaults; pass ``None`` to
        apply the defaults unmodified.
    **kwargs
        Additional ``quarto render`` options. Each ``key=value`` pair
        is expanded to ``--key value`` on the command line (and to a
        bare ``--key`` flag when ``value`` is ``None``). Caller-
        supplied kwargs are layered on top of
        ``DEFAULT_SETTINGS[to]`` so callers can override or extend
        format-specific defaults without touching the global table.
        Non-identifier CLI names (e.g. ``no-input``, ``execute`` or
        ``no-execute``) can be passed by splatting a dictionary:
        ``export(file, **{"no-input": None})``.

    Returns
    -------
        Absolute path of the rendered artefact. The extension is
        resolved by inspecting the file Quarto actually emitted so that
        formats whose identifier differs from their natural suffix
        (``markdown`` produces ``.md``, ``revealjs`` produces
        ``.html``, ``typst`` produces ``.pdf``, ...) land with the
        correct extension instead of a literal ``.<to>``.

    Raises
    ------
    RuntimeError
        If no rendered artefact matching ``file.stem`` is produced
        inside the temporary render directory.
    ValueError
        If ``to`` is not among the formats returned by
        :func:`list_formats`.

    See Also
    --------
    quarto-cli : Upstream Quarto CLI whose ``render`` subcommand is the
        workhorse behind this helper.
    mayutils.export.nbconvert : Sibling module that exposes an
        equivalent ``nbconvert``-backed pipeline without the Quarto
        dependency.
    subprocess.run : Standard library primitive used to invoke
        ``quarto render`` under ``check=True``.
    quarto_bin : Sibling helper that resolves the ``quarto`` binary
        driven by :func:`subprocess.run`.
    list_formats : Sibling helper that enumerates the legal values for
        the ``to`` argument validated here.
    list_extensions : Sibling helper that introspects the Quarto
        extensions available to the render engine.

    Examples
    --------
    Render a notebook to HTML with the default theme and embedded
    resources:

    >>> import io
    >>> import tempfile
    >>> from contextlib import redirect_stderr, redirect_stdout
    >>> from pathlib import Path
    >>> from unittest.mock import patch, MagicMock
    >>> from mayutils.export.quarto import export
    >>> patcher = patch("mayutils.export.quarto.subprocess.run")
    >>> run = patcher.start()
    >>> run.return_value = MagicMock(returncode=0)
    >>> _buffer = io.StringIO()
    >>> with redirect_stdout(_buffer), redirect_stderr(_buffer), tempfile.TemporaryDirectory() as tmp:
    ...     nb = Path(tmp) / "report.ipynb"
    ...     _ = nb.write_text("{}", encoding="utf-8")
    ...     output_dir = Path(tmp) / "out"
    ...     try:
    ...         _ = export(nb, to="html", output_dir=output_dir)
    ...     except RuntimeError:
    ...         pass
    >>> run.called
    True
    >>> _ = patcher.stop()

    Render the same source to PDF, override the YAML front-matter
    ``title`` and disable code echoes:

    >>> import io
    >>> import tempfile
    >>> from contextlib import redirect_stderr, redirect_stdout
    >>> from pathlib import Path
    >>> from unittest.mock import patch, MagicMock
    >>> from mayutils.export.quarto import export
    >>> patcher = patch("mayutils.export.quarto.subprocess.run")
    >>> run = patcher.start()
    >>> run.return_value = MagicMock(returncode=0)
    >>> _buffer = io.StringIO()
    >>> with redirect_stdout(_buffer), redirect_stderr(_buffer), tempfile.TemporaryDirectory() as tmp:
    ...     nb = Path(tmp) / "report.ipynb"
    ...     _ = nb.write_text("{}", encoding="utf-8")
    ...     output_dir = Path(tmp) / "out"
    ...     try:
    ...         _ = export(
    ...             nb,
    ...             to="pdf",
    ...             title="Q1-Review",
    ...             metadata={"title": "Q1 Review", "subtitle": "Risk"},
    ...             output_dir=output_dir,
    ...             **{"no-input": None},
    ...         )
    ...     except RuntimeError:
    ...         pass
    >>> run.called
    True
    >>> _ = patcher.stop()
    """
    binary = quarto_bin()

    available_formats = list_formats()
    if to not in available_formats:
        msg = f"Unknown Quarto format {to!r}. Available: {available_formats}."
        raise ValueError(msg)

    if output_dir is None:
        output_dir = OUTPUT_FOLDER / to.title().replace("Pdf", "PDF")

    merged_metadata = DEFAULT_METADATA.get(to, {}) | (metadata or {})
    settings: dict[str, object] = DEFAULT_SETTINGS.get(to, {}) | kwargs

    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mayutils-quarto-") as tmp:
        render_dir = Path(tmp)
        for sibling in file.parent.iterdir():
            if sibling != file and sibling.stem == file.stem:
                continue
            (render_dir / sibling.name).symlink_to(sibling.resolve())

        args: list[str | Path] = [
            binary,
            "render",
            file.name,
            "--to",
            to,
        ]
        for key, value in merged_metadata.items():
            args.extend(("-M", f"{key}={value}"))
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
                cwd=render_dir,
            )

        rendered_candidates = sorted(
            (child for child in render_dir.iterdir() if child.is_file() and not child.is_symlink() and child.stem == file.stem),
            key=lambda child: child.stat().st_mtime,
            reverse=True,
        )
        if not rendered_candidates:
            msg = (
                f"Could not locate a rendered artefact for {file.name!r} with stem {file.stem!r} "
                f"in the temporary render directory. Check the quarto output for errors."
            )
            raise RuntimeError(msg)
        rendered = rendered_candidates[0]

        output_path = output_dir / f"{title or file.stem}_{datetime.now(tz=UTC).isoformat()}{rendered.suffix}"

        if output_path.exists():
            output_path.unlink()

        shutil.move(src=rendered, dst=output_path)

    return output_path
