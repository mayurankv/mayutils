"""
Provide reusable function decorators for the mayutils library.

This module collects higher-order utilities used to author ergonomic
decorators. In particular, :func:`flexwrap` is a meta-decorator that
adapts a decorator factory so it can be applied either bare
(``@my_deco``) or parameterised (``@my_deco(option=value)``) without
requiring the author to hand-write the dispatch boilerplate. The
adapted decorators preserve the wrapped callable's metadata via
:func:`functools.update_wrapper`, so introspection tools continue to
see the original signature, name and docstring.

See Also
--------
functools.wraps : Copy wrapped-callable metadata onto a wrapper.
functools.update_wrapper : Lower-level metadata transfer primitive.
contextlib.contextmanager : Decorator factory that turns a generator
    into a context manager using similar metadata preservation.

Examples
--------
>>> from mayutils.objects.decorators import flexwrap
>>> @flexwrap
... def trace(fn, *, prefix="trace"):
...     def wrapper(*args, **kwargs):
...         return fn(*args, **kwargs)
...
...     return wrapper
>>> @trace
... def bare(x):
...     return x
>>> bare(1)
1
"""

import inspect
from collections.abc import Callable
from functools import update_wrapper
from inspect import Signature
from typing import Concatenate, Protocol, cast, overload


class BareDecorator[
    Decorating: Callable[..., object],
    Decorated: Callable[..., object],
](Protocol):
    """
    Protocol for a standard function decorator.

    Describes a callable that accepts a single function and returns a
    decorated version of it.

    See Also
    --------
    GenericDecorator : Protocol variant that also accepts keyword options.
    FlexibleDecorator : Protocol combining bare and parameterised forms.

    Examples
    --------
    >>> from mayutils.objects.decorators import BareDecorator
    >>> BareDecorator.__protocol_attrs__  # doctest: +SKIP
    {'__call__'}
    """

    def __call__(
        self,
        func: Decorating,
        /,
    ) -> Decorated:
        """
        Apply the decorator to a target callable.

        Wrap the supplied callable and return the decorated version.

        Parameters
        ----------
        func
            Callable to decorate.

        See Also
        --------
        flexwrap : Meta-decorator that produces flexible decorators.

        Examples
        --------
        >>> from mayutils.objects.decorators import BareDecorator
        >>> BareDecorator.__call__  # doctest: +SKIP
        <function BareDecorator.__call__>
        """
        ...


class GenericDecorator[
    Decorating: Callable[..., object],
    Decorated: Callable[..., object],
](Protocol):
    """
    Protocol for a decorator that accepts keyword configuration.

    Describes a callable that accepts a function and optional keyword
    arguments, returning a decorated version of the function.

    See Also
    --------
    BareDecorator : Protocol for decorators without configuration.
    FlexibleDecorator : Protocol combining bare and parameterised forms.

    Examples
    --------
    >>> from mayutils.objects.decorators import GenericDecorator
    >>> GenericDecorator.__protocol_attrs__  # doctest: +SKIP
    {'__call__'}
    """

    def __call__(
        self,
        func: Decorating,
        /,
        **kwargs: object,
    ) -> Decorated:
        """
        Apply the decorator to a target callable.

        Wrap the supplied callable with the given keyword configuration
        and return the decorated version.

        Parameters
        ----------
        func
            Callable to decorate.
        **kwargs
            Keyword configuration options forwarded to the decorator
            implementation.

        See Also
        --------
        flexwrap : Meta-decorator that produces flexible decorators.

        Examples
        --------
        >>> from mayutils.objects.decorators import GenericDecorator
        >>> GenericDecorator.__call__  # doctest: +SKIP
        <function GenericDecorator.__call__>
        """
        ...


