import contextlib

"""
Memory monitoring utilities for measuring memory usage.

Example usage:
    tracker = MemoryTracker("my_function")
    with tracker.monitor():
        my_function()
    # Access data: tracker.rss_delta, tracker.duration, etc.
    # Get formatted string: tracker.get_summary()
"""
_HAS_PSUTIL = ...
IS_SUPPORTED = ...

def get_available_memory() -> int | None: ...
def get_memory_usage() -> dict[str, int | None]: ...

class MemoryTracker:
    pid: int
    name: str
    start_time: float | None
    end_time: float | None
    start_memory: dict[str, int | None] | None
    end_memory: dict[str, int | None] | None
    duration: float | None
    rss_delta: int | None
    def __init__(self, name: str) -> None: ...
    @contextlib.contextmanager
    def monitor(self):  # -> Generator[Self, Any, None]:

        ...
    def get_summary(self) -> str: ...
