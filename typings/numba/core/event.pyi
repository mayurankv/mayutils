import abc
import enum
from contextlib import contextmanager

from numba.core import config

"""
The ``numba.core.event`` module provides a simple event system for applications
to register callbacks to listen to specific compiler events.

The following events are built in:

- ``"numba:compile"`` is broadcast when a dispatcher is compiling. Events of
  this kind have ``data`` defined to be a ``dict`` with the following
  key-values:

  - ``"dispatcher"``: the dispatcher object that is compiling.
  - ``"args"``: the argument types.
  - ``"return_type"``: the return type.

- ``"numba:compiler_lock"`` is broadcast when the internal compiler-lock is
  acquired. This is mostly used internally to measure time spent with the lock
  acquired.

- ``"numba:llvm_lock"`` is broadcast when the internal LLVM-lock is acquired.
  This is used internally to measure time spent with the lock acquired.

- ``"numba:run_pass"`` is broadcast when a compiler pass is running.

    - ``"name"``: pass name.
    - ``"qualname"``: qualified name of the function being compiled.
    - ``"module"``: module name of the function being compiled.
    - ``"flags"``: compilation flags.
    - ``"args"``: argument types.
    - ``"return_type"`` return type.

Applications can register callbacks that are listening for specific events using
``register(kind: str, listener: Listener)``, where ``listener`` is an instance
of ``Listener`` that defines custom actions on occurrence of the specific event.
"""

class EventStatus(enum.Enum):
    START = ...
    END = ...

_builtin_kinds = ...

class Event:
    def __init__(self, kind, status, data=..., exc_details=...) -> None: ...
    @property
    def kind(self):  # -> Any:

        ...
    @property
    def status(self):  # -> Any:

        ...
    @property
    def data(self):  # -> None:

        ...
    @property
    def is_start(self): ...
    @property
    def is_end(self): ...
    @property
    def is_failed(self):  # -> bool:

        ...

    __repr__ = ...

_registered = ...

def register(kind, listener):  # -> None:

    ...
def unregister(kind, listener):  # -> None:

    ...
def broadcast(event):  # -> None:

    ...

class Listener(abc.ABC):
    @abc.abstractmethod
    def on_start(self, event):  # -> None:

        ...
    @abc.abstractmethod
    def on_end(self, event):  # -> None:

        ...
    def notify(self, event):  # -> None:

        ...

class TimingListener(Listener):
    def __init__(self) -> None: ...
    def on_start(self, event):  # -> None:
        ...
    def on_end(self, event):  # -> None:
        ...
    @property
    def done(self):  # -> bool:

        ...
    @property
    def duration(self):  # -> Any | float:

        ...

class RecordingListener(Listener):
    def __init__(self) -> None: ...
    def on_start(self, event):  # -> None:
        ...
    def on_end(self, event):  # -> None:
        ...

@contextmanager
def install_listener(kind, listener):  # -> Generator[Any, Any, None]:

    ...
@contextmanager
def install_timer(kind, callback):  # -> Generator[TimingListener, Any, None]:

    ...
@contextmanager
def install_recorder(kind):  # -> Generator[RecordingListener, Any, None]:

    ...
def start_event(kind, data=...):  # -> None:

    ...
def end_event(kind, data=..., exc_details=...):  # -> None:

    ...
@contextmanager
def trigger_event(kind, data=...):  # -> Generator[None, Any, None]:

    ...

if config.CHROME_TRACE: ...
