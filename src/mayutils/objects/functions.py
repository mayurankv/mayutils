"""
Provide general-purpose function helpers.

This module exposes small callable utilities that are used across the
``mayutils`` code base. It defines a structural protocol describing the
mutation contract for subscriptable containers, a no-op callable that
can be supplied wherever a function is expected but no behaviour is
desired, and a fluent helper that performs an in-place item assignment
and returns the mutated container so that calls can be chained inside
expressions.

See Also
--------
functools.partial : Bind a subset of arguments to create a specialised callable.
inspect.signature : Inspect callable parameter signatures at runtime.
functools.reduce : Compose repeated applications of a binary callable.

Examples
--------
>>> from mayutils.objects.functions import null, set_inline
>>> null("ignored")
>>> set_inline(parent_object={}, property_name="x", value=1)
{'x': 1}
"""

from typing import Protocol


class SupportsSetItem(Protocol):
    """
    Describe the structural protocol for objects supporting item assignment.

    Captures the minimal interface required by :func:`set_inline`: any
    container that implements ``__setitem__`` (for example ``dict``,
    ``list``, ``numpy.ndarray`` or a user-defined mapping). Using a
    :class:`typing.Protocol` lets :func:`set_inline` accept any duck-typed
    container without requiring a shared base class, mirroring the way
    :func:`inspect.signature` describes callable shape.

    Methods
    -------
    __setitem__(key, value)
        Assign ``value`` under ``key`` on the underlying container.

    See Also
    --------
    set_inline : Apply an item assignment and return the mutated container.
    functools.partial : Pre-bind a subscript target before mutation.
    inspect.signature : Inspect the signature of ``__setitem__`` at runtime.

    Examples
    --------
    >>> hasattr({}, "__setitem__")
    True
    >>> hasattr([0, 1], "__setitem__")
    True
    """

    def __setitem__(
        self,
        key: object,
        value: object,
        /,
    ) -> None:
        """
        Assign ``value`` under ``key`` on the container.

        Defines the contract used by :func:`set_inline`: implementations
        perform the assignment for its side effect and must accept
        positional-only ``key`` and ``value`` arguments. The method
        returns no value because item assignment in Python is a
        statement rather than an expression.

        Parameters
        ----------
        key
            The index, key, or attribute-like identifier at which
            ``value`` should be stored on the container.
        value
            The payload to write at ``key``.

        See Also
        --------
        set_inline : Wrap ``__setitem__`` so the container can be returned.
        functools.partial : Bind a ``key`` to produce a specialised setter.
        inspect.signature : Inspect the binding of ``key`` and ``value``.

        Examples
        --------
        >>> container: dict[str, int] = {}
        >>> container.__setitem__("a", 1)
        >>> container
        {'a': 1}
        """
        ...


def null(
    *_args: object,
    **_kwargs: object,
) -> None:
    """
    Accept any arguments, perform no work, and return ``None``.

    Provides a safe default callable for APIs that accept a function
    argument but need to guarantee a no-op when the caller has nothing
    meaningful to pass. Because every positional and keyword argument is
    discarded, ``null`` is signature-compatible with any call site, so
    it composes freely with :func:`functools.partial` and can be bound
    as a placeholder while a signature is probed with
    :func:`inspect.signature`.

    Parameters
    ----------
    *_args
        Positional arguments forwarded by the caller. All values are
        discarded without inspection.
    **_kwargs
        Keyword arguments forwarded by the caller. All values are
        discarded without inspection.

    See Also
    --------
    set_inline : Sibling helper returning its container after mutation.
    functools.partial : Bind leading arguments to ``null`` for composition.
    inspect.signature : Inspect the variadic signature accepted by ``null``.
    functools.reduce : Fold ``null`` across a sequence as a no-op callback.

    Examples
    --------
    >>> null() is None
    True
    >>> null(1, 2, key="value") is None
    True
    >>> from functools import partial
    >>> bound = partial(null, "ignored")
    >>> bound(flag=True) is None
    True
    """
    return


def set_inline[T: SupportsSetItem](
    *,
    parent_object: T,
    property_name: str | int,
    value: object,
) -> T:
    """
    Perform an in-place item assignment and return the container.

    Invokes ``parent_object[property_name] = value`` via
    :meth:`object.__setitem__` and returns the same container reference.
    Because item assignment is a statement in Python and does not
    produce a value, wrapping it in this function lets callers embed the
    mutation inside expressions or fluent chains, for example when
    composing callables with :func:`functools.partial` or folding state
    updates through :func:`functools.reduce`.

    Parameters
    ----------
    parent_object
        The container on which the assignment is performed. It must
        implement ``__setitem__`` (see :class:`SupportsSetItem`); this
        includes ``dict``, ``list``, and most mapping or sequence
        implementations. The object is mutated in place.
    property_name
        The key, index, or identifier used as the left-hand side of the
        assignment ``parent_object[property_name] = value``.
    value
        The object to store at ``property_name`` on ``parent_object``.

    Returns
    -------
        The same ``parent_object`` reference passed in, after the
        mutation has been applied, so that further calls can operate on
        the updated container.

    See Also
    --------
    SupportsSetItem : Structural protocol enforced on ``parent_object``.
    null : Sibling no-op callable for signature-compatible defaults.
    functools.partial : Bind ``parent_object`` to specialise the setter.
    functools.reduce : Fold ``set_inline`` across key/value pairs.
    inspect.signature : Inspect the keyword-only signature of this helper.

    Examples
    --------
    >>> set_inline(parent_object={}, property_name="k", value=1)
    {'k': 1}
    >>> container = {"a": 0}
    >>> set_inline(parent_object=container, property_name="a", value=42) is container
    True
    >>> from functools import reduce
    >>> pairs = [("x", 1), ("y", 2)]
    >>> reduce(
    ...     lambda acc, item: set_inline(parent_object=acc, property_name=item[0], value=item[1]),
    ...     pairs,
    ...     {},
    ... )
    {'x': 1, 'y': 2}
    """
    parent_object.__setitem__(
        property_name,
        value,
    )

    return parent_object
