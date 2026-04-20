"""Shared package-level constants used across :mod:`mayutils`.

Centralises singleton instances and literal values that need to stay
identical across subpackages. Kept intentionally dependency-light so it
remains importable without optional extras installed; heavier shared
singletons live in the feature-specific submodules behind their own
extras.
"""
