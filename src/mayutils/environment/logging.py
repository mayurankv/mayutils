import logging
# from logging.handlers import RotatingFileHandler
# from datetime import datetime
from pathlib import Path
import time
from rich.logging import RichHandler
from typing import Any, Callable, Optional, Self
from inspect import getmodule, currentframe
from functools import wraps

from mayutils.environment.filesystem import get_root
from typing import Literal

from mayutils.objects.decorators import flexwrap

PredefinedLevel = Literal["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
Level = PredefinedLevel | int

CONSOLE_FORMAT = "%(message)s"
FILE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

root_logger = logging.getLogger()


def setup_logging(
    log_dir: Path | str = get_root() / "logs",
    console_level: Level = logging.WARNING,
    file_level: Level = logging.NOTSET,
) -> None:
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    handlers = dict(
        console=RichHandler(
            level=console_level,
            rich_tracebacks=True,
            show_time=True,
            show_path=True,
        ),
        # file=RotatingFileHandler(
        #     filename=log_dir / f"{datetime.now():%Y-%m-%d}.log",
        #     maxBytes=10_485_760,
        #     backupCount=5,
        #     encoding="utf-8",
        # ),
    )
    handlers["console"].setFormatter(fmt=logging.Formatter(fmt=CONSOLE_FORMAT))
    # handlers["file"].setFormatter(fmt=logging.Formatter(fmt=FILE_FORMAT))
    # handlers["file"].setLevel(level=file_level)

    root_logger.handlers.clear()
    for handler in handlers.values():
        root_logger.addHandler(hdlr=handler)
    root_logger.setLevel(level=logging.DEBUG)

    # module = sys.modules[__name__]

    # for name, obj in list(vars(module).items()):
    #     if name in ["log"]:
    #         continue

    #     if isfunction(obj) and obj.__module__ == __name__:
    #         if name.startswith("__") or hasattr(obj, "__wrapped__"):
    #             continue

    #         setattr(module, name, log(obj))


class Logger(logging.Logger):
    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        return super().__init__(
            *args,
            **kwargs,
        )

    @classmethod
    def clone(
        cls,
        logger: logging.Logger,
    ) -> Self:
        clone = cls(
            logger.name,
            logger.level,
        )
        for handler in logger.handlers:
            clone.addHandler(handler)

        for filter in logger.filters:
            clone.addFilter(filter)

        clone.parent = logger.parent

        return clone

    @classmethod
    def spawn(
        cls,
        name: Optional[str] = None,
    ) -> Self:
        if name is None:
            frame = currentframe()
            if frame is None:
                return cls(root_logger)

            module = getmodule(frame.f_back)

            name = getattr(module, "__name__", "__main__")
            if not name or isinstance(name, str) and name == logging.root.name:
                return cls(root_logger)

        logger = logging.getLogger(name=name)

        return cls.clone(logger=logger)

    def log(
        self,
        *msgs: str,
        sep: str = " ",
        level: Optional[Level] = None,
        show: bool = False,
        **kwargs,
    ) -> None:
        msg = sep.join(msgs)

        self.__log(
            msg=msg,
            level=level,
            **kwargs,
        )

        end = kwargs.pop("end", "\n")

        if show:
            print(msg, end=end)

        return

    def __log(
        self,
        msg: str,
        level: Optional[Level] = None,
        **kwargs,
    ) -> str:
        level_int = (
            logging._nameToLevel.get(level, None) if isinstance(level, str) else level
        )
        if level_int is None:
            level_int = self.getEffectiveLevel()

        super().log(
            level=level_int,
            msg=msg,
            **kwargs,
        )

        return msg


logger = Logger.spawn()


def _log(
    func,
    level: Level = logging.INFO,
    show: bool = False,
    *args,
    **kwargs,
) -> Callable[..., Any]:
    @wraps(wrapped=func)
    def wrapper(
        *args,
        **kwargs,
    ) -> Any:
        logger.log(
            f"Calling function: {func.__name__}",
            level=level,
            show=show,
        )
        start = time.perf_counter()

        try:
            result = func(
                *args,
                **kwargs,
            )
            end = time.perf_counter()
            logger.log(
                f"Function {func.__name__} returned ({end - start:.2f}s): {result}",
                level=level,
                show=show,
            )

            return result
        except Exception as exception:
            end = time.perf_counter()
            logger.log(
                f"Function {func.__name__} raised an exception ({end - start:.2f}s): {exception}",
                level=logging.ERROR,
                exc_info=True,
                show=show,
            )
            raise

    return wrapper


def _log_class(
    cls,
    *args,
    **kwargs,
):
    for attr_name in dir(cls):
        if attr_name.startswith("__"):
            continue

        attr = getattr(cls, attr_name)
        if callable(attr):
            setattr(
                cls,
                attr_name,
                _log(
                    attr,
                    *args,
                    **kwargs,
                ),
            )

    return cls


@flexwrap
def log(
    target: Optional[Callable] = None,
    *args,
    **kwargs,
):
    if target is None:
        raise ValueError("No target provided")
    if isinstance(target, type):
        return _log_class(
            cls=target,
            *args,
            **kwargs,
        )
    else:
        return _log(
            func=target,
            *args,
            **kwargs,
        )
