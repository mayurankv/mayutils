"""Command-line entry point for refreshing local pyright type stubs.

This module exposes a Typer application that inspects the project-local
``typings/`` directory, identifies the third-party packages for which
hand-curated or previously generated stubs already exist, confirms that
the packages still need external stubs (i.e. they do not ship a
``py.typed`` marker themselves and no community ``types-<pkg>`` stub is
installed), regenerates their stubs via ``pyright --createstub`` and
then tidies the result with ``ruff check --fix`` followed by
``ruff format`` so the emitted ``.pyi`` files conform to the project's
lint and formatting rules. It is intended to be run after a dependency
bump so that local stub files stay in sync with the installed package
signatures.
"""

from __future__ import annotations

import importlib.util
import subprocess
from importlib.metadata import distributions
from pathlib import Path

from mayutils.core.extras import may_require_extras

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
    from typer import Argument, Exit, Option, Typer


app = Typer()
console = Console()


def ships_py_typed(
    package: str,
    /,
) -> bool:
    """Return ``True`` when ``package`` ships a PEP 561 ``py.typed`` marker.

    Parameters
    ----------
    package : str
        Top-level importable name of the package to inspect.

    Returns
    -------
    bool
        ``True`` if the installed package declares itself typed, ``False``
        otherwise (including when the package cannot be located).
    """
    spec = importlib.util.find_spec(name=package)
    if spec is None:
        return False

    locations = list(spec.submodule_search_locations or ())
    if not locations and spec.origin is not None:
        locations = [str(Path(spec.origin).parent)]

    return any((Path(location) / "py.typed").is_file() for location in locations)


def types_package_installed(
    package: str,
    /,
) -> bool:
    """Return ``True`` when a community ``types-<package>`` stub package is installed.

    Parameters
    ----------
    package : str
        Top-level importable name of the runtime package.

    Returns
    -------
    bool
        ``True`` if a sibling distribution named ``types-<package>`` (any
        case, hyphen / underscore insensitive) is resolvable via
        :func:`importlib.metadata.distributions`, ``False`` otherwise.
    """
    target = f"types-{package.replace('_', '-')}".lower()
    return any((dist.metadata["Name"] or "").lower() == target for dist in distributions())


def is_installed(
    package: str,
    /,
) -> bool:
    """Return ``True`` when ``package`` is importable in the current environment.

    Parameters
    ----------
    package : str
        Top-level importable name to probe.

    Returns
    -------
    bool
        ``True`` if :func:`importlib.util.find_spec` locates the module,
        ``False`` otherwise.
    """
    return importlib.util.find_spec(name=package) is not None


def is_namespace_package(
    package: str,
    /,
) -> bool:
    """Return ``True`` when ``package`` is a PEP 420 namespace package.

    Namespace packages have no ``__init__`` module (``spec.origin is None``)
    but do expose a submodule search path. ``pyright --createstub`` refuses
    to stub such packages directly and must be invoked against each concrete
    subpackage instead.

    Parameters
    ----------
    package : str
        Dotted import name to inspect.

    Returns
    -------
    bool
        ``True`` when the import spec declares no ``origin`` yet still has
        submodule search locations, ``False`` otherwise.
    """
    spec = importlib.util.find_spec(name=package)
    return spec is not None and spec.origin is None and bool(spec.submodule_search_locations)


def expand_namespace(
    package: str,
    /,
    *,
    typings: Path,
) -> list[str]:
    """Expand a namespace package into the concrete subpackages stubbed under ``typings``.

    Parameters
    ----------
    package : str
        Top-level namespace package name.
    typings : pathlib.Path
        Root of the local stubs directory. ``typings / package`` is
        inspected for immediate child directories that correspond to
        stubbable subpackages.

    Returns
    -------
    list[str]
        Dotted names of the form ``<package>.<subpackage>`` for every
        subdirectory under ``typings / package``. Falls back to
        ``[package]`` when no subdirectories exist so pyright can still
        be invoked against the namespace directly — this succeeds for
        namespaces that effectively expose a single top-level module
        (for example ``quarto_cli``) and surfaces a pyright error for
        genuinely multi-subpackage namespaces that need their stubs
        scaffolded first.
    """
    root = typings / package
    if not root.is_dir():
        return [package]

    subs = sorted(child.name for child in root.iterdir() if child.is_dir() and not child.name.startswith(("_", ".")))
    if not subs:
        return [package]

    return [f"{package}.{sub}" for sub in subs]


