"""Filesystem path helpers for save-path resolution and path-like detection."""

from collections.abc import Sequence
from pathlib import Path


def is_pathlike(
    path: str,
    /,
) -> bool:
    """
    Determine whether a string looks like a filesystem path.

    Returns ``True`` when *path* is absolute, contains directory separators,
    has a file extension, or is one of the special directory tokens
    (``"."`` / ``".."``)  -- i.e. anything beyond a bare filename stem.

    Parameters
    ----------
    path
        The string to inspect.

    Returns
    -------
    bool
        ``True`` if the string resembles a filesystem path, ``False``
        otherwise.

    See Also
    --------
    resolve_save_path : Full resolution pipeline that calls this helper.

    Examples
    --------
    >>> is_pathlike("/tmp/data.csv")
    True
    >>> is_pathlike("report")
    False
    >>> is_pathlike("data.csv")
    True
    >>> is_pathlike(".")
    True
    """
    p = Path(path)
    return p.is_absolute() or len(p.parts) > 1 or p.suffix != "" or path in {".", ".."}


def resolve_save_path(
    path: Path | str | None,
    /,
    *,
    suffixes: Sequence[str] = (),
    overwrite: bool = True,
    default_directory: Path,
    default_name: str,
    default_suffix: str,
) -> tuple[Path, set[str]]:
    """
    Resolve a user-supplied path into a stem ``Path`` and a set of valid suffixes.

    Normalises ``Path``, ``str``, or ``None`` inputs against a set of defaults
    so callers can write files without worrying about missing directories,
    extensions, or accidental overwrites.

    Parameters
    ----------
    path
        User-supplied save location.  ``Path`` objects are used as-is; plain
        strings are tested with `is_pathlike` to decide whether they are full
        paths or bare names; ``None`` falls back to the default location.
    suffixes
        Extra file extensions to accept (without leading dot).
    overwrite
        If ``False``, raise when a target file already exists.
    default_directory
        Directory to use when *path* is ``None`` or a bare name.
    default_name
        Filename stem used when *path* is ``None`` or a directory.
    default_suffix
        Fallback extension when no suffix can be inferred from *path*
        or *suffixes*.

    Returns
    -------
    Path
        The resolved stem (without extension).
    set[str]
        Normalised suffixes (lower-case, no leading dot).

    Raises
    ------
    FileExistsError
        If *overwrite* is ``False`` and a candidate file already exists.

    See Also
    --------
    is_pathlike : Helper used to classify bare strings vs. paths.

    Examples
    --------
    >>> from pathlib import Path
    >>> stem, suffixes = resolve_save_path(
    ...     None,
    ...     default_directory=Path("reports"),
    ...     default_name="out",
    ...     default_suffix="csv",
    ... )
    >>> stem.parent.name, stem.name
    ('reports', 'out')
    >>> sorted(suffixes)
    ['csv']
    """
    valid_suffixes = {suffix.lower().lstrip(".") for suffix in suffixes}

    if isinstance(path, Path):
        resolved = path

    elif isinstance(path, str):
        resolved = Path(path) if is_pathlike(path) else default_directory / path

    else:
        resolved = default_directory / default_name

    if resolved.suffix:
        valid_suffixes.add(resolved.suffix.lower().lstrip("."))
        resolved = resolved.with_suffix(suffix="")
    elif resolved.is_dir():
        resolved = resolved / default_name

    if not valid_suffixes:
        valid_suffixes = {default_suffix.lower().lstrip(".")}

    if not overwrite:
        for suffix in valid_suffixes:
            candidate = resolved.with_suffix(suffix=f".{suffix}")
            if candidate.exists():
                msg = f"File already exists: {candidate} and overwrite is set to False."
                raise FileExistsError(msg)

    return resolved, valid_suffixes
