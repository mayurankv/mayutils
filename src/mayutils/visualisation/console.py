import builtins
from contextlib import contextmanager
from typing import Any, Generator
from unicodeit import replace
from rich import pretty, traceback
from rich import print as rprint


PRINT = builtins.print

def console_latex(
    latex: str,
) -> str:
    return replace(f=latex)


@contextmanager
def replace_print(
    print_method,
) -> Generator[None, Any, None]:
    original = builtins.print
    builtins.print = print_method
    try:
        yield
    finally:
        builtins.print = original


def setup_printing() -> None:
    builtins.print = rprint
    traceback.install(
        # console=CONSOLE,
    )
    pretty.install(
        # console=CONSOLE,
    )