def stub_packages(
    typings: Path,
    /,
) -> list[str]:
    """List top-level packages with stubs under ``typings``.

    Parameters
    ----------
    typings : pathlib.Path
        Directory searched for stub roots. Each immediate subdirectory is
        treated as a separate package; top-level ``.pyi`` files are
        reported as stand-alone modules.

    Returns
    -------
    list[str]
        Package names (directory names or the stem of a top-level
        ``.pyi`` file), sorted alphabetically and de-duplicated.
    """
    names: set[str] = set()
    for child in typings.iterdir():
        if child.is_dir() and not child.name.startswith("_") and not child.name.startswith("."):
            names.add(child.name)
        elif child.is_file() and child.suffix == ".pyi":
            names.add(child.stem)

    return sorted(names)


def run_pyright(
    package: str,
    /,
    *,
    typings: Path,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``pyright --createstub`` for ``package``.

    Parameters
    ----------
    package : str
        Top-level importable name passed to ``pyright --createstub``.
    typings : pathlib.Path
        Directory into which pyright should emit regenerated stubs. The
        command is executed with ``typings.parent`` as the working
        directory so pyright writes into ``<cwd>/typings/<package>``
        following its default convention.

    Returns
    -------
    subprocess.CompletedProcess[str]
        Result of the subprocess call, with ``stdout`` / ``stderr``
        captured for inspection by the caller.
    """
    return subprocess.run(
        args=["pyright", "--createstub", package],
        cwd=typings.parent,
        capture_output=True,
        text=True,
        check=False,
    )


def run_ruff(
    command: str,
    /,
    *args: str,
    target: Path,
) -> subprocess.CompletedProcess[str]:
    """Invoke a ``ruff`` subcommand against ``target``.

    Parameters
    ----------
    command : str
        Ruff subcommand to run (``"check"`` or ``"format"``).
    *args : str
        Additional command-line flags forwarded to ``ruff`` before the
        target path (for example ``"--fix"`` for ``ruff check``).
    target : pathlib.Path
        Path passed as the final positional argument. Passed together
        with ``--no-respect-gitignore`` and ``--force-exclude=false`` so
        that stubs living in a typings folder excluded by
        ``.gitignore`` or a ruff config are still visited.

    Returns
    -------
    subprocess.CompletedProcess[str]
        Result of the subprocess call, with ``stdout`` / ``stderr``
        captured for inspection by the caller.
    """
    return subprocess.run(
        args=[
            "ruff",
            command,
            "--no-respect-gitignore",
            *args,
            str(target),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@app.command()
def refresh(  # noqa: C901, PLR0912, PLR0915
    typings: Path = Argument(  # noqa: B008
        Path("typings"),
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        writable=True,
        resolve_path=True,
        help="Root ``typings/`` folder to refresh",
    ),
    *,
    include_typed: bool = Option(
        False,  # noqa: FBT003
        "--include-typed",
        help="Regenerate even for packages that ship their own ``py.typed``",
    ),
    dry_run: bool = Option(
        False,  # noqa: FBT003
        "--dry-run",
        "-n",
        help="List packages that would be refreshed, do not invoke pyright",
    ),
    verbose: bool = Option(
        False,  # noqa: FBT003
        "--verbose",
        "-v",
        help="Stream pyright stdout/stderr for each package",
    ),
    format_: bool = Option(
        True,  # noqa: FBT003
        "--format/--no-format",
        help="Run ``ruff check --fix`` and ``ruff format`` on the refreshed stubs",
    ),
) -> None:
    """Regenerate ``pyright`` stubs for each package already present in ``typings/``.

    Walks the top level of ``typings`` for existing stub packages, drops any
    package that no longer requires third-party stubs (either because it
    ships its own ``py.typed`` marker or because a community
    ``types-<package>`` distribution is installed), and runs
    ``pyright --createstub`` for the remainder. Packages that are no longer
    importable are reported and skipped.

    Parameters
    ----------
    typings : pathlib.Path, default ``./typings``
        Directory that holds existing stub packages, each as a subfolder.
        Typer validates that the path exists and is writable.
    include_typed : bool, default False
        When ``True`` the runtime ``py.typed`` guard is ignored and pyright
        is run for every discovered package. Useful when an upstream
        package declares itself typed but the project wants to keep local
        overrides in sync anyway.
    dry_run : bool, default False
        When ``True`` the command enumerates the work that would be done
        (including reasons for any skips) but never invokes pyright.
    verbose : bool, default False
        When ``True`` pyright's output is streamed for every package that
        succeeds; errors are always surfaced regardless of this flag.
    format_ : bool, default True
        When ``True`` (the default) each successfully regenerated stub
        folder is tidied up with ``ruff check --fix`` followed by
        ``ruff format`` so the generated ``.pyi`` files conform to the
        project's lint and formatting rules. Disable with
        ``--no-format`` when debugging generator output directly.

    Raises
    ------
    typer.Exit
        Raised without an exit code when ``typings`` contains no stub
        packages, and with code ``1`` when at least one pyright invocation
        fails.
    """
    packages = stub_packages(typings)

    if not packages:
        console.print(f"[green]No stub packages under {typings}; nothing to refresh.[/green]")
        raise Exit

    console.print(f"[blue]Discovered {len(packages)} stub package(s) under {typings}[/blue]")

    refreshable: list[str] = []
    skipped: list[tuple[str, str]] = []

    for package in packages:
        if not is_installed(package):
            skipped.append((package, "not installed"))
            continue

        if not include_typed and ships_py_typed(package):
            skipped.append((package, "ships py.typed"))
            continue

        if types_package_installed(package):
            skipped.append((package, "types-* stub installed"))
            continue

        if is_namespace_package(package):
            refreshable.extend(expand_namespace(package, typings=typings))
        else:
            refreshable.append(package)

    if skipped:
        table = Table(title=f"[yellow]Skipped {len(skipped)} package(s)[/yellow]", show_header=True)
        table.add_column(header="Package")
        table.add_column(header="Reason", style="dim")
        for package, reason in skipped:
            table.add_row(package, reason)
        console.print(table)

    if not refreshable:
        console.print("[green]All stub packages are up-to-date or unnecessary.[/green]")
        raise Exit

    action = "Would refresh" if dry_run else "Refreshing"
    console.print(f"[cyan]{action} {len(refreshable)} package(s):[/cyan] {', '.join(refreshable)}")

    if dry_run:
        raise Exit

    failures: list[tuple[str, str]] = []
    refreshed: list[str] = []

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
            description="[cyan]Running pyright --createstub...",
            total=len(refreshable),
        )

        for package in refreshable:
            progress.update(
                task_id=task,
                description=f"[bold yellow]{package}",
            )

            result = run_pyright(package, typings=typings)

            if result.returncode != 0:
                failures.append((package, result.stderr.strip() or result.stdout.strip()))
                console.print(f"[bold red]:x: {package}:[/bold red] pyright exited with {result.returncode}")
            else:
                refreshed.append(package)
                if verbose:
                    console.print(f"[green]:white_check_mark: {package}[/green]")
                    if result.stdout.strip():
                        console.print(result.stdout.rstrip())

            progress.advance(task_id=task)

    if format_ and refreshed:
        console.print(f"[cyan]Formatting {len(refreshed)} refreshed stub folder(s) with ruff...[/cyan]")
        for package in refreshed:
            target = typings.joinpath(*package.split("."))
            if not target.exists():
                continue

            check_result = run_ruff("check", "--fix", "--unsafe-fixes", target=target)
            if check_result.returncode != 0 and verbose:
                console.print(f"[yellow]ruff check {package}:[/yellow]\n{check_result.stdout.rstrip()}")

            format_result = run_ruff("format", target=target)
            if format_result.returncode != 0:
                failures.append((package, format_result.stderr.strip() or format_result.stdout.strip()))
                console.print(f"[bold red]:x: ruff format {package}:[/bold red] exited with {format_result.returncode}")
            elif verbose:
                console.print(f"[green]:sparkles: formatted {package}[/green]")

    if failures:
        console.print(f"[bold red]:warning: {len(failures)} failure(s):[/bold red]")
        for package, output in failures:
            console.print(f"[red]- {package}[/red]\n{output}")
        raise Exit(code=1)

    console.print(f"[green]:white_check_mark: Refreshed {len(refreshed)} package(s) in {typings}.[/green]")


if __name__ == "__main__":
    app()
