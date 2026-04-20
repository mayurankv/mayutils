from contextlib import contextmanager

"""
Expose each GPU devices directly.

This module implements a API that is like the "CUDA runtime" context manager
for managing CUDA context stack and clean up.  It relies on thread-local globals
to separate the context stack management of each thread. Contexts are also
shareable among threads.  Only the main thread can destroy Contexts.

Note:
- This module must be imported by the main-thread.

"""

class _DeviceList:
    def __getattr__(self, attr):  # -> list[_DeviceContextManager]:
        ...
    def __getitem__(self, devnum): ...
    def __iter__(self):  # -> Iterator[_DeviceContextManager]:
        ...
    def __len__(self) -> int:  # -> int:
        ...
    @property
    def current(self):  # -> None:

        ...

class _DeviceContextManager:
    def __init__(self, device) -> None: ...
    def __getattr__(self, item):  # -> Any:
        ...
    def __enter__(self):  # -> None:
        ...
    def __exit__(self, exc_type, exc_val, exc_tb):  # -> None:
        ...

class _Runtime:
    def __init__(self) -> None: ...
    @contextmanager
    def ensure_context(self):  # -> Generator[None, Any, None]:

        ...
    def get_or_create_context(self, devnum):  # -> Any:

        ...
    def reset(self):  # -> None:

        ...

_runtime = ...
gpus = ...

def get_context(devnum=...):  # -> Any:

    ...
def require_context(fn):  # -> _Wrapped[Callable[..., Any], Any, Callable[..., Any], Any]:

    ...
def reset():  # -> None:

    ...
