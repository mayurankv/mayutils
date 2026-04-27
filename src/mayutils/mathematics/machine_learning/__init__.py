"""
Expose machine-learning utilities for the ``mayutils.mathematics`` namespace.

This package gathers machine-learning helpers that sit under the
:mod:`mayutils.mathematics` namespace of the ``mayutils`` library. It
provides the entry point for shared modelling primitives, fitting
routines, and evaluation helpers used across downstream pricing and
analytics workflows. The submodules wrap scikit-learn-compatible
estimators with project-specific defaults so notebooks and batch
pipelines produce reproducible numbers. Keeping the helpers in one
place makes it straightforward to swap implementations when training
cost, calibration quality, or inference latency require retuning.

See Also
--------
sklearn.base.BaseEstimator : Canonical estimator interface the helpers build on.
sklearn.pipeline.Pipeline : Composition primitive for chaining preprocessors and models.
sklearn.model_selection.cross_validate : Cross-validation utility used in evaluation helpers.
mayutils.mathematics : Parent namespace containing mathematical helpers.
mayutils.mathematics.statistics : Sibling statistical primitives used alongside ML models.

Examples
--------
>>> from mayutils.mathematics import machine_learning as mml
>>> mml.__name__
'mayutils.mathematics.machine_learning'
"""
