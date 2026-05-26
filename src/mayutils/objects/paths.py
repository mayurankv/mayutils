from collections.abc import Sequence
from pathlib import Path


def is_pathlike(
    path: str,
    /,
) -> bool:
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
