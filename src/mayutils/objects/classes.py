"""
Provide descriptor and mixin primitives for class-level attributes and fluent APIs.

This module collects small, dependency-free building blocks used
elsewhere in :mod:`mayutils` to give classes richer behaviour than the
built-in descriptors provide. It exposes a property descriptor variant
that is reachable only on the class itself, a read-only refinement of
that descriptor, a shared :class:`BaseClass` anchor for lightweight
mixins, and helpers that compose methods onto existing classes either by
chaining extensions through a ``prior_value`` pipeline or by rewriting
inherited methods to return ``self`` so the subclass gains a fluent
builder-style interface.

See Also
--------
functools.singledispatch : Companion pattern for dispatching by type.
abc.ABC : Base class for defining abstract class factory patterns.
mayutils.objects.decorators : Sibling module with decorator helpers.
mayutils.objects.functions : Sibling module with function-level utilities.

Examples
--------
>>> from mayutils.objects.classes import BaseClass, classonlyproperty
>>> class Registry(BaseClass):
...     @classonlyproperty
...     def label(cls) -> str:
...         return cls.__name__
>>> Registry.label
'Registry'
"""

from collections.abc import Callable
from functools import wraps
from types import FunctionType
from typing import NoReturn, Protocol


class ChainedMethod[T, V](Protocol):
    """
    Describe the shape of a method extension threading a prior return value.

    Implementations are invoked with the owning instance, any positional
    and keyword arguments passed by the caller, and the previously
    computed return value supplied via the ``prior_value`` keyword.
    Returning ``None`` signals that the prior value should be preserved
    unchanged; any other value replaces it. The generic parameters ``T``
    and ``V`` bind at the type level only and describe the owning
    instance type and the return value type respectively.

    See Also
    --------
    add_method : Installs a chained method onto a class.
    functools.singledispatch : Companion pattern for dispatching by type.
    typing.Protocol : Base class enabling structural subtyping.

    Examples
    --------
    >>> from mayutils.objects.classes import ChainedMethod
    >>> def extension(self_obj, *, prior_value=None) -> int:
    ...     return (prior_value or 0) + 1
    >>> isinstance(extension, object)
    True
    """

    def __call__(
        self,
        self_obj: T,
        *args: object,
        prior_value: V | None,
        **kwargs: object,
    ) -> V | None:
        """
        Run the extension against ``self_obj``, optionally replacing ``prior_value``.

        Forwards any positional and keyword arguments received by the
        outer call site to the underlying implementation, while exposing
        the previous link's return through the ``prior_value`` keyword.
        The return semantics are intentionally tri-state: a non-``None``
        value supersedes ``prior_value`` in later links, whereas
        ``None`` leaves ``prior_value`` intact.

        Parameters
        ----------
        self_obj
            The instance the chained method is being invoked on; takes
            the place of ``self`` because the protocol is structural
            rather than a bound method.
        *args
            Positional arguments forwarded from the outer call site to
            every link in the chain.
        prior_value
            The value returned by the previous link in the chain, or
            ``None`` when this extension is the first link or when the
            previous link produced no value.
        **kwargs
            Keyword arguments forwarded from the outer call site,
            excluding ``prior_value`` which is supplied by the chaining
            machinery.

        Returns
        -------
            A value to replace ``prior_value`` in downstream links, or
            ``None`` to leave ``prior_value`` unchanged.

        See Also
        --------
        add_method : Installs an implementation of this protocol.
        ChainedMethod : Enclosing protocol this method belongs to.
        functools.singledispatch : Related dispatch-by-type pattern.

        Examples
        --------
        >>> def extension(self_obj, *, prior_value=None) -> int:
        ...     return (prior_value or 0) + 1
        >>> extension(object(), prior_value=2)
        3
        """
        ...


