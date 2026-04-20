from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import no_type_check

import coverage
from numba.core import ir

"""
Implement code coverage support.

Currently contains logic to extend ``coverage`` with lines covered by the
compiler.
"""

@no_type_check
def get_active_coverage():  # -> Coverage | None:

    ...

_the_registry: Callable[[], NotifyLocBase | None] = ...

def get_registered_loc_notify() -> Sequence[NotifyLocBase]: ...

class NotifyLocBase(ABC):
    @abstractmethod
    def notify(self, loc: ir.Loc) -> None: ...
    @abstractmethod
    def close(self) -> None: ...

class NotifyCompilerCoverage(NotifyLocBase):
    def __init__(self, collector) -> None: ...
    def notify(self, loc: ir.Loc):  # -> None:
        ...
    def close(self):  # -> None:
        ...

if coverage_available:
    @dataclass(kw_only=True)
    class NumbaTracer(coverage.types.Tracer):
        data: coverage.types.TTraceData
        trace_arcs: bool
        should_trace: coverage.types.TShouldTraceFn
        should_trace_cache: Mapping[str, coverage.types.TFileDisposition | None]
        should_start_context: coverage.types.TShouldStartContextFn | None
        switch_context: Callable[[str | None], None] | None
        lock_data: Callable[[], None]
        unlock_data: Callable[[], None]
        warn: coverage.types.TWarnFn
        packed_arcs: bool
        _activity: bool = ...
        def start(self) -> coverage.types.TTraceFn | None: ...
        def stop(self) -> None: ...
        def activity(self) -> bool: ...
        def reset_activity(self) -> None: ...
        def get_stats(self) -> dict[str, int] | None: ...
        def trace(self, loc: ir.Loc) -> None: ...
