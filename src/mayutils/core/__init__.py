"""
Expose the mayutils core subpackage of shared runtime primitives.

Group the foundational building blocks that the rest of mayutils depends
upon, including lightweight base classes, shared constants, and
cross-cutting helper types. Modules in this package intentionally avoid
heavy third-party dependencies so that importing mayutils remains cheap
and side-effect free, allowing higher-level subpackages to layer
domain-specific behaviour on top of a stable, minimal core.

See Also
--------
mayutils.core.extras : Optional-dependency resolution helpers that map
    ``ImportError`` failures back to the extras that provide the missing
    distribution.
mayutils.core.constants : Shared literal values and lookup tables used
    by the rest of the mayutils library.

Examples
--------
>>> import mayutils.core
>>> mayutils.core.__name__
'mayutils.core'
>>> from mayutils.core import extras
>>> hasattr(extras, "may_require_extras")
True
"""
