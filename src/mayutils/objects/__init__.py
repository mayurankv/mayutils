"""
Provide utilities for everyday Python objects and data structures.

Group the small, self-contained helpers that operate on generic Python values
rather than on infrastructure or I/O. Each submodule focuses on a single
conceptual kind of object so callers can import narrowly and only pay the
cost of the optional extras they actually need. Heavy third-party backends
(pandas, polars, pendulum, packaging, matplotlib) are gated behind the
relevant extras via :func:`mayutils.core.extras.may_require_extras` so that
importing mayutils remains cheap and side-effect free.

See Also
--------
mayutils.objects.classes : Metaclass helpers, descriptors and chained methods.
mayutils.objects.colours : RGBA colour model with CSS parsing and conversion.
mayutils.objects.dataframes : Pandas, polars and pyarrow dataframe helpers.
mayutils.objects.datetime : Pendulum-backed ``Date``, ``DateTime`` and intervals.
mayutils.objects.decorators : Reusable decorator patterns such as ``flexwrap``.
mayutils.objects.dictionaries : Mapping-level helpers for key/value inversion.
mayutils.objects.functions : Function-level primitives and ``SupportsSetItem``.
mayutils.objects.hashing : Deterministic serialisation for cache-key building.
mayutils.objects.numbers : Human-readable numeric formatting and ordinals.
mayutils.objects.strings : Case conversion and ``None``-coercion helpers.
mayutils.objects.types : Shared typing aliases used across the package.
mayutils.objects.versions : Semantic version manipulation on top of packaging.

Examples
--------
>>> from mayutils import objects
>>> objects.__name__
'mayutils.objects'
>>> import importlib
>>> pkg = importlib.import_module("mayutils.objects")
>>> hasattr(pkg, "__doc__")
True
"""
