"""Command-line interface entry point."""

import typer
from rich.console import Console

app = typer.Typer()
console = Console()


@app.command()
def main() -> None:
    """Run the {{ cookiecutter.project_name }} command-line interface."""
    console.print("Replace this message by putting your code into {{ cookiecutter.__package_snake }}.cli.main")
    console.print("See Typer documentation at https://typer.tiangolo.com/")


if __name__ == "__main__":
    app()
