import builtins
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional
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
    print_method: Optional[Callable] = None,
) -> Generator[None, Any, None]:
    # base_print = (
    #     __builtins__["print"] if isinstance(__builtins__, dict) else __builtins__.print
    # )
    base_print = print
    original = builtins.print
    builtins.print = print_method if print_method is not None else base_print
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
