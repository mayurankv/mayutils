import operator

"""
Target Options
"""

class TargetOptions:
    class Mapping:
        def __init__(self, flag_name, apply=...) -> None: ...

    def finalize(self, flags, options):  # -> None:

        ...
    @classmethod
    def parse_as_flags(cls, flags, options): ...

_mapping = TargetOptions.Mapping

class DefaultOptions:
    nopython = _mapping("enable_pyobject", operator.not_)
    forceobj = _mapping("force_pyobject")
    looplift = _mapping("enable_looplift")
    _nrt = _mapping("nrt")
    debug = _mapping("debuginfo")
    boundscheck = _mapping("boundscheck")
    nogil = _mapping("release_gil")
    writable_args = _mapping("writable_args")
    no_rewrites = _mapping("no_rewrites")
    no_cpython_wrapper = _mapping("no_cpython_wrapper")
    no_cfunc_wrapper = _mapping("no_cfunc_wrapper")
    parallel = _mapping("auto_parallel")
    fastmath = _mapping("fastmath")
    error_model = _mapping("error_model")
    inline = _mapping("inline")
    forceinline = _mapping("forceinline")
    _dbg_extend_lifetimes = _mapping("dbg_extend_lifetimes")
    _dbg_optnone = _mapping("dbg_optnone")

def include_default_options(*args):  # -> type[OptionMixins]:

    ...
