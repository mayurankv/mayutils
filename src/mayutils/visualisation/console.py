"""
Provide console output helpers built on top of Rich.

Exposes a shared :class:`rich.console.Console` instance, a factory for
constructing consoles pre-configured with package defaults, and
symmetric install and teardown primitives so that Rich-backed
``print``, traceback, and pretty-display hooks can be toggled globally
or scoped via context managers. A separate :func:`replace_print`
context manager swaps :func:`builtins.print` for an arbitrary callable.

See Also
--------
rich.console.Console : Underlying Rich console primitive wrapped here.
rich.pretty.install : Rich pretty-printer installer.
rich.traceback.install : Rich traceback installer.

Examples
--------
>>> import builtins
>>> from mayutils.visualisation.console import replace_print
>>> calls = []
>>> with replace_print(lambda *a, **k: calls.append(a)):
...     print("ready")
>>> calls
[('ready',)]
>>> builtins.print is __import__("builtins").print
True
"""

import builtins
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from rich.console import Console
    from rich.pretty import install as install_pretty
    from rich.traceback import install as install_traceback

PRINT = builtins.print


def default_console(
    **kwargs: Any,  # noqa: ANN401
) -> Console:
    """
    Construct a Rich console pre-configured with package defaults.

    The factory layers an internal defaults mapping beneath any keyword
    arguments supplied by the caller so that project-wide behaviours
    such as colour system detection, width negotiation, and terminal
    capability probing remain consistent across call sites. Caller
    kwargs always win when keys collide, keeping the helper compatible
    with ad-hoc overrides such as enabling ``record=True`` for tests.
    The returned instance is independent and not stored on the module.

    Parameters
    ----------
    **kwargs
        Keyword arguments forwarded verbatim to
        :class:`rich.console.Console`. Package-level defaults are
        applied first and may be overridden by any matching kwarg.

    Returns
    -------
        A freshly constructed :class:`rich.console.Console` instance
        with defaults merged in.

    See Also
    --------
    rich.console.Console : Underlying Rich console implementation.
    setup_printing : Install this console as the global ``print`` hook.
    rich_printing : Scope a console to a ``with`` block.

    Examples
    --------
    >>> from rich.console import Console
    >>> from mayutils.visualisation.console import default_console
    >>> console = default_console(record=True)
    >>> isinstance(console, Console)
    True
    """
    defaults: dict[str, Any] = {}

    return Console(**(defaults | kwargs))


CONSOLE: Console = default_console()

_state: dict[str, tuple[bool, Any]] = {
    "print": (False, None),
    "traceback": (False, None),
    "pretty": (False, None),
}


@contextmanager
def replace_print(
    print_method: Callable[..., None] | None = None,
    /,
) -> Generator[None, object]:
    """
    Temporarily rebind :func:`builtins.print` to a caller-supplied callable.

    The context manager saves the current ``builtins.print`` binding on
    entry, installs the supplied replacement, and unconditionally
    restores the original on exit so that exceptions raised inside the
    block do not leak a rebound ``print``. Passing ``None`` is treated
    as a no-op swap, which simplifies call sites that decide whether to
    rebind based on runtime conditions without needing separate
    branches.

    Parameters
    ----------
    print_method : Callable or None, optional
        The callable installed as ``builtins.print`` for the duration
        of the ``with`` block. When ``None`` the current binding is
        left untouched, producing a no-op swap that is useful for
        symmetry when the replacement is conditional.

    Yields
    ------
    None
        Control is returned to the ``with`` block; on exit (including
        exceptional exit) the previous ``builtins.print`` is restored.

    See Also
    --------
    rich.console.Console.print : Typical replacement callable.
    setup_printing : Install Rich hooks globally.
    rich_printing : Richer context manager that also swaps tracebacks.

    Examples
    --------
    >>> import builtins
    >>> from mayutils.visualisation.console import replace_print
    >>> original_print = builtins.print
    >>> calls = []
    >>> with replace_print(lambda *a, **k: calls.append(a)):
    ...     print("hi")
    >>> calls
    [('hi',)]
    >>> builtins.print is original_print
    True
    """
    original = builtins.print
    if print_method is not None:
        builtins.print = print_method  # ty:ignore[invalid-assignment]
    try:
        yield
    finally:
        builtins.print = original


