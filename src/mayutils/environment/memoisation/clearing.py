"""
Provide cache clearing for both in-memory and persistent caches.

The single :func:`clear_cache` function orchestrates clearing of
:class:`~mayutils.environment.memoisation.memory.MemoryStore` instances
and stale persistent cache files. When ``interactive=True``, it renders
Rich progress bars and summary tables.

See Also
--------
mayutils.environment.memoisation.memory : In-memory cache backend.
mayutils.environment.memoisation.files : File-backed cache backend.
mayutils.scripts.clear_cache : Typer CLI wrapping :func:`clear_cache`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from mayutils.core.extras import may_require_extras
from mayutils.data import CACHE_FOLDER
from mayutils.environment.filesystem import is_file_stale
from mayutils.environment.memoisation.memory import clear_shared_stores

if TYPE_CHECKING:
    from collections.abc import Sequence

    from mayutils.environment.memoisation.types import CacheStore
    from mayutils.objects.datetime import Duration


def clear_cache(
    *,
    ttl: Duration | None = None,
    stores: Sequence[CacheStore[Any]] = (),
    cache_folder: Path | str = CACHE_FOLDER,
    prefix: str | None = None,
    suffix: str | None = None,
    dry_run: bool = False,
    interactive: bool = False,
) -> list[Path]:
    """
    Clear in-memory stores and remove stale persistent cache files.

    Iterates over *stores* calling :meth:`~CacheStore.clear`, then
    scans *cache_folder* for files matching the age and name filters.

    Parameters
    ----------
    ttl
        Maximum allowed age for persistent cache files. Files older
        than ``ttl`` are deleted. ``None`` deletes all files.
    stores
        :class:`MemoryStore` instances to clear.
    cache_folder
        Root directory containing persistent cache files.
    prefix
        Only delete files whose name starts with this prefix.
    suffix
        Only delete files whose extension matches this suffix.
    dry_run
        When ``True``, list files that would be deleted without
        removing them. Only meaningful when ``interactive=True``.
    interactive
        When ``True``, show Rich progress bars and a summary table.

    Returns
    -------
        Paths of persistent cache files that were deleted (or would
        be deleted in dry-run mode).

    See Also
    --------
    mayutils.environment.memoisation.memory.MemoryStore.clear : Clear
        an individual in-memory store.
    mayutils.scripts.clear_cache : Typer CLI wrapping this function.

    Examples
    --------
    >>> from mayutils.environment.memoisation.clearing import clear_cache
    >>> deleted = clear_cache(cache_folder="/nonexistent")
    >>> deleted
    []
    """
    if not dry_run:
        clear_shared_stores()
        for store in stores:
            store.clear()

    folder = Path(cache_folder)
    if not folder.is_dir():
        return []

    candidates = [
        path
        for path in folder.rglob("*")
        if path.is_file()
        and path.name != ".gitkeep"
        and (prefix is None or path.name.startswith(prefix))
        and (suffix is None or path.suffix == suffix)
        and (ttl is None or is_file_stale(path, ttl=ttl))
    ]

    if interactive:
        return _clear_interactive(
            candidates,
            dry_run=dry_run,
        )

    if not dry_run:
        for path in candidates:
            path.unlink()

    return candidates


def _clear_interactive(
    candidates: list[Path],
    /,
    *,
    dry_run: bool,
) -> list[Path]:
    """
    Delete *candidates* with Rich progress bar and summary table.

    Renders a Rich progress bar while deleting (or simulating deletion
    of) each file, then prints a summary table of affected paths.

    Parameters
    ----------
    candidates
        Paths to delete (or preview in dry-run mode).
    dry_run
        When ``True``, skip actual deletion but still report paths.

    Returns
    -------
        Paths of files that were deleted (or would be in dry-run mode).

    See Also
    --------
    clear_cache : Public entry point that delegates here.

    Examples
    --------
    >>> from mayutils.environment.memoisation.clearing import clear_cache
    >>> clear_cache(cache_folder="/nonexistent", interactive=True)
    []
    """
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

    from mayutils.visualisation.console import CONSOLE

    if not candidates:
        CONSOLE.print("[green]No files to delete![/green]")
        return []

    deleted: list[Path] = []

    with Progress(
        SpinnerColumn(style="bold blue"),
        TextColumn(text_format="[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=CONSOLE,
        transient=not dry_run,
    ) as progress:
        task = progress.add_task(
            description="[magenta]Dry run (no deletions)..." if dry_run else "[cyan]Deleting files...",
            total=len(candidates),
        )

        for path in candidates:
            progress.update(task_id=task, description=f"[bold yellow]{path.name}")

            if not dry_run and path.exists():
                path.unlink()

            deleted.append(path)
            progress.advance(task_id=task)

    action = "would be deleted" if dry_run else "deleted"
    CONSOLE.print(f"[green]{len(deleted)}[/green] file(s) {action}.")

    if deleted:
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column(header="Status", style="dim", width=12)
        table.add_column(header="File")
        state = "Would Remove" if dry_run else "Removed"

        for path in deleted:
            table.add_row(state, path.name)

        CONSOLE.print(table)

    return deleted


__all__ = [
    "clear_cache",
]
