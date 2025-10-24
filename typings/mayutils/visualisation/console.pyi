from _typeshed import Incomplete
from contextlib import contextmanager
from typing import Any, Callable, Generator

PRINT: Incomplete

def console_latex(latex: str) -> str: ...
@contextmanager
def replace_print(
    print_method: Callable | None = None,
) -> Generator[None, Any, None]: ...
def setup_printing() -> None: ...
