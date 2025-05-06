import os
from pathlib import Path
from typing import Optional
import shutil
import typer
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.console import Console
from rich.table import Table

from mayutils.data.read import CACHE_FOLDER

app = typer.Typer()
console = Console()


def show_summary(
    files,
    dry_run=False,
) -> None:
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
def clean(
    folder: Path = typer.Argument(
        CACHE_FOLDER,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Target folder",
    ),
    prefix: Optional[str] = typer.Option(
        None,
        "--prefix",
        "-p",
        help="Only delete files starting with this prefix",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show all filenames as they're deleted",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="List files that would be deleted, do not delete",
    ),
) -> None:
    files = [
        child
        for child in folder.iterdir()
        if child.is_file()
        and child.name != ".gitkeep"
        and (prefix is None or child.name.startswith(prefix))
    ]

    if len(files) == 0:
        console.print("[green]No files to delete![/green]")
        raise typer.Exit()

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

        if not typer.confirm(
            text="Continue?",
            default=False,
        ):
            console.print("[red]Aborted.[/red]")
            raise typer.Exit()

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
            description="[cyan]Deleting files..."
            if not dry_run
            else "[magenta]Dry run (no deletions)...",
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
            else:
                try:
                    os.remove(path=file)
                    deleted += 1
                    if verbose:
                        console.print(f"[green]deleted[/green] {file.name}")
                except Exception as err:
                    console.print(
                        f"[bold red]:x: Error deleting {file}: {err}[/bold red]"
                    )

            progress.advance(task_id=task)

    console.print(
        f"[yellow]:test_tube: Dry-run Complete:[/yellow] [cyan]{len(files)}[/cyan] file(s) would be deleted."
        if dry_run
        else f"[green]:white_check_mark: Complete:[/green] [cyan]{deleted}[/cyan] file(s) deleted."
    )

    if verbose and (dry_run or deleted):
        show_summary(
            files=files,
            dry_run=dry_run,
        )


def clear_cache() -> None:
    if os.path.exists(path=CACHE_FOLDER):
        shutil.rmtree(CACHE_FOLDER)
        os.mkdir(path=CACHE_FOLDER)
        open(file=CACHE_FOLDER / ".gitkeep", mode="a").close()
        print(f"Cache at '{CACHE_FOLDER}' has been cleared.")
    else:
        print(f"No cache found at '{CACHE_FOLDER}'.")


def main() -> None:
    app()


if __name__ == "__main__":
    app()
    # clear_cache()
