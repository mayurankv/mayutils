"""General-purpose function helpers.

This module provides small callable utilities that are used across the
``mayutils`` code base. It exposes a structural protocol describing the
mutation contract for subscriptable containers, a no-op callable that
can be supplied wherever a function is expected but no behaviour is
desired, and a fluent helper that performs an in-place item assignment
and returns the mutated container so that calls can be chained inside
expressions.
"""

from typing import Any, Protocol


class SupportsSetItem(Protocol):
    """Structural protocol for objects supporting item assignment.

    Captures the minimal interface required by :func:`set_inline`: any
    container that implements ``__setitem__`` (for example ``dict``,
    ``list``, ``numpy.ndarray`` or a user-defined mapping).

    Methods
    -------
    __setitem__(key, value)
        Assign ``value`` under ``key`` on the underlying container.

    Examples
    --------
    >>> isinstance({}, SupportsSetItem)  # runtime_checkable not enabled
    False
    >>> hasattr({}, "__setitem__")
    True
    """

    def __setitem__(
        self,
        key: Any,  # noqa: ANN401
        value: Any,  # noqa: ANN401
        /,
    ) -> None:
        """Assign ``value`` under ``key`` on the container.

        Parameters
        ----------
        key : Any
            The index, key, or attribute-like identifier at which
            ``value`` should be stored on the container.
        value : Any
            The payload to write at ``key``.

        Returns
        -------
        None
            The assignment is performed for its side effect.
        """
        ...


def null(
    *_args: Any,  # noqa: ANN401
    **_kwargs: Any,  # noqa: ANN401
) -> None:
    """Accept any arguments, perform no work, and return ``None``.

    Provides a safe default callable for APIs that accept a function
    argument but need to guarantee a no-op when the caller has nothing
    meaningful to pass. Because every positional and keyword argument is
    discarded, ``null`` is signature-compatible with any call site.

    Parameters
    ----------
    *_args : Any
        Positional arguments forwarded by the caller. All values are
        discarded without inspection.
    **_kwargs : Any
        Keyword arguments forwarded by the caller. All values are
        discarded without inspection.

    Returns
    -------
    None
        The function always returns ``None`` regardless of inputs.

    Examples
    --------
    >>> null() is None
    True
    >>> null(1, 2, key="value") is None
    True
    """
    return


def set_inline[T: SupportsSetItem](
    *,
    parent_object: T,
    property_name: str | int,
    value: Any,  # noqa: ANN401
) -> T:
    """Perform an in-place item assignment and return the container.

    Invokes ``parent_object[property_name] = value`` via
    :meth:`object.__setitem__` and returns the same container reference.
    Because item assignment is a statement in Python and does not
    produce a value, wrapping it in this function lets callers embed the
    mutation inside expressions or fluent chains.

    Parameters
    ----------
    parent_object : T
        The container on which the assignment is performed. It must
        implement ``__setitem__`` (see :class:`SupportsSetItem`); this
        includes ``dict``, ``list``, and most mapping or sequence
        implementations. The object is mutated in place.
    property_name : str | int
        The key, index, or identifier used as the left-hand side of the
        assignment ``parent_object[property_name] = value``.
    value : Any
        The object to store at ``property_name`` on ``parent_object``.

    Returns
    -------
    T
        The same ``parent_object`` reference passed in, after the
        mutation has been applied, so that further calls can operate on
        the updated container.

    Raises
    ------
    TypeError
        Raised by the container when ``property_name`` is not a valid
        key type for that container (for example a non-integer index on
        a ``list``).
    IndexError
        Raised by sequence containers when ``property_name`` refers to
        a position outside the current range.

    Examples
    --------
    >>> set_inline(parent_object={}, property_name="k", value=1)
    {'k': 1}
    >>> container = {"a": 0}
    >>> set_inline(parent_object=container, property_name="a", value=42) is container
    True
    """
    parent_object.__setitem__(
        property_name,
        value,
    )

    return parent_object