def setup_printing(
    console: Console | None = None,
    *,
    printing: bool = True,
    tracebacks: bool = True,
    prettify: bool = True,
) -> None:
    """
    Install Rich-backed print, traceback, and pretty-display hooks globally.

    Each hook is only installed if its corresponding flag is ``True``
    and the hook is not already tracked as installed, making the call
    idempotent at the per-hook level. The previous binding for each
    newly installed hook is captured in a module-level state mapping so
    that :func:`teardown_printing` can restore it symmetrically. The
    active console determines width, colour system, and terminal
    detection behaviour for every installed hook.

    Parameters
    ----------
    console : Console or None, optional
        Rich console routed to the installed hooks. When ``None`` the
        module-level :data:`CONSOLE` is used so every hook shares a
        consistent configuration.
    printing : bool, default True
        When ``True`` replace :func:`builtins.print` with
        ``console.print`` so module-level ``print`` calls are rendered
        by Rich with full markup support.
    tracebacks : bool, default True
        When ``True`` install Rich's traceback handler so uncaught
        exceptions render with coloured source context.
    prettify : bool, default True
        When ``True`` install Rich's pretty-printer hook so interactive
        results are syntactically highlighted.

    See Also
    --------
    teardown_printing : Inverse operation that restores originals.
    rich_printing : Scoped equivalent as a context manager.
    rich.console.Console : Console providing the render target.

    Examples
    --------
    >>> from mayutils.visualisation.console import (
    ...     _state,
    ...     setup_printing,
    ...     teardown_printing,
    ... )
    >>> try:
    ...     setup_printing(print=True, traceback=False, pretty=False)
    ...     installed = _state["print"][0]
    ... finally:
    ...     teardown_printing(print=True, traceback=False, pretty=False)
    >>> installed
    True
    >>> _state["print"][0]
    False
    """
    active_console = console if console is not None else CONSOLE

    if printing and not _state["print"][0]:
        _state["print"] = (True, builtins.print)
        builtins.print = active_console.print  # ty:ignore[invalid-assignment]

    if tracebacks and not _state["traceback"][0]:
        _state["traceback"] = (True, sys.excepthook)
        install_traceback(console=active_console)

    if prettify and not _state["pretty"][0]:
        _state["pretty"] = (True, sys.displayhook)
        install_pretty(console=active_console)


def teardown_printing(
    *,
    printing: bool = True,
    tracebacks: bool = True,
    prettify: bool = True,
) -> None:
    """
    Restore hooks previously installed by :func:`setup_printing`.

    A flag set to ``False`` leaves the corresponding hook in place so
    callers can tear down a subset, for example restoring the built-in
    ``print`` while keeping Rich tracebacks active. Hooks not currently
    tracked as installed are silently ignored, which keeps the call
    safe to invoke from cleanup code that does not know whether
    :func:`setup_printing` has run. The state mapping is updated so
    subsequent :func:`setup_printing` calls are not suppressed.

    Parameters
    ----------
    printing : bool, default True
        When ``True`` restore the :func:`builtins.print` captured by
        :func:`setup_printing`.
    tracebacks : bool, default True
        When ``True`` restore the previous :data:`sys.excepthook`.
    prettify : bool, default True
        When ``True`` restore the previous :data:`sys.displayhook`.

    See Also
    --------
    setup_printing : Counterpart that installs the hooks.
    plain_printing : Scoped equivalent as a context manager.
    rich.console.Console : Console associated with the removed hooks.

    Examples
    --------
    >>> import builtins
    >>> from mayutils.visualisation.console import (
    ...     _state,
    ...     setup_printing,
    ...     teardown_printing,
    ... )
    >>> original_print = builtins.print
    >>> try:
    ...     setup_printing(print=True, traceback=False, pretty=False)
    ... finally:
    ...     teardown_printing(print=True, traceback=False, pretty=False)
    >>> _state["print"][0]
    False
    >>> builtins.print is original_print
    True
    """
    if printing and _state["print"][0]:
        builtins.print = _state["print"][1]
        _state["print"] = (False, None)

    if tracebacks and _state["traceback"][0]:
        sys.excepthook = _state["traceback"][1]
        _state["traceback"] = (False, None)

    if prettify and _state["pretty"][0]:
        sys.displayhook = _state["pretty"][1]
        _state["pretty"] = (False, None)


def _snapshot() -> tuple[Any, Any, Any, dict[str, tuple[bool, Any]]]:
    """
    Capture current print, traceback, and display bindings for restoration.

    The snapshot tuple stores the live ``builtins.print`` reference,
    :data:`sys.excepthook`, :data:`sys.displayhook`, and a shallow copy
    of the module-level ``_state`` tracking dictionary. A copy of the
    tracking dictionary is taken so later mutations by
    :func:`setup_printing` or :func:`teardown_printing` do not bleed
    back into the snapshot. The captured values are consumed by
    :func:`_restore` to reinstate the exact prior configuration.

    Returns
    -------
    tuple of (Any, Any, Any, dict of str to tuple of (bool, Any))
        Four-element tuple holding the current ``builtins.print``
        binding, :data:`sys.excepthook`, :data:`sys.displayhook`, and
        a copy of the ``_state`` tracking dictionary.

    See Also
    --------
    _restore : Consumes the snapshot to reinstate bindings.
    rich_printing : Primary public user of the snapshot mechanism.
    plain_printing : Secondary public user of the snapshot mechanism.

    Examples
    --------
    >>> from mayutils.visualisation.console import _snapshot
    >>> snap = _snapshot()
    >>> isinstance(snap, tuple) and len(snap) == 4
    True
    """
    return builtins.print, sys.excepthook, sys.displayhook, dict(_state)


