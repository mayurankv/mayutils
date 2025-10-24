import logging
from _typeshed import Incomplete
from mayutils.environment.filesystem import get_root as get_root
from mayutils.objects.decorators import flexwrap as flexwrap
from pathlib import Path
from typing import Callable, Self

PredefinedLevel: Incomplete
Level = PredefinedLevel | int
CONSOLE_FORMAT: str
FILE_FORMAT: str
root_logger: Incomplete

class Logger(logging.Logger):
    def __init__(self, *args, **kwargs) -> None: ...
    @staticmethod
    def configure(
        log_dir: Path | str = ..., console_level: Level = ..., file_level: Level = ...
    ) -> None: ...
    @classmethod
    def clone(cls, logger: logging.Logger) -> Self: ...
    @classmethod
    def spawn(cls, name: str | None = None) -> Self: ...
    def report(
        self,
        *msgs: str,
        sep: str = " ",
        level: Level | None = None,
        show: bool = False,
        **kwargs,
    ) -> None: ...

logger: Incomplete

@flexwrap
def log(target: Callable | None = None, *args, **kwargs): ...
