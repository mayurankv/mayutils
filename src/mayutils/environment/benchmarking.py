import time
from functools import wraps
from typing import Any, Callable

from mayutils.objects.decorators import flexwrap
from mayutils.environment.logging import Logger

logger = Logger.spawn()


@flexwrap
def timing(
    func: Callable,
    *,
    show: bool = True,
):
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