def _restore(
    snapshot: tuple[Any, Any, Any, dict[str, tuple[bool, Any]]],
) -> None:
    """
    Reinstate print, traceback, and display bindings from a snapshot tuple.

    The function unpacks the tuple produced by :func:`_snapshot`,
    reassigns the captured callables to :mod:`builtins` and :mod:`sys`,
    and replaces the module-level ``_state`` dictionary in place so
    that subsequent installation attempts see the same tracking flags
    that were present at snapshot time. It is written to be exception
    safe when invoked from ``finally`` blocks inside Rich-aware context
    managers.

    Parameters
    ----------
    snapshot : tuple of (Any, Any, Any, dict of str to tuple of (bool, Any))
        Snapshot previously returned by :func:`_snapshot`. The tuple
        encodes the prior ``builtins.print`` binding,
        :data:`sys.excepthook`, :data:`sys.displayhook`, and a copy of
        ``_state``.

    See Also
    --------
    _snapshot : Produces the snapshot consumed here.
    rich_printing : Uses this helper to exit cleanly.
    plain_printing : Uses this helper to exit cleanly.

    Examples
    --------
    >>> import builtins
    >>> from mayutils.visualisation.console import _restore, _snapshot
    >>> original_print = builtins.print
    >>> snap = _snapshot()
    >>> _restore(snap)
    >>> builtins.print is original_print
    True
    """
    previous_print, previous_excepthook, previous_displayhook, previous_state = snapshot
    builtins.print = previous_print
    sys.excepthook = previous_excepthook
    sys.displayhook = previous_displayhook
    _state.clear()
    _state.update(previous_state)


@contextmanager
def rich_printing(
    console: Console | None = None,
    *,
    printing: bool = True,
    tracebacks: bool = True,
    prettify: bool = True,
) -> Generator[None, object]:
    """
    Install Rich-backed hooks for the duration of a ``with`` block.

    The hooks and bindings active on entry are snapshotted and fully
    restored on exit, including exceptional exit, so the context
    manager nests correctly regardless of prior :func:`setup_printing`
    state. Width, colour system, and terminal detection all derive
    from the supplied console, making it practical to swap in a
    recording console for tests or a narrow console for constrained
    terminals.

    Parameters
    ----------
    console : Console or None, optional
        Passed through to :func:`setup_printing`; falls back to the
        module-level :data:`CONSOLE` when ``None``.
    printing : bool, default True
        Whether to install the Rich ``print`` replacement.
    tracebacks : bool, default True
        Whether to install the Rich traceback handler.
    prettify : bool, default True
        Whether to install the Rich pretty-display hook.

    Yields
    ------
    None
        Control is returned to the ``with`` block; the prior bindings
        are reinstated automatically on exit.

    See Also
    --------
    setup_printing : Non-scoped counterpart performing the install.
    plain_printing : Inverse context manager that disables Rich.
    rich.console.Console : Console determining render behaviour.

    Examples
    --------
    >>> import builtins
    >>> import sys
    >>> from mayutils.visualisation.console import rich_printing
    >>> original_print = builtins.print
    >>> original_excepthook = sys.excepthook
    >>> original_displayhook = sys.displayhook
    >>> with rich_printing():
    ...     swapped = builtins.print is not original_print
    >>> swapped
    True
    >>> builtins.print is original_print
    True
    >>> sys.excepthook is original_excepthook
    True
    >>> sys.displayhook is original_displayhook
    True
    """
    snapshot = _snapshot()
    setup_printing(console=console, printing=printing, tracebacks=tracebacks, prettify=prettify)
    try:
        yield
    finally:
        _restore(snapshot=snapshot)


@contextmanager
def plain_printing(
    *,
    printing: bool = True,
    tracebacks: bool = True,
    prettify: bool = True,
) -> Generator[None, Any]:
    """
    Remove Rich-backed hooks for the duration of a ``with`` block.

    The hooks and bindings active on entry are snapshotted and fully
    restored on exit so a caller can disable Rich inside a block
    without losing the original configuration. This is especially
    useful when emitting plain ASCII output to pipes or CI log
    collectors that misrender ANSI escapes, since the nested scope
    guarantees the surrounding Rich configuration is left untouched
    once the block completes.

    Parameters
    ----------
    printing : bool, default True
        Whether to restore the built-in ``print`` while the block runs.
    tracebacks : bool, default True
        Whether to restore the previous :data:`sys.excepthook`.
    prettify : bool, default True
        Whether to restore the previous :data:`sys.displayhook`.

    Yields
    ------
    None
        Control is returned to the ``with`` block; the prior bindings
        are reinstated automatically on exit.

    See Also
    --------
    teardown_printing : Non-scoped counterpart performing the removal.
    rich_printing : Inverse context manager that enables Rich.
    rich.console.Console : Console associated with the removed hooks.

    Examples
    --------
    >>> import builtins
    >>> from mayutils.visualisation.console import plain_printing
    >>> original_print = builtins.print
    >>> with plain_printing():
    ...     same = builtins.print is original_print
    >>> same
    True
    >>> builtins.print is original_print
    True
    """
    snapshot = _snapshot()
    teardown_printing(printing=printing, tracebacks=tracebacks, prettify=prettify)
    try:
        yield
    finally:
        _restore(snapshot=snapshot)
