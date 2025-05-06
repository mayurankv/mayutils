from functools import update_wrapper, wraps
from inspect import isclass
from typing import Any, Callable


def flexwrap(
    decorator: Callable | None = None,
    *,
    keyword_only=True,
) -> Callable:
    def make_wrapper(
        deco: Callable,
    ) -> Callable:
        @wraps(wrapped=deco)
        def outer(
            *args,
            **kwargs,
        ) -> Any:
            # Case 1: Used as @deco (no args, gets func directly)
            if len(args) == 1 and callable(args[0]) and not kwargs:
                return deco(args[0])  # Call with no args

            # Case 2: Used as @deco(...) (with args)
            if keyword_only and args:
                raise TypeError("This decorator only supports keyword arguments.")

            def true_deco(
                func: Callable,
            ) -> Callable:
                # @wraps()
                return deco(
                    func,
                    *args,
                    **kwargs,
                )

            return true_deco

        return outer

    if decorator is not None and callable(decorator):
        if isclass(object=decorator):
            pass
            # setattr(
            #     decorator,
            #     "__annotations__",
            #     getattr(
            #         decorator.__init__,
            #         "__annotations__",
            #         {},
            #     ),
            # )

            # update_wrapper(
            #     wrapper=self,
            #     wrapped=func,
            # )

        return make_wrapper(deco=decorator)

    else:
        return make_wrapper