class FlexibleDecorator[
    Decorating: Callable[..., object],
    Decorated: Callable[..., object],
    **Params,
](Protocol):
    """
    Protocol for a decorator supporting both bare and parameterised forms.

    Describes a callable that can be applied either directly to a function
    or called with configuration options first.

    See Also
    --------
    BareDecorator : Protocol for decorators without configuration.
    GenericDecorator : Protocol for decorators with keyword configuration.
    flexwrap : Meta-decorator that creates flexible decorators.

    Examples
    --------
    >>> from mayutils.objects.decorators import FlexibleDecorator
    >>> FlexibleDecorator.__protocol_attrs__  # doctest: +SKIP
    {'__call__', '__signature__'}
    """

    __signature__: Signature

    @overload
    def __call__(  # numpydoc ignore=GL08
        self,
        func: Decorating,
        /,
    ) -> Decorated: ...

    @overload
    def __call__(  # numpydoc ignore=GL08
        self,
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> BareDecorator[Decorating, Decorated]: ...

    def __call__(
        self,
        *args: object,
        **kwargs: object,
    ) -> Decorated | BareDecorator[Decorating, Decorated]:
        """
        Dispatch between bare and parameterised invocation.

        Inspect the supplied arguments to decide whether to apply the
        decorator directly or return a configured decorator.

        Parameters
        ----------
        *args
            Positional arguments; a single callable triggers bare form.
        **kwargs
            Keyword configuration options for parameterised form.

        See Also
        --------
        flexwrap : Meta-decorator that builds this dispatch logic.

        Examples
        --------
        >>> from mayutils.objects.decorators import FlexibleDecorator
        >>> FlexibleDecorator.__call__  # doctest: +SKIP
        <function FlexibleDecorator.__call__>
        """
        ...


def extract_decorator_signature(
    decorator: Callable[..., object],
    /,
) -> Signature:
    """
    Return the signature of *decorator* without its first parameter.

    Strip the leading positional parameter (the decorated function) from
    the decorator's signature, leaving only the configuration parameters.

    Parameters
    ----------
    decorator
        Decorator factory whose first positional parameter is the
        function being decorated.

    Returns
    -------
        Signature containing only the configuration parameters.

    See Also
    --------
    flexwrap : Consumer that uses this to build the dispatch signature.
    inspect.signature : Underlying introspection primitive.

    Examples
    --------
    >>> from mayutils.objects.decorators import extract_decorator_signature
    >>> def my_deco(func, *, verbose=False): ...
    >>> sig = extract_decorator_signature(my_deco)
    >>> list(sig.parameters)
    ['verbose']
    """
    signature = inspect.signature(decorator)
    params = list(signature.parameters.values())
    config_params = params[1:]
    return signature.replace(parameters=config_params)


def flexwrap[
    Decorating: Callable[..., object],
    Decorated: Callable[..., object],
    **Params,
](
    decorator: Callable[Concatenate[Decorating, Params], Decorated],
) -> FlexibleDecorator[Decorating, Decorated, Params]:
    """
    Adapt a decorator factory so it supports bare and parameterised forms.

    Convert *decorator* into a callable that can be invoked either as
    ``@decorator`` (bare form) or as ``@decorator(**kwargs)``
    (parameterised form). A single callable positional with no keyword
    arguments triggers the bare path; any other call shape builds a
    secondary decorator bound to the captured kwargs.

    Parameters
    ----------
    decorator
        Decorator factory to adapt. Its first positional parameter must
        be the function being decorated; any additional parameters must
        be keyword-only configuration options, because the parameterised
        form rejects extra positional arguments.

    Returns
    -------
        A callable sharing *decorator*'s type that dispatches to the bare
        or parameterised code path based on how it is invoked. When
        called bare, it returns the wrapped function directly; when
        called with keyword arguments, it returns a secondary decorator
        bound to those arguments.

    See Also
    --------
    functools.wraps : Decorator used internally to propagate *decorator*'s
        metadata onto the dispatch wrapper returned by this function.
    functools.update_wrapper : Lower-level primitive used by the bare
        and parameterised branches to transfer metadata onto the final
        wrapper.
    functools.cache : Example of a decorator factory that benefits from
        ``flexwrap``-style dual-invocation ergonomics.
    contextlib.contextmanager : Sibling pattern that wraps callables
        while preserving their introspection surface.

    Notes
    -----
    The bare-form heuristic ``len(args) == 1 and callable(args[0]) and
    not kwargs`` means a decorator whose only configuration argument is
    itself a callable cannot be detected automatically; such
    decorators must always be invoked with keyword arguments.

    Examples
    --------
    >>> @flexwrap
    ... def shout(func, prefix="!"):
    ...     def wrapper(*a, **k):
    ...         return prefix + func(*a, **k).upper()
    ...
    ...     return wrapper
    >>> @shout
    ... def hello() -> str:
    ...     return "hi"
    >>> @shout(prefix=">>> ")
    ... def hey() -> str:
    ...     return "hey"
    >>> hello(), hey()
    ('!HI', '>>> HEY')
    """
    signature = extract_decorator_signature(decorator)
    generic_decorator = cast(
        "GenericDecorator[Decorating, Decorated]",
        decorator,
    )

    def parameterised_decorator_wrapper(
        **kwargs: object,
    ) -> BareDecorator[Decorating, Decorated]:
        """
        Build a secondary decorator bound to the captured keyword arguments.

        Validate the supplied keyword arguments against the decorator's
        configuration signature, then return a closure that applies the
        decorator with those arguments to a target callable.

        Parameters
        ----------
        **kwargs
            Keyword configuration options forwarded to the underlying
            decorator factory.

        Returns
        -------
            A bare decorator that applies the outer decorator with the
            captured keyword arguments.

        See Also
        --------
        flexwrap : Meta-decorator that installs this helper.

        Examples
        --------
        >>> @flexwrap
        ... def add_tag(func, tag="default"):
        ...     def wrapper(*a, **k):
        ...         return (tag, func(*a, **k))
        ...
        ...     return wrapper
        >>> @add_tag(tag="custom")
        ... def greet():
        ...     return "hi"
        >>> greet()
        ('custom', 'hi')
        """
        signature.bind(**kwargs)

        def implicitly_parameterised_decorator(
            func: Decorating,
            /,
        ) -> Decorated:
            """
            Apply the parameterised decorator to a target callable.

            Invoke the outer ``deco`` factory with the captured
            configuration keyword arguments and the supplied ``func``,
            then transfer ``func``'s metadata onto the resulting
            wrapper so attributes such as ``__name__``, ``__doc__``
            and ``__wrapped__`` behave as if the function had been
            wrapped directly. The resulting wrapper is cast back to
            ``func``'s declared type to preserve static type inference
            at call sites.

            Parameters
            ----------
            func
                Target callable to decorate. Its signature must be
                compatible with whatever call contract ``deco``
                establishes for its wrapped functions.

            Returns
            -------
                The wrapper produced by ``deco(func, **kwargs)`` with
                ``func``'s metadata copied onto it, cast back to
                ``func``'s declared type so downstream type inference
                is preserved.

            See Also
            --------
            flexwrap : Outer meta-decorator that creates this closure.
            functools.wraps : Decorator-style convenience wrapper
                around :func:`functools.update_wrapper`.
            functools.update_wrapper : Primitive used here to copy
                metadata from ``func`` onto the ``deco``-produced
                wrapper.

            Examples
            --------
            >>> @flexwrap
            ... def prefix(func, token="*"):
            ...     def wrapper(*a, **k):
            ...         return token + func(*a, **k)
            ...
            ...     return wrapper
            >>> @prefix(token="#")
            ... def greet() -> str:
            ...     return "hi"
            >>> greet()
            '#hi'
            """
            implicitly_parameterised_decorated_func = generic_decorator(
                func,
                **kwargs,
            )

            update_wrapper(
                wrapper=implicitly_parameterised_decorated_func,
                wrapped=func,
            )

            return implicitly_parameterised_decorated_func

        update_wrapper(
            wrapped=decorator,
            wrapper=implicitly_parameterised_decorator,
        )

        return implicitly_parameterised_decorator

    def bare_decorator(
        func: Decorating,
        /,
    ) -> Decorated:
        """
        Apply the decorator directly without keyword configuration.

        Invoke the decorator factory with only the target callable and
        transfer the callable's metadata onto the resulting wrapper.

        Parameters
        ----------
        func
            Target callable to decorate.

        Returns
        -------
            The wrapper produced by the decorator factory with the
            target callable's metadata copied onto it.

        See Also
        --------
        flexwrap : Meta-decorator that installs this helper.
        functools.update_wrapper : Used to transfer metadata.

        Examples
        --------
        >>> @flexwrap
        ... def echo(func):
        ...     def wrapper(*a, **k):
        ...         return func(*a, **k)
        ...
        ...     return wrapper
        >>> @echo
        ... def identity(x):
        ...     return x
        >>> identity(42)
        42
        """
        bare_decorated_func = generic_decorator(func)

        update_wrapper(
            wrapper=bare_decorated_func,
            wrapped=func,
        )

        return bare_decorated_func

    def flexible_decorator(
        *args: object,
        **kwargs: object,
    ) -> Decorated | BareDecorator[Decorating, Decorated]:
        """
        Dispatch between bare and parameterised invocation of ``deco``.

        Inspect the supplied ``args`` and ``kwargs`` to decide whether
        the enclosing decorator is being applied directly to a target
        callable or being configured with keyword options. A single
        callable positional with no keywords triggers the bare path,
        which immediately wraps the function; any other call shape
        builds a secondary decorator bound to the captured ``kwargs``.
        Metadata on the wrapped callable is propagated via
        :func:`functools.update_wrapper` in both branches.

        Parameters
        ----------
        *args
            Positional arguments forwarded from the decorator call
            site. In the supported usage this is either empty or a
            single callable; any other shape raises ``TypeError``.
        **kwargs
            Keyword configuration options forwarded to ``deco`` when
            the parameterised form is used.

        Returns
        -------
            Either the wrapped target callable (bare form) or a nested
            decorator that, when applied to a callable, returns the
            final wrapper produced by ``deco``.

        Raises
        ------
        TypeError
            If positional arguments other than a single callable are
            supplied, signalling misuse of the parameterised form.

        See Also
        --------
        flexwrap : Outer meta-decorator that installs this dispatcher.
        functools.wraps : Applied to this function to copy ``deco``'s
            metadata onto the dispatcher itself.
        functools.update_wrapper : Transfers metadata from the target
            callable onto the wrapper produced by ``deco``.

        Examples
        --------
        >>> @flexwrap
        ... def tag(func, label="t"):
        ...     def wrapper(*a, **k):
        ...         return (label, func(*a, **k))
        ...
        ...     return wrapper
        >>> @tag
        ... def bare():
        ...     return 1
        >>> @tag(label="x")
        ... def parameterised():
        ...     return 2
        >>> bare(), parameterised()
        (('t', 1), ('x', 2))
        """
        if len(args) == 1 and callable(args[0]) and not kwargs:  # Bare form
            func = cast("Decorating", args[0])

            return bare_decorator(func)

        if args:
            msg = "This decorator only supports keyword arguments."
            raise TypeError(msg)

        return parameterised_decorator_wrapper(**kwargs)

    update_wrapper(
        wrapper=flexible_decorator,
        wrapped=decorator,
    )

    final_decorator = cast("FlexibleDecorator[Decorating, Decorated, Params]", flexible_decorator)
    final_decorator.__signature__ = signature

    return final_decorator
