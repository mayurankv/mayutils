import time
from functools import wraps
from typing import Any, Callable, Optional

from mayutils.objects.decorators import flexwrap
from mayutils.environment.logging import Logger

logger = Logger.spawn()


@flexwrap
def timing(
    func: Optional[Callable] = None,
    *,
    show: bool = True,
):
    if func is None:
        raise ValueError("No function provided")
    @wraps(wrapped=func)
    def wrapper(
        *args,
        **kwargs,
    ) -> Any:
        start = time.perf_counter()

        result = func(
            *args,
            **kwargs,
        )

        end = time.perf_counter()

        length = end - start

        logger.log(
            f"{func.__name__} took {length:.4f} seconds",
            show=show,
        )

        return result

    return wrapper
