"""Core runtime primitives shared across the mayutils library.

This subpackage groups the foundational building blocks that the rest of
mayutils depends upon, including lightweight base classes, shared constants,
and cross-cutting helper types. Modules in this package intentionally avoid
heavy third-party dependencies so that importing mayutils remains cheap and
side-effect free, allowing higher-level subpackages to layer domain-specific
behaviour on top of a stable, minimal core.
"""
