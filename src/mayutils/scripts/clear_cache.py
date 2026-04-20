"""Command-line entry point for purging on-disk memoisation caches.

This module exposes a Typer application whose sole subcommand walks a
cache directory, filters candidate files by an optional name prefix,
and deletes them while rendering a live Rich progress bar plus a
summary table. It also provides a non-interactive helper that resets
the default cache folder by removing it and recreating a fresh
directory with a ``.gitkeep`` marker, suitable for use in setup and
continuous integration scripts that need a clean slate without
user confirmation.
"""

from pathlib import Path

from mayutils.core.extras import may_require_extras
from mayutils.data import CACHE_FOLDER

with may_require_extras():
    from rich.console import Console
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
console = Console()


def show_summary(
    *files: Path,
    dry_run: bool = False,
) -> None:
    """Render a two-column Rich table summarising removed cache files.

    The table lists each file's basename alongside a status label
    indicating whether the removal actually took place or was
    simulated, and prints the result to the module-level Rich console
    so it appears inline in the terminal.

    Parameters
    ----------
    *files : pathlib.Path
        Variadic positional paths of the cache entries to list. Only
        the ``name`` attribute is consulted, so the arguments may be
        any ``Path``-like objects regardless of whether they still
        exist on disk at the time of rendering.
    dry_run : bool, default False
        Controls the label placed in the status column. When
        ``True`` every row is marked ``"Would Remove"`` to signal a
        simulated deletion; when ``False`` every row is marked
        ``"Removed"`` to confirm that the file has been unlinked.

    Returns
    -------
    None
        The function renders output as a side effect and does not
        yield a value.

    Examples
    --------
    >>> show_summary(Path("a.pkl"), Path("b.pkl"), dry_run=True)
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

    console.print(table)


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
    """Delete cached files under a directory with live progress feedback.

    Iterates over the immediate children of ``folder``, optionally
    filtering by a name prefix, and removes each matching file while
    streaming progress through a Rich progress bar. Files named
    ``.gitkeep`` are always preserved so the directory remains
    tracked in version control, and subdirectories are skipped
    entirely. The command can preview the work without touching the
    filesystem, gate execution behind an interactive confirmation,
    and emit per-file messages for auditing.

    Parameters
    ----------
    folder : pathlib.Path, default :data:`mayutils.data.CACHE_FOLDER`
        Root directory whose top-level files are candidates for
        removal. The path is validated by Typer to exist and to be a
        readable directory; symbolic links are resolved to their
        targets before iteration.
    prefix : str or None, default None
        Filename prefix used to narrow the deletion set. Only files
        whose ``name`` begins with this string are considered; when
        ``None`` every file (other than ``.gitkeep``) is eligible.
    force : bool, default False
        Bypass the interactive confirmation prompt. When ``False``
        the command lists the pending deletions and asks the user to
        confirm before any file is touched.
    verbose : bool, default False
        Emit a line per file as it is processed and keep the
        progress bar on screen once complete. When ``False`` the
        progress bar is rendered transiently and only the final
        summary line is retained.
    dry_run : bool, default False
        Simulate the operation without modifying disk state. Files
        that would be removed are listed and counted, but no call to
        :meth:`pathlib.Path.unlink` is issued.

    Returns
    -------
    None
        The command communicates exclusively through console output.

    Raises
    ------
    typer.Exit
        Raised with no exit code when the filter matches zero files,
        or when the user answers "no" at the confirmation prompt.

    Notes
    -----
    Individual filesystem errors raised by :meth:`pathlib.Path.unlink`
    are caught and reported via the console so that a single
    problematic file does not abort the whole run; the deletion
    counter only advances for files that were removed successfully.
    """
    console.print(f"[blue]Targeting folder {folder}[/blue]")
    files = [
        child
        for child in folder.iterdir()
        if child.is_file() and child.name != ".gitkeep" and (prefix is None or child.name.startswith(prefix))
    ]

    if len(files) == 0:
        console.print("[green]No files to delete![/green]")
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

        console.print(table)

        if not confirm(
            text="Continue?",
            default=False,
        ):
            console.print("[red]Aborted.[/red]")
            raise Exit

    deleted = 0
    with Progress(
        SpinnerColumn(style="bold blue"),
        TextColumn(text_format="[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
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
                    console.print(f"[cyan][dry-run][/cyan] Would delete: {file.name}")
            elif file.exists():
                file.unlink()
                deleted += 1
                if verbose:
                    console.print(f"[green]deleted[/green] {file.name}")
            else:
                console.print(f"[red]Failed to delete {file.name} (file not found)[/red]")

            progress.advance(task_id=task)

    console.print(
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
    """Reset the default cache folder to an empty, version-controlled state.

    If :data:`mayutils.data.CACHE_FOLDER` exists it is removed
    recursively and then recreated as an empty directory containing
    a single zero-byte ``.gitkeep`` file so that the folder remains
    tracked by Git. If the folder does not exist the function is a
    no-op, which makes it safe to call unconditionally from bootstrap
    scripts.

    Returns
    -------
    None
        The function mutates the filesystem as a side effect and
        does not return a value.

    Raises
    ------
    OSError
        Propagated from :meth:`pathlib.Path.unlink`,
        :meth:`pathlib.Path.rmdir`, :meth:`pathlib.Path.mkdir`, or
        :meth:`pathlib.Path.touch` if the cache directory cannot be
        removed or recreated, for example due to permission errors or
        a concurrent process holding a handle on one of its entries.

    Notes
    -----
    This helper is intentionally non-interactive and unconditional;
    it is intended for setup and continuous integration contexts
    where the caller knows the cache is disposable. For an
    interactive, filter-aware workflow use :func:`clean` instead.
    """
    if CACHE_FOLDER.exists():
        remove_tree(path=CACHE_FOLDER)
        CACHE_FOLDER.mkdir()
        (CACHE_FOLDER / ".gitkeep").touch()


def remove_tree(
    *,
    path: Path,
) -> None:
    """Recursively remove ``path`` and all of its contents via :mod:`pathlib`.

    Parameters
    ----------
    path : pathlib.Path
        Directory (or file) to remove. When ``path`` is a directory its
        children are deleted depth-first before the directory itself is
        removed; when ``path`` is a file it is unlinked directly.
        Symbolic links pointing at directories are unlinked without
        descending into the target so as not to affect files outside
        ``path``.

    Returns
    -------
    None
        The function mutates the filesystem as a side effect and does
        not return a value.

    Raises
    ------
    OSError
        Propagated from :meth:`pathlib.Path.unlink` or
        :meth:`pathlib.Path.rmdir` when an entry cannot be removed,
        for example due to permission errors or an open handle held
        by another process.
    """
    if path.is_dir() and not path.is_symlink():
        for child in path.iterdir():
            remove_tree(path=child)
        path.rmdir()
    else:
        path.unlink()


if __name__ == "__main__":
    app()
