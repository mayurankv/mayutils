from _typeshed import Incomplete
from mayutils.environment.logging import Logger as Logger
from mayutils.objects.decorators import flexwrap as flexwrap
from typing import Callable

logger: Incomplete

@flexwrap
def timing(func: Callable | None = None, *, show: bool = True): ...
