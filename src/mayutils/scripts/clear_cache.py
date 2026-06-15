"""
Provide a command-line entry point for purging on-disk memoisation caches.

Thin Typer wrapper around
:func:`mayutils.environment.memoisation.clearing.clear_cache`.

See Also
--------
mayutils.environment.memoisation.clearing : Core clearing logic.

Examples
--------
::

    $ python -m mayutils.scripts.clear_cache --dry-run
    $ python -m mayutils.scripts.clear_cache --prefix model_ --force
"""

from pathlib import Path

from mayutils.core.extras import may_require_extras
from mayutils.data import CACHE_FOLDER
from mayutils.environment.memoisation.clearing import clear_cache

with may_require_extras():
    from typer import Argument, Option, Typer

app = Typer()


@app.command()
def clean(
    folder: Path = Argument(  # noqa: B008
        CACHE_FOLDER,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Target folder",
    ),
    *,
    prefix: str | None = Option(
        None,
        "--prefix",
        "-p",
        help="Only delete files starting with this prefix",
    ),
    suffix: str | None = Option(
        None,
        "--suffix",
        "-s",
        help="Only delete files ending with this suffix",
    ),
    force: bool = Option(
        False,  # noqa: FBT003
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
    dry_run: bool = Option(
        False,  # noqa: FBT003
        "--dry-run",
        "-n",
        help="List files that would be deleted, do not delete",
    ),
) -> None:
    """
    Delete cached files under a directory with live progress feedback.

    Optionally filters by prefix and suffix, and supports a dry-run mode
    that lists files without deleting them.

    Parameters
    ----------
    folder
        Target directory containing cached files.
    prefix
        Only delete files starting with this prefix.
    suffix
        Only delete files ending with this suffix.
    force
        Skip the interactive confirmation prompt.
    dry_run
        List files that would be deleted without actually deleting.

    Raises
    ------
    Exit
        When the user declines the confirmation prompt.

    See Also
    --------
    mayutils.environment.memoisation.clearing.clear_cache : Core
        clearing logic invoked by this command.

    Examples
    --------
    ::

        $ python -m mayutils.scripts.clear_cache --dry-run
        $ python -m mayutils.scripts.clear_cache --prefix model_ --force
    """
    with may_require_extras():
        from typer import Exit, confirm

    if not force and not dry_run and not confirm(text=f"Delete cache files in {folder}?", default=False):
        raise Exit

    clear_cache(
        cache_folder=folder,
        prefix=prefix,
        suffix=suffix,
        dry_run=dry_run,
        interactive=True,
    )


if __name__ == "__main__":
    app()
