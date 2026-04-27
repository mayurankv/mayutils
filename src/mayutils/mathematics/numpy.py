"""
Provide NumPy-backed numerical helpers for the mathematics namespace.

Centralise thin wrappers and convenience functions built on top of
:mod:`numpy` so that higher-level statistical and modelling code across
:mod:`mayutils.mathematics` can rely on a consistent, typed interface.
Utilities here are array-oriented, operate on :class:`numpy.ndarray`
inputs, and preserve broadcasting semantics and dtype handling inherited
from NumPy. Keeping them in one module avoids scattering low-level
vectorised primitives across the wider :mod:`mayutils` library.

See Also
--------
numpy.ndarray : Core N-dimensional array container used by the helpers.
numpy.linalg : Linear algebra routines that sibling modules build upon.
numpy.typing.ArrayLike : Accepted input protocol for array-coercible values.
mayutils.mathematics : Parent package hosting related numerical utilities.

Examples
--------
>>> from mayutils.mathematics import numpy as mnp
>>> import numpy as np
>>> arr = np.arange(6, dtype=np.float64).reshape(2, 3)
>>> arr.shape
(2, 3)
"""
