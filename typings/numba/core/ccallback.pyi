from functools import cached_property

from numba.core.compiler_lock import global_compiler_lock
from numba.core.dispatcher import _FunctionCompiler

"""
Implementation of compiled C callbacks (@cfunc).
"""

class _CFuncCompiler(_FunctionCompiler): ...

class CFunc:
    _targetdescr = ...
    def __init__(self, pyfunc, sig, locals, options, pipeline_class=...) -> None: ...
    def enable_caching(self):  # -> None:
        ...
    @global_compiler_lock
    def compile(self):  # -> None:
        ...
    @property
    def native_name(self):  # -> None:

        ...
    @property
    def address(self):  # -> None:

        ...
    @cached_property
    def cffi(self):  # -> CData:

        ...
    @cached_property
    def ctypes(self):  # -> _CFunctionType:

        ...
    def inspect_llvm(self): ...
    @property
    def cache_hits(self):  # -> int:
        ...
    def __call__(self, *args, **kwargs): ...
