"""Descriptor and mixin primitives for class-level attributes and fluent APIs.

This module collects small, dependency-free building blocks used elsewhere
in :mod:`mayutils` to give classes richer behaviour than the built-in
descriptors provide. It exposes a property descriptor variant that is
reachable only on the class itself, a read-only refinement of that
descriptor, a shared :class:`BaseClass` anchor for lightweight mixins,
and helpers that compose methods onto existing classes — either by
chaining extensions through a ``prior_value`` pipeline or by rewriting
inherited methods to return ``self`` so the subclass gains a fluent
builder-style interface.
"""

from collections.abc import Callable
from functools import wraps
from types import FunctionType
from typing import Any, NoReturn, Protocol


class ChainedMethod[T, V](Protocol):
    """Protocol for a method extension that observes or augments a prior return value.

    Implementations are invoked with the owning instance, any positional
    and keyword arguments passed by the caller, and the previously
    computed return value supplied via the ``prior_value`` keyword.
    Returning ``None`` signals that the prior value should be preserved
    unchanged; any other value replaces it.

    Parameters
    ----------
    T
        The type of the instance that owns the chained method.
    V
        The type of the value produced by the prior method link, and
        therefore the type this extension may return as a replacement.
    """

    def __call__(
        self,
        self_obj: T,
        *args: Any,  # noqa: ANN401
        prior_value: V | None,
        **kwargs: Any,  # noqa: ANN401
    ) -> V | None:
        """Run the extension against ``self_obj``, optionally replacing ``prior_value``.

        Parameters
        ----------
        self_obj : T
            The instance the chained method is being invoked on; takes
            the place of ``self`` because the protocol is structural
            rather than a bound method.
        *args : Any
            Positional arguments forwarded from the outer call site to
            every link in the chain.
        prior_value : V or None
            The value returned by the previous link in the chain, or
            ``None`` when this extension is the first link or when the
            previous link produced no value.
        **kwargs : Any
            Keyword arguments forwarded from the outer call site,
            excluding ``prior_value`` which is supplied by the chaining
            machinery.

        Returns
        -------
        V or None
            A value to replace ``prior_value`` in downstream links, or
            ``None`` to leave ``prior_value`` unchanged.
        """
        ...


class classonlyproperty[V]:  # noqa: N801
    """Descriptor exposing a computed attribute only through the class itself.

    Behaves like the built-in :class:`property` when the attribute is
    read off the owning class, but raises :class:`AttributeError` if an
    instance tries to read it. This is useful for metadata that
    conceptually belongs to the class — names, registries, schema
    identifiers — and should not vary across instances nor be
    reachable through them.

    Parameters
    ----------
    V
        The type produced by the wrapped getter when the descriptor is
        read from the class.

    Examples
    --------
    >>> class Foo:
    ...     @classonlyproperty
    ...     def name(cls) -> str:
    ...         return cls.__name__
    >>> Foo.name
    'Foo'
    """

    def __init__(
        self,
        func: Callable[..., V],
    ) -> None:
        """Store the class-level getter that backs this descriptor.

        Parameters
        ----------
        func : Callable[..., V]
            The callable invoked when the descriptor is accessed; it
            receives the owning class as its sole argument and must
            return the value to expose as the property.
        """
        self.func = func

    def __get__(
        self,
        instance: object,
        owner: type[Any],
    ) -> V:
        """Resolve the descriptor to the getter's return value, rejecting instance access.

        Parameters
        ----------
        instance : object
            The instance through which the attribute is being accessed;
            ``None`` when the access happens on the class directly, and
            any non-``None`` value causes this descriptor to refuse the
            lookup.
        owner : type
            The class that owns the descriptor and is passed to the
            wrapped getter to compute the returned value.

        Returns
        -------
        V
            The value produced by calling the wrapped getter with
            ``owner``.

        Raises
        ------
        AttributeError
            If ``instance`` is not ``None``, i.e. the descriptor was
            read via an instance rather than via the class itself.
        """
        if instance is not None:
            msg = "This property is only accessible on the class, not instances."
            raise AttributeError(msg)

        return self.func(owner)


class readonlyclassonlyproperty[V](classonlyproperty[V]):  # noqa: N801
    """Read-only variant of :class:`classonlyproperty` that forbids assignment.

    Inherits the class-only access semantics from
    :class:`classonlyproperty` and additionally defines ``__set__`` so
    that assigning to the attribute — including via the class itself —
    always raises :class:`AttributeError`. Use this when the computed
    value must remain immutable at the class level.

    Parameters
    ----------
    V
        The type produced by the wrapped getter, forwarded unchanged to
        :class:`classonlyproperty`.
    """

    def __set__(
        self,
        instance: object,
        value: Any,  # noqa: ANN401
    ) -> NoReturn:
        """Refuse every assignment attempt so the attribute stays read-only.

        Parameters
        ----------
        instance : object
            The object being mutated; ignored because the descriptor
            never accepts writes from either the class or an instance.
        value : Any
            The value the caller attempted to bind; ignored for the
            same reason.

        Raises
        ------
        AttributeError
            Unconditionally, to indicate the attribute cannot be set.
        """
        msg = "Can't set read-only class property."
        raise AttributeError(msg)


