"""
Provide a command-line entry point for purging on-disk memoisation caches.

This module exposes a Typer application whose sole subcommand walks a
cache directory, filters candidate files by an optional name prefix,
and deletes them while rendering a live Rich progress bar plus a
summary table. It also provides a non-interactive helper that resets
the default cache folder by removing it and recreating a fresh
directory with a ``.gitkeep`` marker, suitable for use in setup and
continuous integration scripts that need a clean slate without
user confirmation.

See Also
--------
typer : CLI framework used to declare the ``clean`` subcommand.
mayutils.environment.memoisation : Produces the on-disk artefacts that
    this script is designed to remove.
pathlib : Standard library module used to discover and unlink the cache
    entries on disk.
mayutils.scripts.refresh_stubs : Sibling script that rebuilds cached
    type stubs after the cache has been cleared.

Examples
--------
Invoke the Typer application from the shell to clean the default cache
folder interactively::

    $ python -m mayutils.scripts.clear_cache --dry-run
    $ python -m mayutils.scripts.clear_cache --prefix model_ --force
"""

from pathlib import Path

from mayutils.core.extras import may_require_extras
from mayutils.data import CACHE_FOLDER
from mayutils.visualisation.console import CONSOLE

with may_require_extras():
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Table
    from typer import Argument, Exit, Option, Typer, confirm

app = Typer()


