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

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable


class Unset:
    """
    Marker type for intentionally missing values.

    This class is used to signal that a value is deliberately not provided,
    so that ``None`` and other falsy values can still be passed explicitly
    without being treated as "no value supplied".

    See Also
    --------
    UNSET : Shared sentinel instance of this marker type.
    null : No-op callable used as a placeholder default.
    typing.Optional : Standard annotation when ``None`` is an acceptable value.

    Examples
    --------
    >>> from mayutils.objects.functions import UNSET, Unset
    >>> isinstance(UNSET, Unset)
    True
    >>> def f(value=UNSET):
    ...     return "default" if value is UNSET else value
    >>> f()
    'default'
    >>> f(0)
    0
    """


UNSET: Final = Unset()


class Lazy[T]:
    """
    Defer construction of a value until it is first used.

    Wraps a zero-argument ``factory`` and invokes it only the first time
    the wrapped value is accessed (via :meth:`get`, attribute access, or a
    call), caching the result for subsequent use. This is useful for
    expensive objects, or for values whose construction needs an optional
    dependency that may be absent at import time but present once the value
    is actually required. Attribute access and calls are transparently
    forwarded to the underlying value.

    Parameters
    ----------
    factory
        Zero-argument callable that builds and returns the wrapped value
        the first time it is needed. It is invoked at most once.

    See Also
    --------
    null : No-op callable used as a placeholder default.
    functools.cached_property : Standard-library equivalent for instance attributes.
    mayutils.core.extras.may_require_extras : Defers optional-dependency import errors.

    Examples
    --------
    >>> from mayutils.objects.functions import Lazy
    >>> created = []
    >>> def build():
    ...     created.append("built")
    ...     return {"ready": True}
    >>> lazy = Lazy(build)
    >>> created
    []
    >>> lazy.get()
    {'ready': True}
    >>> created
    ['built']
    """

    def __init__(
        self,
        factory: Callable[[], T],
        /,
    ) -> None:
        """
        Store the factory without invoking it.

        Records the zero-argument ``factory`` and initialises the cached
        value so that the wrapped object is constructed lazily on first
        access rather than at construction time.

        Parameters
        ----------
        factory
            Zero-argument callable that produces the wrapped value when it
            is first required.

        See Also
        --------
        Lazy.get : Materialise and cache the wrapped value.

        Examples
        --------
        >>> from mayutils.objects.functions import Lazy
        >>> lazy = Lazy(lambda: 42)
        >>> lazy.get()
        42
        """
        self._factory = factory
        self._obj: T | None = None

    def get(
        self,
    ) -> T:
        """
        Return the wrapped value, building it once on first access.

        Invokes the stored factory the first time it is called and caches
        the result, so repeated calls return the same object without
        re-running the factory.

        Returns
        -------
            The value produced by the factory, created on the first call
            and reused on every subsequent call.

        See Also
        --------
        Lazy : Container that defers construction until this method runs.

        Examples
        --------
        >>> from mayutils.objects.functions import Lazy
        >>> lazy = Lazy(lambda: [1, 2, 3])
        >>> lazy.get()
        [1, 2, 3]
        >>> lazy.get() is lazy.get()
        True
        """
        if self._obj is None:
            self._obj = self._factory()

        return self._obj

    def __getattr__(
        self,
        name: str,
    ) -> Any:  # noqa: ANN401
        """
        Forward attribute access to the wrapped value.

        Triggered only for attributes not found on the :class:`Lazy`
        wrapper itself, this materialises the wrapped value (if needed) and
        returns the requested attribute from it, so the proxy behaves like
        the underlying object for attribute lookups.

        Parameters
        ----------
        name
            Name of the attribute to retrieve from the wrapped value.

        Returns
        -------
            The attribute ``name`` resolved on the wrapped value.

        See Also
        --------
        Lazy.get : Used to materialise the value before delegating.

        Examples
        --------
        >>> from mayutils.objects.functions import Lazy
        >>> lazy = Lazy(lambda: "hello")
        >>> lazy.upper()
        'HELLO'
        """
        return getattr(self.get(), name)

    def __call__(
        self,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        """
        Invoke the wrapped value as a callable.

        Materialises the wrapped value (if needed) and calls it with the
        supplied arguments, raising :class:`TypeError` when it is not
        callable and re-raising any error from the call wrapped in a
        :class:`RuntimeError`.

        Parameters
        ----------
        *args
            Positional arguments forwarded to the wrapped callable.
        **kwargs
            Keyword arguments forwarded to the wrapped callable.

        Returns
        -------
            Whatever the wrapped callable returns for the given arguments.

        Raises
        ------
        TypeError
            If the wrapped value is not callable.
        RuntimeError
            If the wrapped callable raises during invocation.

        See Also
        --------
        Lazy.get : Used to materialise the value before calling it.

        Examples
        --------
        >>> from mayutils.objects.functions import Lazy
        >>> double = Lazy(lambda: lambda x: x * 2)
        >>> double(21)
        42
        """
        _obj = self.get()
        if not callable(_obj):
            msg = f"Lazy object of type {type(_obj).__name__} is not callable"
            raise TypeError(msg)

        try:
            return _obj(*args, **kwargs)  # ty:ignore[call-top-callable]
        except Exception as err:
            msg = f"Error calling lazy object of type {type(_obj).__name__}: {err}"
            raise RuntimeError(msg) from err


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
        key: Any,  # noqa: ANN401
        value: Any,  # noqa: ANN401
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


def set_inline[Object: SupportsSetItem](
    *,
    parent_object: Object,
    property_name: str | int,
    value: object,
) -> Object:
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
