"""
Expose analytics utilities for the ``mayutils.mathematics`` namespace.

This package gathers higher-level analytical routines built on the
numerical primitives of :mod:`mayutils.mathematics`. Its single
submodule, :mod:`mayutils.mathematics.analytics.attribution`,
decomposes the change in a metric between a baseline and a comparison
scenario into per-factor contributions, offering an exact Shapley
allocation alongside a basic one-at-a-time decomposition with an
explicit interaction remainder — the building blocks of pricing
waterfalls and bridge analyses. Scenarios can be supplied as plain
mappings or as aligned dataframes attributed row by row.

See Also
--------
mayutils.mathematics.analytics.attribution : Shapley and naive metric attribution.
mayutils.mathematics.statistics : Sibling statistical helpers.
mayutils.mathematics : Parent namespace containing mathematical helpers.

Examples
--------
>>> from mayutils.mathematics import analytics
>>> analytics.__name__
'mayutils.mathematics.analytics'
"""
