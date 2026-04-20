import numpy as np
from numba.core.extending import overload
from numpy.polynomial import polynomial as poly
from numpy.polynomial import polyutils as pu

"""
Implementation of operations involving polynomials.
"""

@overload(np.roots)
def roots_impl(p):  # -> Callable[..., _Array1D[Incomplete] | NDArray[Incomplete] | NDArray[float64] | NDArray[complex128]]:
    ...
@overload(pu.trimseq)
def polyutils_trimseq(seq):  # -> Callable[..., Any]:
    ...
@overload(pu.as_series)
def polyutils_as_series(alist, trim=...):  # -> Callable[..., list[Any]]:
    ...
@overload(poly.polyadd)
def numpy_polyadd(c1, c2):  # -> Callable[..., NDArray[float64]]:
    ...
@overload(poly.polysub)
def numpy_polysub(c1, c2):  # -> Callable[..., NDArray[float64]]:
    ...
@overload(poly.polymul)
def numpy_polymul(c1, c2):  # -> Callable[..., _Array1D[float16]]:
    ...
@overload(poly.polyval, prefer_literal=True)
def poly_polyval(x, c, tensor=...):  # -> Callable[..., Any]:
    ...
@overload(poly.polyint)
def poly_polyint(c, m=...):  # -> Callable[..., ndarray[_AnyShape, dtype[object_ | Any]] | ndarray[tuple[int], dtype[object_ | Any]]]:
    ...
@overload(poly.polydiv)
def numpy_polydiv(
    c1, c2
):  # -> Callable[..., tuple[ndarray[_AnyShape, dtype[floating[Any]]], _FloatSeries] | tuple[Any, ndarray[_AnyShape, dtype[floating[Any]]]]]:
    ...
