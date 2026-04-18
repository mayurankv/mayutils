"""General-purpose function helpers — ``null`` no-op and in-place ``set_inline`` setter."""

from typing import Any, Protocol, TypeVar


class _SupportsSetItem(Protocol):
    """Minimal protocol for objects with ``__setitem__`` (dict, list, etc.)."""

    def __setitem__(self, key: Any, value: Any, /) -> None: ...  # noqa: ANN401


T = TypeVar(name="T", bound=_SupportsSetItem)


def null(
    *_args: Any,  # noqa: ANN401
    **_kwargs: Any,  # noqa: ANN401
) -> None:
    """No-op that accepts any arguments and returns ``None``.

    Useful as a default callable when a parameter expects a function
    but the caller wants no-op behaviour.

    Parameters
    ----------
    *args
        Ignored.
    **kwargs
        Ignored.

    Returns
    -------
    None
        Always ``None``.

    Examples
    --------
    >>> null() is None
    True
    >>> null(1, 2, key="value") is None
    True
    """
    return


def set_inline(
    *,
    parent_object: T,
    property_name: str,
    value: Any,  # noqa: ANN401
) -> T:
    """Assign ``parent_object[property_name] = value`` in place and return ``parent_object``.

    Wraps :meth:`object.__setitem__` so that a mutation can be chained
    with other calls in a fluent style.

    Parameters
    ----------
    parent_object : T
        The container to mutate. Must support ``__setitem__`` (e.g.
        ``dict``, ``list``).
    property_name : str
        The key to set on ``parent_object``.
    value : Any
        The new value.

    Returns
    -------
    T
        ``parent_object`` after the mutation, so the caller can chain
        further operations on the same reference.

    Examples
    --------
    >>> set_inline({}, "k", 1)
    {'k': 1}
    """
    parent_object.__setitem__(
        property_name,
        value,
    )

    return parent_object
