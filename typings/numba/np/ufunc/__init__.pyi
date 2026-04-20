from numba.np.ufunc import _internal

if hasattr(_internal, "PyUFunc_ReorderableNone"):
    PyUFunc_ReorderableNone = ...
