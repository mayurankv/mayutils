from functools import wraps
from types import FunctionType
from typing import Any, Callable, NoReturn, Type


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


def adopt_super_methods(
    cls: Type,
) -> Type:
    base_cls = cls.__base__

    for name in dir(base_cls):
        if name.startswith("__"):
            continue

        base_method = getattr(base_cls, name)
        if not isinstance(base_method, FunctionType):
            continue

        # Skip if subclass already overrides this method
        if name in cls.__dict__:
            continue

        def make_wrapper(method_name, base_method):
            @wraps(base_method)
            def wrapper(self, *args, **kwargs):
                getattr(super(cls, self), method_name)(*args, **kwargs)
                return self

            return wrapper

        setattr(cls, name, make_wrapper(name, base_method))

    return cls