class BaseClass:
    """Shared anchor type for lightweight mixins defined elsewhere in the package.

    Carries no behaviour of its own. Subclasses (and mixin utilities
    such as :func:`add_method` and :func:`adopt_super_methods`) use it
    as a stable attachment point so that generated methods and
    descriptors can rely on a predictable MRO root.
    """


def add_method[T, V](
    cls: type[T],
    method: ChainedMethod[T, V],
    method_name: str,
) -> type[T]:
    """Attach a chained method to a class, composing with any existing binding.

    When ``cls`` already exposes an attribute at ``method_name``, the
    existing callable is invoked first and its return value is threaded
    into ``method`` via the ``prior_value`` keyword. If ``method``
    returns ``None`` the original return is preserved, allowing the
    extension to observe or side-effect without overwriting the prior
    result. When no attribute exists yet, ``method`` runs with
    ``prior_value=None`` and its return value is used directly.

    Parameters
    ----------
    cls : type
        The class that will be mutated in place to host the new
        attribute; also returned to support decorator-style chaining.
    method : ChainedMethod
        The extension to install. It must accept the owning instance,
        arbitrary positional and keyword arguments, and a
        ``prior_value`` keyword carrying the previous link's return.
    method_name : str
        The attribute name on ``cls`` under which the composed callable
        is stored, replacing any current binding with the chained
        version.

    Returns
    -------
    type
        ``cls`` itself, with the composed method bound at
        ``method_name``, so the function can be used as a decorator or
        in a pipeline.
    """
    previous_method = getattr(cls, method_name, None)

    @wraps(wrapped=method)
    def new_method(
        self: T,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        prior = previous_method(self, *args, **kwargs) if previous_method is not None else None
        result = method(self, *args, prior_value=prior, **kwargs)

        return prior if result is None else result

    setattr(cls, method_name, new_method)

    return cls


def adopt_super_methods[T](
    cls: type[T],
    /,
) -> type[T]:
    """Rewrite inherited methods on ``cls`` so they return ``self`` for fluent chaining.

    Walks the immediate base of ``cls`` and, for every non-dunder
    attribute that is a plain function and is not already overridden
    on ``cls`` itself, installs a wrapper that forwards to the base
    implementation via ``super`` and then returns the receiving
    instance. The result is that the subclass gains a builder-style
    API without having to re-declare each inherited method.

    Parameters
    ----------
    cls : type
        The subclass to decorate; its ``__dict__`` is extended with
        chain-returning wrappers for every eligible base-class method,
        and the class is returned to support decorator use.

    Returns
    -------
    type
        ``cls`` with the newly attached wrappers; the original base
        methods remain reachable through ``super()``.

    Examples
    --------
    >>> class Base:
    ...     def foo(self): ...
    ...     def bar(self): ...
    >>> @adopt_super_methods
    ... class Sub(Base):
    ...     pass
    >>> Sub().foo().bar() is not None
    True
    """
    base_cls = cls.__base__

    for name in dir(base_cls):
        if name.startswith("__"):
            continue

        base_method = getattr(base_cls, name)
        if not isinstance(base_method, FunctionType):
            continue

        if name in cls.__dict__:
            continue

        def make_wrapper(
            method_name: str,
            base_method: Callable[..., Any],
        ) -> Callable[..., T]:
            """Build a wrapper that delegates to a base-class method and returns ``self``.

            Parameters
            ----------
            method_name : str
                The attribute name on the base class whose bound method
                the wrapper resolves via ``super`` at call time.
            base_method : Callable[..., Any]
                The underlying function object, used as the target for
                :func:`functools.wraps` so that metadata such as
                ``__name__`` and ``__doc__`` propagate to the wrapper.

            Returns
            -------
            Callable[..., T]
                A wrapper accepting the same arguments as
                ``base_method`` that invokes the base implementation
                and returns the receiving instance.
            """

            @wraps(wrapped=base_method)
            def wrapper(
                self: T,
                *args: Any,  # noqa: ANN401
                **kwargs: Any,  # noqa: ANN401
            ) -> T:
                """Invoke the base method on ``self`` and return ``self`` for chaining.

                Parameters
                ----------
                self : T
                    The instance whose base-class implementation is
                    invoked via ``super`` and which is returned so
                    calls can be chained.
                *args : Any
                    Positional arguments forwarded verbatim to the
                    base-class method.
                **kwargs : Any
                    Keyword arguments forwarded verbatim to the
                    base-class method.

                Returns
                -------
                T
                    The instance ``self``, enabling a fluent
                    builder-style call sequence.
                """
                getattr(super(cls, self), method_name)(*args, **kwargs)
                return self

            return wrapper

        setattr(
            cls,
            name,
            make_wrapper(
                method_name=name,
                base_method=base_method,
            ),
        )

    return cls
