from numba.cuda.cudadrv.error import CudaRuntimeError

"""
CUDA Runtime wrapper.

This provides a very minimal set of bindings, since the Runtime API is not
really used in Numba except for querying the Runtime version.
"""

class CudaRuntimeAPIError(CudaRuntimeError):
    def __init__(self, code, msg) -> None: ...

class Runtime:
    def __init__(self) -> None: ...
    def __getattr__(self, fname):  # -> _Wrapped[Callable[..., Any], Any, Callable[..., Any], None]:
        ...
    def get_version(self):  # -> tuple[int, int]:

        ...
    def is_supported_version(self):  # -> bool:

        ...
    @property
    def supported_versions(
        self,
    ):  # -> tuple[()] | tuple[tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]]:

        ...

runtime = ...

def get_version():  # -> tuple[int, int]:

    ...