class classonlyproperty[V]:  # noqa: N801
    """
    Expose a computed attribute reachable only through the class itself.

    Behaves like the built-in :class:`property` when the attribute is
    read off the owning class, but raises :class:`AttributeError` if an
    instance tries to read it. This is useful for metadata that
    conceptually belongs to the class, such as names, registries or
    schema identifiers, and should not vary across instances nor be
    reachable through them. The generic parameter ``V`` captures the
    value type produced by the wrapped getter for static checkers.

    Parameters
    ----------
    func
        The callable invoked when the descriptor is accessed; it
        receives the owning class as its sole argument and must return
        the value to expose as the property.

    See Also
    --------
    readonlyclassonlyproperty : Read-only refinement of this descriptor.
    builtins.property : Standard library descriptor this mimics.
    abc.ABC : Base class often paired with class-level metadata.

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
        """
        Store the class-level getter that backs this descriptor.

        Captures the callable passed at decoration time so that future
        lookups via :meth:`__get__` can forward the owning class to it.
        No other state is created; instances of the descriptor are
        intended to live on the class body as a lightweight wrapper.

        Parameters
        ----------
        func
            The callable invoked when the descriptor is accessed; it
            receives the owning class as its sole argument and must
            return the value to expose as the property.

        See Also
        --------
        classonlyproperty.__get__ : Performs the class-only access check.
        builtins.property : Standard library descriptor this mimics.
        readonlyclassonlyproperty : Read-only refinement of this descriptor.

        Examples
        --------
        >>> def getter(cls) -> str:
        ...     return cls.__name__
        >>> descriptor = classonlyproperty(getter)
        >>> descriptor.func is getter
        True
        """
        self.func = func

    def __get__(
        self,
        instance: object,
        owner: type,
    ) -> V:
        """
        Resolve the descriptor to the getter's return, rejecting instance access.

        When Python invokes the descriptor protocol, ``instance`` is
        ``None`` for class-level reads and a concrete object for
        instance-level reads. The implementation uses that distinction
        to raise :class:`AttributeError` for instance access and to
        forward ``owner`` into the wrapped getter otherwise, which
        enforces the class-only semantics advertised by the class.

        Parameters
        ----------
        instance
            The instance through which the attribute is being accessed;
            ``None`` when the access happens on the class directly, and
            any non-``None`` value causes this descriptor to refuse the
            lookup.
        owner
            The class that owns the descriptor and is passed to the
            wrapped getter to compute the returned value.

        Returns
        -------
            The value produced by calling the wrapped getter with
            ``owner``.

        Raises
        ------
        AttributeError
            If ``instance`` is not ``None``, i.e. the descriptor was
            read via an instance rather than via the class itself.

        See Also
        --------
        classonlyproperty : Enclosing descriptor defining this protocol.
        readonlyclassonlyproperty : Read-only refinement of this descriptor.
        builtins.property : Standard library descriptor this mimics.

        Examples
        --------
        >>> class Foo:
        ...     @classonlyproperty
        ...     def name(cls) -> str:
        ...         return cls.__name__
        >>> Foo.name
        'Foo'
        """
        if instance is not None:
            msg = "This property is only accessible on the class, not instances."
            raise AttributeError(msg)

        return self.func(owner)


class readonlyclassonlyproperty[V](classonlyproperty[V]):  # noqa: N801
    """
    Forbid assignment on a :class:`classonlyproperty` to enforce read-only semantics.

    Inherits the class-only access semantics from
    :class:`classonlyproperty` and additionally defines ``__set__`` so
    that assigning to the attribute, including via the class itself,
    always raises :class:`AttributeError`. Use this when the computed
    value must remain immutable at the class level. The generic
    parameter ``V`` is forwarded unchanged to the base descriptor for
    static typing of the wrapped getter.

    See Also
    --------
    classonlyproperty : Base descriptor that provides the getter semantics.
    builtins.property : Standard library descriptor this refines.
    abc.ABC : Base class often paired with immutable class metadata.

    Examples
    --------
    >>> class Foo:
    ...     @readonlyclassonlyproperty
    ...     def label(cls) -> str:
    ...         return cls.__name__
    >>> Foo.label
    'Foo'
    """

    def __set__(
        self,
        instance: object,
        value: object,
    ) -> NoReturn:
        """
        Refuse every assignment attempt so the attribute stays read-only.

        Implementing ``__set__`` makes the enclosing class a data
        descriptor, which means Python consults it ahead of the
        instance dictionary during attribute writes. The method never
        stores anything; it always raises, ensuring the attribute
        cannot be mutated from either the class or its instances.

        Parameters
        ----------
        instance
            The object being mutated; ignored because the descriptor
            never accepts writes from either the class or an instance.
        value
            The value the caller attempted to bind; ignored for the
            same reason.

        Raises
        ------
        AttributeError
            Unconditionally, to indicate the attribute cannot be set.

        See Also
        --------
        readonlyclassonlyproperty : Enclosing descriptor this belongs to.
        classonlyproperty : Base descriptor without the write guard.
        builtins.property : Standard library descriptor this refines.

        Examples
        --------
        >>> class Foo:
        ...     @readonlyclassonlyproperty
        ...     def label(cls) -> str:
        ...         return cls.__name__
        >>> try:
        ...     Foo().label = "x"
        ... except AttributeError:
        ...     print("blocked")
        blocked
        """
        msg = "Can't set read-only class property."
        raise AttributeError(msg)


class BaseClass:
    """
    Anchor shared mixin behaviour beneath a predictable MRO root.

    Carries no behaviour of its own. Subclasses and mixin utilities
    such as :func:`add_method` and :func:`adopt_super_methods` use it
    as a stable attachment point so that generated methods and
    descriptors can rely on a predictable method resolution order. The
    class is therefore intentionally empty and exists only to give
    downstream helpers a known root to target.

    See Also
    --------
    add_method : Attaches a chained method to any class, including subclasses of this.
    adopt_super_methods : Rewrites inherited methods to return ``self``.
    abc.ABC : Alternative base for abstract class factory patterns.

    Examples
    --------
    >>> class MyMixin(BaseClass):
    ...     pass
    >>> issubclass(MyMixin, BaseClass)
    True
    """


def add_method[T, V](
    cls: type[T],
    method: ChainedMethod[T, V],
    method_name: str,
) -> type[T]:
    """
    Attach a chained method to a class, composing with any existing binding.

    When ``cls`` already exposes an attribute at ``method_name``, the
    existing callable is invoked first and its return value is threaded
    into ``method`` via the ``prior_value`` keyword. If ``method``
    returns ``None`` the original return is preserved, allowing the
    extension to observe or side-effect without overwriting the prior
    result. When no attribute exists yet, ``method`` runs with
    ``prior_value=None`` and its return value is used directly.

    Parameters
    ----------
    cls
        The class to extend. This can be any class since the method is
        attached directly to ``cls`` without relying on MRO semantics.
    method
        The extension to install. It must accept the owning instance,
        arbitrary positional and keyword arguments, and a
        ``prior_value`` keyword carrying the previous link's return.
    method_name
        The attribute name on ``cls`` under which the composed callable
        is stored, replacing any current binding with the chained
        version.

    Returns
    -------
        ``cls`` itself, with the composed method bound at
        ``method_name``, so the function can be used as a decorator or
        in a pipeline.

    See Also
    --------
    ChainedMethod : Protocol describing the expected shape of ``method``.
    adopt_super_methods : Sibling helper that rewrites inherited methods.
    functools.singledispatch : Related dispatch-by-type composition pattern.

    Examples
    --------
    >>> class Greeter:
    ...     def greet(self) -> str:
    ...         return "hello"
    >>> def louder(self_obj, *, prior_value=None) -> str:
    ...     return f"{prior_value}!" if prior_value else "!"
    >>> _ = add_method(Greeter, louder, "greet")
    >>> Greeter().greet()
    'hello!'
    """
    previous_method = getattr(cls, method_name, None)

    @wraps(wrapped=method)
    def new_method(
        self: T,
        *args: object,
        **kwargs: object,
    ) -> object:
        """
        Dispatch to the prior binding and then to ``method`` with its return.

        Calls the previously bound attribute when one existed, captures
        its return as ``prior_value``, and then invokes ``method`` with
        the same arguments plus that keyword. The final return value is
        ``method``'s own result when it is non-``None`` and otherwise
        the prior return, preserving observe-only extensions.

        Parameters
        ----------
        self
            The instance the method is being invoked on; forwarded to both
            the prior binding and the new extension as the first argument.
        *args
            Positional arguments forwarded to both the prior binding
            and the new extension.
        **kwargs
            Keyword arguments forwarded to both the prior binding and
            the new extension.

        Returns
        -------
            The result of ``method`` when it returns a non-``None``
            value, otherwise the result of the prior binding.

        See Also
        --------
        add_method : Enclosing helper that installs this wrapper.
        ChainedMethod : Protocol describing the extension being composed.
        adopt_super_methods : Sibling helper that rewrites inherited methods.

        Examples
        --------
        >>> class Greeter:
        ...     def greet(self) -> str:
        ...         return "hi"
        >>> def louder(self_obj, *, prior_value=None) -> str:
        ...     return f"{prior_value}!"
        >>> _ = add_method(Greeter, louder, "greet")
        >>> Greeter().greet()
        'hi!'
        """
        prior = previous_method(self, *args, **kwargs) if previous_method is not None else None
        result = method(self, *args, prior_value=prior, **kwargs)

        return prior if result is None else result

    setattr(cls, method_name, new_method)

    return cls


def adopt_super_methods[T](
    cls: type[T],
    /,
) -> type[T]:
    """
    Rewrite inherited methods on ``cls`` so they return ``self`` for fluent chaining.

    Walks the immediate base of ``cls`` and, for every non-dunder
    attribute that is a plain function and is not already overridden
    on ``cls`` itself, installs a wrapper that forwards to the base
    implementation via ``super`` and then returns the receiving
    instance. The result is that the subclass gains a builder-style
    API without having to re-declare each inherited method.

    Parameters
    ----------
    cls
        The class whose inherited methods are rewritten to return
        ``self`` for fluent chaining.

    Returns
    -------
        ``cls`` with the newly attached wrappers; the original base
        methods remain reachable through ``super()``.

    See Also
    --------
    add_method : Sibling helper that composes chained method extensions.
    BaseClass : Common attachment point for mixin-style classes.
    functools.wraps : Used internally to preserve method metadata.

    Examples
    --------
    >>> class Base:
    ...     def foo(self) -> None:
    ...         return None
    ...
    ...     def bar(self) -> None:
    ...         return None
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
            base_method: Callable[..., object],
        ) -> Callable[..., T]:
            """
            Build a wrapper that delegates to a base-class method and returns ``self``.

            Captures ``method_name`` and ``base_method`` in a closure so
            that the generated wrapper can later look up the inherited
            implementation via ``super`` at call time while preserving
            the original function's metadata through
            :func:`functools.wraps`. This factory exists to avoid the
            late-binding pitfalls of defining the wrapper directly
            inside the surrounding ``for`` loop.

            Parameters
            ----------
            method_name
                The attribute name on the base class whose bound method
                the wrapper resolves via ``super`` at call time.
            base_method
                The underlying function object, used as the target for
                :func:`functools.wraps` so that metadata such as
                ``__name__`` and ``__doc__`` propagate to the wrapper.

            Returns
            -------
                A wrapper accepting the same arguments as
                ``base_method`` that invokes the base implementation
                and returns the receiving instance.

            See Also
            --------
            adopt_super_methods : Enclosing helper that uses this factory.
            functools.wraps : Used to copy metadata onto the wrapper.
            add_method : Sibling helper for chained method composition.

            Examples
            --------
            >>> class Base:
            ...     def foo(self) -> None:
            ...         return None
            >>> @adopt_super_methods
            ... class Sub(Base):
            ...     pass
            >>> Sub().foo() is not None
            True
            """

            @wraps(wrapped=base_method)
            def wrapper(
                self: T,
                *args: object,
                **kwargs: object,
            ) -> T:
                """
                Invoke the base method on ``self`` and return ``self`` for chaining.

                Resolves the original implementation through
                ``super(cls, self)`` so that cooperative multiple
                inheritance is respected, forwards the received
                arguments, and then discards the inherited return value
                in favour of the receiving instance to enable builder-
                style call sequences.

                Parameters
                ----------
                self
                    The instance whose base-class implementation is
                    invoked via ``super`` and which is returned so
                    calls can be chained.
                *args
                    Positional arguments forwarded verbatim to the
                    base-class method.
                **kwargs
                    Keyword arguments forwarded verbatim to the
                    base-class method.

                Returns
                -------
                    The instance ``self``, enabling a fluent
                    builder-style call sequence.

                See Also
                --------
                adopt_super_methods : Enclosing helper that installs this wrapper.
                make_wrapper : Factory that constructs this wrapper.
                add_method : Sibling helper for chained method composition.

                Examples
                --------
                >>> class Base:
                ...     def foo(self) -> None:
                ...         return None
                >>> @adopt_super_methods
                ... class Sub(Base):
                ...     pass
                >>> Sub().foo() is not None
                True
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
