from typing import Any, Callable, TypeVar

D = TypeVar("D", bound=Callable[..., Any])
T = TypeVar("T", bound=Callable[..., Any])

def flexwrap(deco: D) -> D: ...