def show_summary(
    *files: Path,
    dry_run: bool = False,
) -> None:
    """
    Render a two-column Rich table summarising removed cache files.

    The table lists each file's basename alongside a status label
    indicating whether the removal actually took place or was
    simulated, and prints the result to the module-level Rich console
    so it appears inline in the terminal. The helper is invoked by the
    ``clean`` subcommand in verbose mode once the deletion pass has
    finished, giving operators a tidy audit trail of what was touched.

    Parameters
    ----------
    *files
        Variadic positional paths of the cache entries to list. Only
        the ``name`` attribute is consulted, so the arguments may be
        any ``Path``-like objects regardless of whether they still
        exist on disk at the time of rendering.
    dry_run
        Controls the label placed in the status column. When
        ``True`` every row is marked ``"Would Remove"`` to signal a
        simulated deletion; when ``False`` every row is marked
        ``"Removed"`` to confirm that the file has been unlinked.

    See Also
    --------
    clean : Typer subcommand that calls this helper after it has
        iterated over the cache folder.
    typer : CLI framework whose ``confirm`` prompt gates whether the
        deletions this table reports actually take place.
    mayutils.environment.memoisation : Produces the files whose removal
        is summarised here.
    pathlib.Path : Type of the ``files`` arguments rendered by the table.

    Examples
    --------
    Render a simulated summary for two cache artefacts:

    >>> import io
    >>> from contextlib import redirect_stdout
    >>> from pathlib import Path
    >>> _buf = io.StringIO()
    >>> with redirect_stdout(_buf):
    ...     show_summary(Path("model_v1.pkl"), Path("model_v2.pkl"), dry_run=True)
    >>> "model_v1.pkl" in _buf.getvalue()
    True
    """
    table = Table(
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column(
        header="Status",
        style="dim",
        width=10,
    )
    table.add_column(
        header="File",
    )

    state = "Would Remove" if dry_run else "Removed"
    for file in files:
        table.add_row(state, file.name)

    CONSOLE.print(table)


@app.command()
def clean(  # noqa: C901
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
    force: bool = Option(
        False,  # noqa: FBT003
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
    verbose: bool = Option(
        False,  # noqa: FBT003
        "--verbose",
        "-v",
        help="Show all filenames as they're deleted",
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

    Iterates over the immediate children of ``folder``, optionally
    filtering by a name prefix, and removes each matching file while
    streaming progress through a Rich progress bar. Files named
    ``.gitkeep`` are always preserved so the directory remains
    tracked in version control, and subdirectories are skipped
    entirely. The command can preview the work without touching the
    filesystem, gate execution behind an interactive confirmation,
    and emit per-file messages for auditing. This combination lets
    operators reclaim disk space confidently while retaining enough
    telemetry to diagnose unexpected cache growth.

    Parameters
    ----------
    folder
        Root directory whose top-level files are candidates for
        removal. The path is validated by Typer to exist and to be a
        readable directory; symbolic links are resolved to their
        targets before iteration.
    prefix
        Filename prefix used to narrow the deletion set. Only files
        whose ``name`` begins with this string are considered; when
        ``None`` every file (other than ``.gitkeep``) is eligible.
        Exposed as ``--prefix``/``-p`` on the command line.
    force
        Bypass the interactive confirmation prompt. When ``False``
        the command lists the pending deletions and asks the user to
        confirm before any file is touched. Exposed as
        ``--force``/``-f`` on the command line.
    verbose
        Emit a line per file as it is processed and keep the
        progress bar on screen once complete. When ``False`` the
        progress bar is rendered transiently and only the final
        summary line is retained. Exposed as ``--verbose``/``-v`` on
        the command line.
    dry_run
        Simulate the operation without modifying disk state. Files
        that would be removed are listed and counted, but no call to
        :meth:`pathlib.Path.unlink` is issued. Exposed as
        ``--dry-run``/``-n`` on the command line.

    Raises
    ------
    typer.Exit
        Raised with no exit code when the filter matches zero files,
        or when the user answers "no" at the confirmation prompt.

    See Also
    --------
    show_summary : Helper used in verbose mode to render the final
        per-file table.
    clear_cache : Non-interactive counterpart that wipes the default
        cache folder without prompting.
    typer : CLI framework whose ``Argument``, ``Option``, ``confirm``,
        and ``Exit`` primitives drive this subcommand.
    mayutils.environment.memoisation : Produces the on-disk artefacts
        that this command deletes.
    pathlib.Path : Backs the iteration, prefix matching, and unlinking
        performed by the subcommand.
    mayutils.scripts.refresh_stubs : Sibling script that is typically
        run after clearing the cache to rebuild type stubs.

    Notes
    -----
    Individual filesystem errors raised by :meth:`pathlib.Path.unlink`
    are caught and reported via the console so that a single
    problematic file does not abort the whole run; the deletion
    counter only advances for files that were removed successfully.

    Examples
    --------
    Preview every file that would be removed from the default cache::

        $ python -m mayutils.scripts.clear_cache --dry-run

    Delete only files prefixed with ``model_`` without prompting::

        $ python -m mayutils.scripts.clear_cache --prefix model_ --force

    Run against a custom folder with verbose per-file output::

        $ python -m mayutils.scripts.clear_cache /tmp/my_cache --verbose
    """
    CONSOLE.print(f"[blue]Targeting folder {folder}[/blue]")
    files = [
        child
        for child in folder.iterdir()
        if child.is_file() and child.name != ".gitkeep" and (prefix is None or child.name.startswith(prefix))
    ]

    if len(files) == 0:
        CONSOLE.print("[green]No files to delete![/green]")
        raise Exit

    if not force:
        action = "would be deleted" if dry_run else "will be deleted"

        table = Table(title=f"{len(files)} Files {action} in [bold]{folder}[/bold]")
        table.add_column(
            header="File",
            justify="left",
        )

        for file in files:
            table.add_row(file.name)

        CONSOLE.print(table)

        if not confirm(
            text="Continue?",
            default=False,
        ):
            CONSOLE.print("[red]Aborted.[/red]")
            raise Exit

    deleted = 0
    with Progress(
        SpinnerColumn(style="bold blue"),
        TextColumn(text_format="[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=CONSOLE,
        transient=not verbose,
    ) as progress:
        task = progress.add_task(
            description="[cyan]Deleting files..." if not dry_run else "[magenta]Dry run (no deletions)...",
            total=len(files),
        )

        for file in files:
            progress.update(
                task_id=task,
                description=f"[bold yellow]{file.name}",
            )

            if dry_run:
                if verbose:
                    CONSOLE.print(f"[cyan][dry-run][/cyan] Would delete: {file.name}")
            elif file.exists():
                file.unlink()
                deleted += 1
                if verbose:
                    CONSOLE.print(f"[green]deleted[/green] {file.name}")
            else:
                CONSOLE.print(f"[red]Failed to delete {file.name} (file not found)[/red]")

            progress.advance(task_id=task)

    CONSOLE.print(
        f"[yellow]:test_tube: Dry-run Complete:[/yellow] [cyan]{len(files)}[/cyan] file(s) would be deleted."
        if dry_run
        else f"[green]:white_check_mark: Complete:[/green] [cyan]{deleted}[/cyan] file(s) deleted."
    )

    if verbose and (dry_run or deleted):
        show_summary(
            *files,
            dry_run=dry_run,
        )


def clear_cache() -> None:
    """
    Reset the default cache folder to an empty, version-controlled state.

    If :data:`mayutils.data.CACHE_FOLDER` exists it is removed
    recursively and then recreated as an empty directory containing
    a single zero-byte ``.gitkeep`` file so that the folder remains
    tracked by Git. If the folder does not exist the function is a
    no-op, which makes it safe to call unconditionally from bootstrap
    scripts. The recreation step ensures downstream tooling that
    expects the directory to be present does not have to special-case
    a missing path after a purge. Any :class:`OSError` raised by the
    underlying :mod:`pathlib` calls, for example from permission
    errors or a concurrent process holding a handle on one of the
    entries, propagates to the caller unmodified.

    See Also
    --------
    remove_tree : Depth-first recursive deletion helper used to empty
        the cache folder before it is recreated.
    clean : Interactive Typer subcommand that offers a filter-aware
        alternative to the blanket reset performed here.
    typer : CLI framework exposing the sibling ``clean`` command.
    mayutils.environment.memoisation : Produces the on-disk artefacts
        that this helper wipes.
    pathlib.Path : Backs the ``exists``, ``mkdir`` and ``touch`` calls
        that recreate the directory skeleton.
    mayutils.scripts.refresh_stubs : Sibling script typically executed
        after this helper to regenerate cached type stubs.

    Notes
    -----
    This helper is intentionally non-interactive and unconditional;
    it is intended for setup and continuous integration contexts
    where the caller knows the cache is disposable. For an
    interactive, filter-aware workflow use :func:`clean` instead.

    Examples
    --------
    Reset the cache from a Python bootstrap script::

        >>> from mayutils.scripts.clear_cache import clear_cache
        >>> clear_cache()

    Invoke from the shell as part of a CI pipeline::

        $ python -c "from mayutils.scripts.clear_cache import clear_cache; clear_cache()"
    """
    if CACHE_FOLDER.exists():
        remove_tree(path=CACHE_FOLDER)
        CACHE_FOLDER.mkdir()
        (CACHE_FOLDER / ".gitkeep").touch()


def remove_tree(
    *,
    path: Path,
) -> None:
    """
    Recursively remove ``path`` and all of its contents via :mod:`pathlib`.

    Walks the directory tree depth-first, unlinking every file and
    then removing each directory once its children have been cleared.
    Symbolic links to directories are unlinked in place rather than
    traversed so that files located outside ``path`` cannot be
    collaterally destroyed. The function deliberately relies only on
    :mod:`pathlib` primitives so it can be reasoned about without
    pulling in :mod:`shutil` semantics for error handling or follow-
    symlinks behaviour.

    Parameters
    ----------
    path
        Directory (or file) to remove. When ``path`` is a directory its
        children are deleted depth-first before the directory itself is
        removed; when ``path`` is a file it is unlinked directly.
        Symbolic links pointing at directories are unlinked without
        descending into the target so as not to affect files outside
        ``path``. Any :class:`OSError` raised by the underlying
        :meth:`pathlib.Path.unlink` or :meth:`pathlib.Path.rmdir`
        calls, for example due to permission errors or an open handle
        held by another process, propagates to the caller unmodified.

    See Also
    --------
    clear_cache : Public helper that composes this utility with a
        subsequent directory recreation step.
    clean : Interactive Typer subcommand that deletes individual cache
        files rather than a whole subtree.
    typer : CLI framework used by the sibling ``clean`` subcommand.
    mayutils.environment.memoisation : Produces the on-disk artefacts
        typically removed by calling this helper on the cache folder.
    pathlib.Path : Supplies the ``iterdir``, ``is_dir``, ``is_symlink``,
        ``rmdir`` and ``unlink`` primitives used here.
    mayutils.scripts.refresh_stubs : Sibling script run alongside cache
        maintenance to refresh generated type stubs.

    Examples
    --------
    Remove a throwaway directory from a test fixture:

    >>> import tempfile
    >>> from pathlib import Path
    >>> from mayutils.scripts.clear_cache import remove_tree
    >>> _tmp = Path(tempfile.mkdtemp())
    >>> _sub = _tmp / "child"
    >>> _sub.mkdir()
    >>> _ = (_sub / "file.txt").write_text("data")
    >>> remove_tree(path=_tmp)
    >>> _tmp.exists()
    False
    """
    if path.is_dir() and not path.is_symlink():
        for child in path.iterdir():
            remove_tree(path=child)
        path.rmdir()
    else:
        path.unlink()


if __name__ == "__main__":
    app()
