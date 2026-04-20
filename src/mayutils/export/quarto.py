"""Thin wrapper around the ``quarto render`` command-line interface.

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
"""

import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

DEFAULT_SETTINGS: dict[str, dict[str, Any]] = {
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
    """Locate the ``quarto`` executable bundled inside the ``quarto_cli`` wheel.

    Inspects the ``quarto_cli`` package's ``__file__`` and ``__path__``
    attributes to enumerate candidate installation roots, then returns
    the first existing ``bin/quarto`` entry found beneath one of those
    roots. Resolution is performed lazily on every call so that a
    mid-session reinstall of the optional dependency is picked up
    without requiring a module reload.

    Returns
    -------
    Path
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
    """Enumerate every Quarto output format accepted by :func:`export`.

    Reflects the keys of :data:`DEFAULT_SETTINGS`, which are kept in
    sync with Quarto's built-in Pandoc output targets. The result is
    used by :func:`export` to validate the ``to`` argument before
    spawning the subprocess.

    Returns
    -------
    tuple of str
        Format identifier strings (``"html"``, ``"pdf"``, ``"pptx"``,
        ``"revealjs"``, ...) that may be passed to :func:`export` as
        the ``to`` argument.
    """
    return tuple(DEFAULT_SETTINGS)


def list_extensions() -> tuple[dict[str, str], ...]:
    """Enumerate the Quarto extensions installed for the active project.

    Invokes ``quarto list extensions`` via :func:`subprocess.run` and
    parses the fixed three-column table (``Id``, ``Version``,
    ``Contributes``) written by Quarto to stdout or stderr. Whitespace-
    only lines are ignored and the header row is used to detect the
    "no extensions installed" case, in which an empty tuple is
    returned rather than a row describing the header.

    Returns
    -------
    tuple of dict
        One mapping per installed extension. Each mapping carries an
        ``id`` key holding the fully qualified extension identifier, a
        ``version`` key holding the semver string (or an empty string
        if the CLI omits it), and a ``contributes`` key listing the
        comma separated contribution types (``formats``, ``filters``,
        ...). Empty if Quarto reports no installed extensions.

    Raises
    ------
    RuntimeError
        Propagated from :func:`quarto_bin` when the bundled binary is
        missing.
    subprocess.CalledProcessError
        If ``quarto list extensions`` exits with a non-zero status.
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
    """Render a notebook or Quarto document via ``quarto render``.

    Builds and runs a ``quarto render`` command line against ``file``
    and writes the result into ``output_dir``. The output stem is
    composed from ``title`` (falling back to ``file.stem``) and the
    current UTC timestamp in ISO-8601 form so that repeated invocations
    never clobber a prior export. The requested output format is
    validated up front so that invalid inputs fail fast with a list of
    legal values rather than via an opaque non-zero exit from the child
    process.

    Parameters
    ----------
    file : Path
        Source notebook (``.ipynb``) or Quarto markdown document
        (``.qmd``) to render. Forwarded to ``quarto render`` as the
        positional input, so any engine and path resolution rules
        applied by the CLI also apply here.
    to : str, optional
        Target output format. Must appear in :func:`list_formats`;
        drives both the ``--to`` flag and the selection of per-format
        metadata defaults. Defaults to ``"html"``.
    title : str or None, optional
        Stem used for the output filename before the timestamp suffix
        is appended. When ``None`` the stem of ``file`` is used, which
        keeps the output name aligned with the source.
    output_dir : Path or None, optional
        Directory into which the rendered artefact is written. The
        directory is not created automatically; callers must ensure it
        exists. When ``None`` the destination is derived from ``to``
        under :data:`mayutils.export.OUTPUT_FOLDER` so each format lands
        in its own subfolder.
    metadata : dict of str to str or None, optional
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
    Path
        Absolute path of the rendered artefact. The extension is
        resolved via :data:`FORMAT_EXTENSIONS` so that formats whose
        identifier differs from their natural suffix (``markdown`` →
        ``.md``, ``revealjs`` → ``.html``, ``typst`` → ``.pdf``, ...)
        land with the correct extension instead of a literal
        ``.<to>``.

    Raises
    ------
    RuntimeError
        If the bundled ``quarto`` binary cannot be located when
        :func:`quarto_bin` is consulted.
    ValueError
        If ``to`` is not among the formats returned by
        :func:`list_formats`.
    subprocess.CalledProcessError
        If the ``quarto render`` invocation exits with a non-zero
        status, propagated from :func:`subprocess.run` under
        ``check=True``.
    """
    binary = quarto_bin()

    available_formats = list_formats()
    if to not in available_formats:
        msg = f"Unknown Quarto format {to!r}. Available: {available_formats}."
        raise ValueError(msg)

    if output_dir is None:
        output_dir = OUTPUT_FOLDER / to.title().replace("Pdf", "PDF")

    merged_metadata = DEFAULT_METADATA.get(to, {}) | (metadata or {})
    settings: dict[str, Any] = DEFAULT_SETTINGS.get(to, {}) | kwargs

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
