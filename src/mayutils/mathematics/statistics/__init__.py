"""
Expose statistics utilities for the ``mayutils.mathematics`` namespace.

This package gathers statistical helpers under the
:mod:`mayutils.mathematics` namespace of the ``mayutils`` library. It
collects descriptive, inferential, and distributional routines used by
pricing, risk, and analytics code paths that depend on consistent
statistical primitives. The submodules wrap common estimators with
project-specific defaults so downstream notebooks produce reproducible
numbers. Keeping the helpers in one place makes it straightforward to
swap implementations when numerical precision or performance tuning is
required.

See Also
--------
scipy.stats : Probability distributions and statistical functions.
statsmodels.api : Estimation and inference for statistical models.
sklearn.metrics : Scoring utilities for model evaluation.
mayutils.mathematics : Parent namespace containing mathematical helpers.

Examples
--------
>>> from mayutils.mathematics import statistics as mstats
>>> mstats.__name__
'mayutils.mathematics.statistics'
"""
