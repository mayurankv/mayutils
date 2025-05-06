from typing import Any, Callable, NoReturn


class classonlyproperty:
    def __init__(
        self,
        func,
    ) -> None:
        self.func = func

    def __get__(
        self,
        instance: object,
        owner: type,
    ) -> Any:
        if instance is not None:
            raise AttributeError(
                "This property is only accessible on the class, not instances."
            )
        return self.func(owner)


class readonlyclassonlyproperty(classonlyproperty):
    def __set__(
        self,
        instance: object,
        value: Any,
    ) -> NoReturn:
        raise AttributeError("Can't set read-only class property.")


class BaseClass:
    def __repr__(
        self,
    ) -> str:
        return super().__repr__()


def add_method(
    cls,
    method: Callable,
    method_name: str = "__post_init__",
) -> Any:
    previous_method = getattr(
        cls,
        method_name,
        lambda self: None,
    )

    def new_method(
        self,
        *args,
        **kwargs,
    ) -> Any:
        old_value = previous_method(
            self,
            *args,
            **kwargs,
        )
        return (
            method(
                self,
                *args,
                **kwargs,
            )
            or old_value
        )

    setattr(
        cls,
        method_name,
        new_method,
    )

    return cls
