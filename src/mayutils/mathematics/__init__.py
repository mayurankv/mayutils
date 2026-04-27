"""
Provide mathematical utilities for the mayutils library.

Group numerical and mathematical helpers used throughout mayutils, including
NumPy-backed routines, Numba-accelerated kernels, statistical primitives, and
machine learning support code. Offer a common namespace for lower-level
computation that underpins higher-level data analysis, modelling, and
visualisation modules. Submodules expose focused APIs so consumers can opt in
to only the numerical surface they require.

See Also
--------
mayutils.mathematics.numpy : NumPy-backed array and linear-algebra helpers.
mayutils.mathematics.numba : Numba-accelerated numerical kernels.
mayutils.mathematics.statistics : Statistical primitives and distributions.
mayutils.mathematics.machine_learning : Machine learning support utilities.

Examples
--------
>>> from mayutils import mathematics
>>> mathematics.__name__
'mayutils.mathematics'
>>> import importlib
>>> pkg = importlib.import_module("mayutils.mathematics")
>>> hasattr(pkg, "__doc__")
True
"""
