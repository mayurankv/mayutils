import sys

"""CUDA Toolkit libraries lookup utilities.

CUDA Toolkit libraries can be available via either:

- the `cuda-nvcc` and `cuda-nvrtc` conda packages for CUDA 12,
- the `cudatoolkit` conda package for CUDA 11,
- a user supplied location from CUDA_HOME,
- a system wide location,
- package-specific locations (e.g. the Debian NVIDIA packages),
- or can be discovered by the system loader.
"""
if sys.platform == "win32": ...
else:
    _dllnamepattern = ...
    _staticnamepattern = ...

def get_libdevice():  # -> Any:
    ...
def open_libdevice():  # -> bytes:
    ...
def get_cudalib(lib, static=...):  # -> Any | str:

    ...
def open_cudalib(lib):  # -> CDLL:
    ...
def check_static_lib(path):  # -> None:
    ...
def test():  # -> bool:

    ...
