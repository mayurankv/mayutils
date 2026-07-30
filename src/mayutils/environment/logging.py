"""
Provide Rich-backed logging utilities and a timing decorator.

Expose a :class:`logging.Logger` subclass that installs a
:class:`rich.logging.RichHandler` and a
:class:`logging.handlers.RotatingFileHandler` on the root logger, a
module-aware ``spawn`` factory, a structured ``print`` method that
concatenates message fragments, and a ``@log`` decorator that wraps
callables (or every method of a class) with entry, exit and exception
logging along with wall-clock timing. The module is imported early in
application bootstrap so that downstream packages can simply call
``Logger.spawn()`` to obtain a named logger inheriting the configured
handlers. All log records flow through the standard :mod:`logging`
pipeline so existing filters, adapters and third-party handlers
continue to function.

See Also
--------
logging.Logger : Standard library logger class extended here.
logging.Handler : Base class for console / file routing targets.
logging.Formatter : Formatter tokens used by :data:`CONSOLE_FORMAT`.
rich.logging.RichHandler : Console handler attached in :meth:`Logger.configure`.

Examples
--------
>>> import logging as _logging
>>> from mayutils.environment.logging import Logger
>>> module_logger = Logger("pipeline_demo", level=_logging.INFO)
>>> module_logger.print("pipeline", "started", level="INFO")
pipeline started
>>> isinstance(module_logger, Logger)
True
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from functools import update_wrapper
from inspect import currentframe, getmodule
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self, cast

from mayutils.core.extras import may_require_extras
from mayutils.environment.filesystem import get_root
from mayutils.objects.decorators import flexwrap

if TYPE_CHECKING:
    from types import TracebackType

PredefinedLevel = Literal["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
Level = PredefinedLevel | int

CONSOLE_FORMAT = "%(message)s"
FILE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

root_logger = logging.getLogger()


def attach_handler(
    logger: logging.Logger,
    /,
    *,
    handler: logging.Handler,
    formatter: logging.Formatter | None,
) -> None:
    """
    Apply an optional formatter to a handler and attach it to a logger.

    When ``formatter`` is not ``None`` it is applied to ``handler``
    via :meth:`logging.Handler.setFormatter` before the handler is
    added to ``logger``.

    Parameters
    ----------
    logger
        Target logger.
    handler
        Handler to attach.
    formatter
        Optional formatter.  When not ``None`` it is set on
        ``handler`` before attachment.

    See Also
    --------
    logging.Handler.setFormatter : Applies the formatter.
    logging.Logger.addHandler : Attaches the handler.

    Examples
    --------
    >>> import logging
    >>> from mayutils.environment.logging import attach_handler
    >>> lgr = logging.getLogger("test_attach")
    >>> h = logging.StreamHandler()
    >>> attach_handler(lgr, handler=h, formatter=None)
    >>> h in lgr.handlers
    True
    """
    if formatter is not None:
        handler.setFormatter(fmt=formatter)

    logger.addHandler(hdlr=handler)


class Logger(logging.Logger):
    """
    Extend :class:`logging.Logger` with Rich output and factories.

    Adds three capabilities over the standard library logger so that
    application code can stay terse: :meth:`configure` installs a
    console and file handler on the root logger, ensuring formatted,
    coloured console output with rich tracebacks and persistent file
    logs across the whole process; :meth:`spawn` returns a
    :class:`Logger` instance automatically named after the caller's
    module, removing the ``__name__`` boilerplate from downstream
    modules; and :meth:`print` concatenates multiple message fragments
    with a configurable separator and dispatches a single log record
    while also printing to stdout for interactive use.  Instances
    behave identically to :class:`logging.Logger` for any API not
    explicitly overridden, and existing handlers, filters and parents
    are preserved by :meth:`clone`.

    Parameters
    ----------
    name
        Logger name, typically the dotted module path.
    level
        Initial severity threshold for this logger.
    console_handler
        Optional console handler.
    console_formatter
        Optional formatter for ``console_handler``.
    file_handler
        Optional file handler.
    file_formatter
        Optional formatter for ``file_handler``.

    See Also
    --------
    logging.Logger : Standard library parent class.
    logging.Handler : Base class of handlers attached via configure.
    logging.Formatter : Formatter applied with CONSOLE_FORMAT tokens.
    rich.logging.RichHandler : Console handler attached in configure.

    Examples
    --------
    >>> import logging as _logging
    >>> from tempfile import TemporaryDirectory
    >>> _root = _logging.getLogger()
    >>> _saved_handlers = _root.handlers[:]
    >>> _saved_level = _root.level
    >>> with TemporaryDirectory() as _tmp:
    ...     Logger.configure(log_dir=_tmp, console_level="WARNING")
    >>> log = Logger.spawn(name="my.module")
    >>> log.print("hello", "world", level="INFO")
    hello world
    >>> _root.handlers = _saved_handlers
    >>> _root.setLevel(_saved_level)
    """

    def __init__(
        self,
        name: str,
        /,
        *,
        level: Level = logging.NOTSET,
        console_handler: logging.Handler | None = None,
        console_formatter: logging.Formatter | None = None,
        file_handler: logging.Handler | None = None,
        file_formatter: logging.Formatter | None = None,
    ) -> None:
        """
        Initialise the underlying :class:`logging.Logger`.

        Forward ``name`` and ``level`` to the parent constructor and
        optionally attach console and file handlers.

        Parameters
        ----------
        name
            Logger name, typically the dotted module path.
        level
            Initial severity threshold.
        console_handler
            Optional console handler.
        console_formatter
            Optional formatter for ``console_handler``.
        file_handler
            Optional file handler.
        file_formatter
            Optional formatter for ``file_handler``.

        See Also
        --------
        logging.Logger.__init__ : Parent constructor.
        Logger.clone : Alternative factory that copies an existing
            logger.
        Logger.spawn : Higher-level factory used by most callers.

        Examples
        --------
        >>> log = Logger("my.module", level=logging.INFO)
        >>> log.name
        'my.module'
        """
        super().__init__(name=name, level=level)
        for handler, formatter in (
            (console_handler, console_formatter),
            (file_handler, file_formatter),
        ):
            if handler is not None:
                attach_handler(self, handler=handler, formatter=formatter)

        self._previous_level: int | None = None

    def __enter__(self) -> Self:
        """
        Save the current level so it can be restored on exit.

        Record the current numeric level so that :meth:`__exit__`
        can reinstate it when the ``with`` block ends.

        Returns
        -------
            The logger instance for use in a ``with`` block.

        See Also
        --------
        Logger.__exit__ : Restores the saved level.

        Examples
        --------
        >>> log = Logger("ctx_demo", level=logging.WARNING)
        >>> log.level == logging.WARNING
        True
        """
        self._previous_level = self.level
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """
        Restore the level saved by :meth:`__enter__`.

        Reset the logger's severity to the value captured on entry
        regardless of whether the ``with`` block raised.

        Parameters
        ----------
        exc_type
            Exception type, if any.
        exc_val
            Exception value, if any.
        exc_tb
            Exception traceback, if any.

        See Also
        --------
        Logger.__enter__ : Saves the level before entry.

        Examples
        --------
        >>> log = Logger("exit_demo", level=logging.WARNING)
        >>> log.__exit__(None, None, None)
        """
        if self._previous_level is not None:
            self.setLevel(level=self._previous_level)
            self._previous_level = None

    @staticmethod
    def configure(
        *,
        console_handler: logging.Handler | None = None,
        console_formatter: logging.Formatter | None = None,
        console_level: Level = logging.WARNING,
        file_handler: logging.Handler | None = None,
        file_formatter: logging.Formatter | None = None,
        file_level: Level = logging.DEBUG,
        log_dir: Path | str | None = None,
    ) -> None:
        """
        Install console and file handlers on the root logger.

        Clear any pre-existing handlers on the root logger and attach
        a console handler (defaulting to :class:`rich.logging.RichHandler`)
        and a file handler (defaulting to
        :class:`logging.handlers.RotatingFileHandler`).  The root level
        is set to :data:`logging.DEBUG` so that handler-level filters
        control visibility.

        Parameters
        ----------
        console_handler
            Console handler.  When ``None`` a
            :class:`rich.logging.RichHandler` is created.
        console_formatter
            Formatter for the console handler.  When ``None`` the
            default :data:`CONSOLE_FORMAT` is used.
        console_level
            Minimum severity for the default console handler.
            Ignored when a custom ``console_handler`` is supplied.
        file_handler
            File handler.  When ``None`` a
            :class:`logging.handlers.RotatingFileHandler` is created.
        file_formatter
            Formatter for the file handler.  When ``None`` the
            default :data:`FILE_FORMAT` is used.
        file_level
            Minimum severity for the default file handler.  Ignored
            when a custom ``file_handler`` is supplied.
        log_dir
            Filesystem location for log files.  Created (including
            parents) if missing.  Defaults to ``get_root() / "logs"``
            when ``None``.

        See Also
        --------
        logging.Logger : Root logger whose handlers are replaced.
        logging.Handler : Base class of the attached handlers.
        rich.logging.RichHandler : Default console handler.
        logging.handlers.RotatingFileHandler : Default file handler.

        Examples
        --------
        >>> import logging as _logging
        >>> from tempfile import TemporaryDirectory
        >>> _root = _logging.getLogger()
        >>> _saved_handlers = _root.handlers[:]
        >>> _saved_level = _root.level
        >>> with TemporaryDirectory() as _tmp:
        ...     Logger.configure(log_dir=_tmp, console_level="INFO")
        >>> len(_root.handlers)
        2
        >>> _root.level == _logging.DEBUG
        True
        >>> _root.handlers = _saved_handlers
        >>> _root.setLevel(_saved_level)
        """
        if log_dir is None:
            log_dir = get_root() / "logs"
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        if console_handler is None:
            with may_require_extras():
                from rich.logging import RichHandler

            console_handler = RichHandler(
                level=console_level,
                rich_tracebacks=True,
                show_time=True,
                show_path=True,
            )
        if console_formatter is None:
            console_formatter = logging.Formatter(fmt=CONSOLE_FORMAT)

        if file_handler is None:
            file_handler = RotatingFileHandler(
                filename=log_dir / "default.log",
                maxBytes=10_485_760,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setLevel(level=file_level)

        if file_formatter is None:
            file_formatter = logging.Formatter(fmt=FILE_FORMAT)

        root_logger.handlers.clear()
        attach_handler(root_logger, handler=console_handler, formatter=console_formatter)
        attach_handler(root_logger, handler=file_handler, formatter=file_formatter)

        root_logger.setLevel(level=logging.DEBUG)

    @classmethod
    def clone(
        cls,
        logger: logging.Logger,
        /,
    ) -> Self:
        """
        Return a :class:`Logger` copy of the supplied logger.

        Produce a new instance sharing the source logger's name,
        numeric level, attached handlers, filters and parent so that
        callers obtain an object compatible with the extended API
        without mutating the original logger stored in the
        :data:`logging.Logger.manager` dictionary.  Handlers and
        filters are re-attached by reference (not deep-copied), which
        means records continue to flow through the existing routing
        infrastructure while still benefiting from the :class:`Logger`
        helpers such as :meth:`print`.

        Parameters
        ----------
        logger
            Source logger whose identity and configuration are
            replicated.  Its handlers and filters are re-attached to
            the clone by reference (not deep-copied).

        Returns
        -------
            A new :class:`Logger` whose ``name``, ``level``,
            ``handlers``, ``filters`` and ``parent`` mirror those of
            ``logger``.

        See Also
        --------
        logging.Logger : Standard logger type being cloned.
        logging.Handler : Handlers re-attached to the clone.
        Logger.spawn : Primary caller of this method.

        Examples
        --------
        >>> base = logging.getLogger("pipeline")
        >>> clone = Logger.clone(base)
        >>> clone.name
        'pipeline'
        """
        clone = cls(
            logger.name,
            level=logger.level,
        )
        for handler in logger.handlers:
            clone.addHandler(handler)

        for log_filter in logger.filters:
            clone.addFilter(filter=log_filter)

        clone.parent = logger.parent

        return clone

    @classmethod
    def spawn(
        cls,
        *,
        name: str | None = None,
        console_handler: logging.Handler | None = None,
        console_formatter: logging.Formatter | None = None,
        file_handler: logging.Handler | None = None,
        file_formatter: logging.Formatter | None = None,
    ) -> Self:
        """
        Return a :class:`Logger` named for the caller's module.

        Walk one frame up via :func:`inspect.currentframe` when
        ``name`` is omitted to derive the caller's ``__name__``,
        mirroring the convention
        ``logger = logging.getLogger(__name__)``.  Fall back to the
        root logger when the calling frame or module cannot be
        resolved.  The resolved logger is then cloned via
        :meth:`clone` so the caller receives a :class:`Logger`
        instance with the extended API while still sharing handlers
        with any existing logger of the same name.

        Parameters
        ----------
        name
            Explicit logger name.  When ``None`` the caller's module
            name is inferred; otherwise the supplied value is passed
            straight to :func:`logging.getLogger`.
        console_handler
            Optional console handler for the spawned logger.
        console_formatter
            Optional formatter for ``console_handler``.
        file_handler
            Optional file handler for the spawned logger.
        file_formatter
            Optional formatter for ``file_handler``.

        Returns
        -------
            A cloned, ready-to-use :class:`Logger` retrieved from the
            standard library's logger manager.

        See Also
        --------
        logging.Logger : Underlying logger class.
        logging.getLogger : Registry consulted when resolving names.
        Logger.clone : Helper used to copy the resolved logger.

        Examples
        --------
        >>> log = Logger.spawn()
        >>> isinstance(log, Logger)
        True
        """
        if name is None:
            frame = currentframe()
            if frame is None:
                return cls(root_logger.name)

            module = getmodule(frame.f_back)

            name = getattr(module, "__name__", "__main__")
            if not name or name == logging.root.name:
                return cls(root_logger.name)

        existing = logging.getLogger(name=name)
        result = cls.clone(existing)

        for handler, formatter in (
            (console_handler, console_formatter),
            (file_handler, file_formatter),
        ):
            if handler is not None:
                attach_handler(result, handler=handler, formatter=formatter)

        return result

    def print(
        self,
        *msgs: str,
        sep: str = " ",
        level: Level | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """
        Print a message to stdout and log it.

        Join the supplied fragments with ``sep`` into a single line,
        print it to stdout, and dispatch it through the logging
        pipeline at the requested severity.

        Parameters
        ----------
        *msgs
            Message fragments to concatenate.
        sep
            Separator placed between successive fragments.
        level
            Severity at which to emit the record.  When ``None`` the
            logger's effective level is used.
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`logging.Logger.log` (for example ``exc_info`` or
            ``extra``).

        See Also
        --------
        logging.Logger : Parent class providing the log method.
        logging.Handler : Handlers that eventually emit the record.
        Logger.configure : Installs the console handler invoked here.

        Examples
        --------
        >>> import logging as _logging
        >>> log = Logger("print_demo", level=_logging.INFO)
        >>> records = []
        >>> class _Capture(_logging.Handler):
        ...     def emit(self, record):
        ...         records.append(record)
        >>> log.addHandler(_Capture())
        >>> log.print("stage", "complete", level="INFO")
        stage complete
        >>> records[-1].getMessage()
        'stage complete'
        """
        msg = sep.join(msgs)
        print(msg)  # noqa: T201
        self.dispatch(msg=msg, level=level, **kwargs)

    def dispatch(
        self,
        msg: str,
        level: Level | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> str:
        """
        Dispatch the message with a normalised integer severity.

        Resolve ``level`` (which may be an integer, a predefined
        name, or ``None``) to a concrete integer severity, falling
        back to the logger's effective level when unresolved, then
        call :meth:`logging.Logger.log`.

        Parameters
        ----------
        msg
            Pre-joined log message to emit.
        level
            Requested severity.  String values are translated via
            :func:`logging.getLevelNamesMapping`; ``None`` defers to
            :meth:`logging.Logger.getEffectiveLevel`.
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`logging.Logger.log`.

        Returns
        -------
            The ``msg`` argument unchanged, returned to support
            chaining and make the dispatched payload inspectable by
            callers.

        See Also
        --------
        logging.Logger.log : Ultimate destination of the dispatch.
        logging.Handler : Recipients of the emitted record.
        Logger.print : Public wrapper that calls this helper.

        Examples
        --------
        >>> log = Logger.spawn()
        >>> log.print("status", "ok", level="INFO")
        status ok
        """
        level_int = logging.getLevelNamesMapping().get(level, None) if isinstance(level, str) else level
        if level_int is None:
            level_int = self.getEffectiveLevel()

        super().log(
            level=level_int,
            msg=msg,
            **kwargs,
        )

        return msg


_logger: Logger | None = None


def get_logger() -> Logger:
    """
    Return the module-level logger, creating it lazily on first use.

    On the first call a :class:`Logger` is spawned via
    :meth:`Logger.spawn` and cached for subsequent calls.

    Returns
    -------
        The shared :class:`Logger` instance for this module.

    See Also
    --------
    Logger.spawn : Factory used on first invocation.

    Examples
    --------
    >>> from mayutils.environment.logging import get_logger
    >>> lgr = get_logger()
    >>> isinstance(lgr, Logger)
    True
    """
    global _logger  # noqa: PLW0603

    if _logger is None:
        _logger = Logger.spawn()

    return _logger


def format_entry(
    name: str,
    /,
    *,
    args: tuple[object, ...],
    kwargs: dict[str, object],
    include_args: bool,
) -> str:
    """
    Build the entry log message for a wrapped call.

    Format a ``"Calling name(…)"`` string, optionally including
    :func:`repr` of each positional and keyword argument.

    Parameters
    ----------
    name
        Function name.
    args
        Positional arguments to the wrapped call.
    kwargs
        Keyword arguments to the wrapped call.
    include_args
        Whether to include argument representations.

    Returns
    -------
        Formatted entry message.

    See Also
    --------
    _format_outcome : Companion for exit / exception messages.

    Examples
    --------
    >>> from mayutils.environment.logging import format_entry
    >>> format_entry("f", args=(1,), kwargs={}, include_args=True)
    'Calling f(1)'
    """
    if not include_args:
        return f"Calling {name}"

    args_repr = ", ".join(
        [repr(arg) for arg in args] + [f"{key}={value!r}" for key, value in kwargs.items()],
    )

    return f"Calling {name}({args_repr})"


def format_outcome(
    name: str,
    /,
    *,
    outcome: str,
    detail: object,
    elapsed: float,
    include_timing: bool,
) -> str:
    """
    Build the exit or exception log message for a wrapped call.

    Format a ``"name returned/raised (Xs): detail"`` string,
    optionally including the wall-clock duration.

    Parameters
    ----------
    name
        Function name.
    outcome
        Either ``"returned"`` or ``"raised"``.
    detail
        The return value or exception.
    elapsed
        Wall-clock seconds from :func:`time.perf_counter`.
    include_timing
        Whether to include the duration.

    Returns
    -------
        Formatted outcome message.

    See Also
    --------
    _format_entry : Companion for entry messages.

    Examples
    --------
    >>> from mayutils.environment.logging import format_outcome
    >>> format_outcome("f", outcome="returned", detail=42, elapsed=0.1, include_timing=True)
    'f returned (0.10s): 42'
    """
    if include_timing:
        return f"{name} {outcome} ({elapsed:.2f}s): {detail}"

    return f"{name} {outcome}: {detail}"


def prepare_handlers(
    *handler_pairs: tuple[logging.Handler, logging.Formatter | None],
) -> list[logging.Handler]:
    """
    Build a list of handlers from (handler, formatter) pairs.

    Iterate over the pairs, skip ``None`` handlers, apply any
    non-``None`` formatter, and collect the results.

    Parameters
    ----------
    *handler_pairs
        Pairs of ``(handler, formatter)``.  ``None`` handlers are
        skipped; non-``None`` formatters are applied before the
        handler is included.

    Returns
    -------
        Handlers ready for attachment.

    See Also
    --------
    _attach_handler : Attaches a single handler to a logger.

    Examples
    --------
    >>> import logging
    >>> from mayutils.environment.logging import prepare_handlers
    >>> handler = logging.StreamHandler()
    >>> formatter = logging.Formatter(fmt="%(message)s")
    >>> result = prepare_handlers((handler, formatter))
    >>> result == [handler]
    True
    >>> handler.formatter is formatter
    True
    """
    result: list[logging.Handler] = []
    for handler, formatter in handler_pairs:
        if formatter is not None:
            handler.setFormatter(fmt=formatter)

        result.append(handler)

    return result


def get_valid_handlers(
    *handler_pairs: tuple[logging.Handler | None, logging.Formatter | None],
) -> tuple[tuple[logging.Handler, logging.Formatter | None], ...]:
    """
    Filter handler pairs, keeping only those with a non-``None`` handler.

    Iterates over the supplied pairs and discards any whose handler
    element is ``None``, narrowing the type for downstream consumers.

    Parameters
    ----------
    *handler_pairs
        Pairs of ``(handler, formatter)``.  Pairs whose handler is
        ``None`` are excluded from the result.

    Returns
    -------
        Pairs where the handler is not ``None``.

    See Also
    --------
    prepare_handlers : Consumer that applies formatters to the
        filtered pairs.

    Examples
    --------
    >>> import logging
    >>> from mayutils.environment.logging import get_valid_handlers
    >>> get_valid_handlers((None, None))
    ()
    """
    return tuple((handler, formatter) for (handler, formatter) in handler_pairs if handler is not None)


@flexwrap
def log_func[Decorating: Callable[..., object]](
    func: Decorating,
    /,
    *,
    level: Level = logging.INFO,
    log_entry: bool = True,
    log_exit: bool = True,
    log_timing: bool = True,
    log_args: bool = True,
    log_exception: bool = True,
    console_handler: logging.Handler | None = None,
    console_formatter: logging.Formatter | None = None,
    file_handler: logging.Handler | None = None,
    file_formatter: logging.Formatter | None = None,
) -> Decorating:
    """
    Wrap the callable with entry, exit and exception logging.

    Produce a :func:`functools.wraps`-preserving wrapper that
    optionally records entry, exit and exception messages with
    wall-clock timing measured via :func:`time.perf_counter`.  The
    wrapper uses the module-level logger, so the output is routed
    through whatever handlers :meth:`Logger.configure` has installed.

    Parameters
    ----------
    func
        Callable to be decorated.
    level
        Severity used for the entry and successful-return messages.
        Exception messages always use :data:`logging.ERROR`.
    log_entry
        Whether to log a message before invocation.
    log_exit
        Whether to log a message after successful return.
    log_timing
        Whether to include wall-clock duration in messages.
    log_args
        Whether to include function arguments in the entry message.
    log_exception
        Whether to log exceptions before re-raising.
    console_handler
        Optional console handler temporarily attached per call.
    console_formatter
        Optional formatter for ``console_handler``.
    file_handler
        Optional file handler temporarily attached per call.
    file_formatter
        Optional formatter for ``file_handler``.

    Returns
    -------
        Wrapper around ``func`` that adds logging and timing while
        preserving the original return value and exception
        behaviour.

    See Also
    --------
    logging.Logger : Underlying logger type used by the wrapper.
    Logger.print : Helper invoked inside the wrapper.

    Examples
    --------
    >>> @log(level="DEBUG")
    ... def double(x: int) -> int:
    ...     return x * 2
    >>> double(3)
    6
    """
    temp_handlers = prepare_handlers(
        *get_valid_handlers(
            (console_handler, console_formatter),
            (file_handler, file_formatter),
        )
    )

    func_name: str = getattr(func, "__name__", repr(func))

    def wrapper(
        *args: object,
        **kwargs: object,
    ) -> object:
        """
        Invoke the wrapped callable with instrumentation.

        Attach any temporary handlers, emit configured log messages
        around the call, and remove the temporary handlers on exit.

        Parameters
        ----------
        *args
            Positional arguments passed through to the wrapped
            callable.
        **kwargs
            Keyword arguments passed through to the wrapped
            callable.

        Returns
        -------
            The value returned by the wrapped callable.

        See Also
        --------
        Logger.dispatch : Emits each log record.

        Examples
        --------
        >>> @log
        ... def greet(name: str) -> str:
        ...     return f"hello {name}"
        >>> greet("world")
        'hello world'
        """
        active_logger = get_logger()

        for handler in temp_handlers:
            active_logger.addHandler(hdlr=handler)

        try:
            if log_entry:
                active_logger.dispatch(
                    format_entry(
                        func_name,
                        args=args,
                        kwargs=kwargs,
                        include_args=log_args,
                    ),
                    level=level,
                )

            start = time.perf_counter()

            try:
                result = func(*args, **kwargs)
            except Exception as exception:
                elapsed = time.perf_counter() - start

                if log_exception:
                    active_logger.dispatch(
                        format_outcome(
                            func_name,
                            outcome="raised",
                            detail=exception,
                            elapsed=elapsed,
                            include_timing=log_timing,
                        ),
                        level=logging.ERROR,
                        exc_info=True,
                    )

                raise
            else:
                elapsed = time.perf_counter() - start
                if log_exit:
                    active_logger.dispatch(
                        format_outcome(
                            func_name,
                            outcome="returned",
                            detail=result,
                            elapsed=elapsed,
                            include_timing=log_timing,
                        ),
                        level=level,
                    )

                return result
        finally:
            for handler in temp_handlers:
                active_logger.removeHandler(hdlr=handler)

    update_wrapper(
        wrapper=wrapper,
        wrapped=func,
    )

    return cast("Decorating", wrapper)


@flexwrap
def log_class(
    cls: type,
    /,
    *,
    level: Level = logging.INFO,
    log_entry: bool = True,
    log_exit: bool = True,
    log_timing: bool = True,
    log_args: bool = True,
    log_exception: bool = True,
    console_handler: logging.Handler | None = None,
    console_formatter: logging.Formatter | None = None,
    file_handler: logging.Handler | None = None,
    file_formatter: logging.Formatter | None = None,
) -> type:
    """
    Wrap every public callable attribute of a class with :func:`_log`.

    Iterate over :func:`dir` of the class, skip dunder attributes,
    and replace each callable with the result of :func:`_log` applied
    to it.

    Parameters
    ----------
    cls
        The class whose public callable attributes are wrapped with
        logging.
    level
        Severity for entry and exit messages.
    log_entry
        Whether to log before invocation.
    log_exit
        Whether to log after successful return.
    log_timing
        Whether to include wall-clock duration.
    log_args
        Whether to include arguments in entry message.
    log_exception
        Whether to log exceptions before re-raising.
    console_handler
        Optional console handler temporarily attached per call.
    console_formatter
        Optional formatter for ``console_handler``.
    file_handler
        Optional file handler temporarily attached per call.
    file_formatter
        Optional formatter for ``file_handler``.

    Returns
    -------
        The same ``cls`` argument, with its public callables
        replaced in place by logged wrappers.

    See Also
    --------
    logging.Logger : Logger class the wrappers emit through.
    Logger.print : Emission helper used inside each wrapper.

    Examples
    --------
    >>> import logging as _logging
    >>> from mayutils.environment.logging import log_class
    >>> _root = _logging.getLogger()
    >>> _saved_handlers = _root.handlers[:]
    >>> _root.handlers = [_logging.NullHandler()]
    >>> @log_class
    ... class Worker:
    ...     def run(self) -> str:
    ...         return "done"
    >>> Worker().run()
    'done'
    >>> _root.handlers = _saved_handlers
    """
    for attr_name in dir(cls):
        if attr_name.startswith("__"):
            continue

        attr = getattr(cls, attr_name)
        if callable(attr):
            setattr(
                cls,
                attr_name,
                log_func(
                    level=level,
                    log_entry=log_entry,
                    log_exit=log_exit,
                    log_timing=log_timing,
                    log_args=log_args,
                    log_exception=log_exception,
                    console_handler=console_handler,
                    console_formatter=console_formatter,
                    file_handler=file_handler,
                    file_formatter=file_formatter,
                )(attr),
            )

    return cls


@flexwrap
def log(
    target: Callable[..., object] | type,
    /,
    *,
    level: Level = logging.INFO,
    log_entry: bool = True,
    log_exit: bool = True,
    log_timing: bool = True,
    log_args: bool = True,
    log_exception: bool = True,
    console_handler: logging.Handler | None = None,
    console_formatter: logging.Formatter | None = None,
    file_handler: logging.Handler | None = None,
    file_formatter: logging.Formatter | None = None,
) -> Callable[..., object] | type:
    """
    Decorate a callable or class with entry, exit and timing logs.

    Dispatch to :func:`_log` for functions and methods or to
    :func:`_log_class` for classes.  Thanks to the
    :func:`mayutils.objects.decorators.flexwrap` wrapper the
    decorator may be used interchangeably as ``@log``, ``@log()`` or
    ``@log(level=..., log_args=False)``.  When applied to a class,
    every public callable (non-dunder) attribute is replaced with an
    instrumented wrapper; when applied to a function, only that
    function is wrapped.

    Parameters
    ----------
    target
        The object being decorated.  Supplied automatically by Python
        when used as ``@log`` without parentheses; set to ``None``
        when the decorator is invoked with only configuration
        arguments.
    level
        Severity used for the entry and successful-return messages.
        Exception messages always use :data:`logging.ERROR`.
    log_entry
        Whether to log a message before invocation.
    log_exit
        Whether to log a message after successful return.
    log_timing
        Whether to include wall-clock duration in messages.
    log_args
        Whether to include function arguments in the entry message.
    log_exception
        Whether to log exceptions before re-raising.
    console_handler
        Optional console handler attached per call.
    console_formatter
        Optional formatter for ``console_handler``.
    file_handler
        Optional file handler attached per call.
    file_formatter
        Optional formatter for ``file_handler``.

    Returns
    -------
        A wrapped callable that logs invocations when ``target`` is
        a function, or ``target`` itself with every public callable
        replaced by a logged wrapper when ``target`` is a class.

    See Also
    --------
    logging.Logger : Logger used by the generated wrappers.
    Logger.print : Helper called inside each logged wrapper.

    Examples
    --------
    >>> import logging as _logging
    >>> _root = _logging.getLogger()
    >>> _saved_handlers = _root.handlers[:]
    >>> _root.handlers = [_logging.NullHandler()]
    >>> @log(level="INFO")
    ... def add(a: int, b: int) -> int:
    ...     return a + b
    >>> add(2, 3)
    5
    >>> _root.handlers = _saved_handlers
    """
    if isinstance(target, type):
        return log_class(
            level=level,
            log_entry=log_entry,
            log_exit=log_exit,
            log_timing=log_timing,
            log_args=log_args,
            log_exception=log_exception,
            console_handler=console_handler,
            console_formatter=console_formatter,
            file_handler=file_handler,
            file_formatter=file_formatter,
        )(target)

    return log_func(
        level=level,
        log_entry=log_entry,
        log_exit=log_exit,
        log_timing=log_timing,
        log_args=log_args,
        log_exception=log_exception,
        console_handler=console_handler,
        console_formatter=console_formatter,
        file_handler=file_handler,
        file_formatter=file_formatter,
    )(target)
