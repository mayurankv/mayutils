from functools import wraps, update_wrapper
from typing import Any, Callable, TypeVar


D = TypeVar("D", bound=Callable[..., Any])
T = TypeVar("T", bound=Callable[..., Any])


def flexwrap(
    deco: D,
) -> D:
    @wraps(wrapped=deco)
    def deco_wrapper(
        *args,
        **kwargs,
    ):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            func = args[0]

            return update_wrapper(
                wrapped=func,
                wrapper=deco(func),
            )
        else:
            # if args:
            #     raise TypeError("This decorator only supports keyword arguments.")

            def true_deco(
                func: T,
            ) -> T:
                decorated_func = update_wrapper(
                    wrapped=func,
                    wrapper=deco(
                        func,
                        *args,
                        **kwargs,
                    ),
                )

                return decorated_func

            return update_wrapper(
                wrapped=deco,
                wrapper=true_deco,
            )

    return deco_wrapper  # type: ignore
