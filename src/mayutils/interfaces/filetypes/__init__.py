"""Filetype-specific authoring and rendering helpers.

This package groups adapters that speak particular document formats
rather than third-party services — for example :mod:`.markdown` for
Mistune-backed Markdown parsing, :mod:`.pptx` for ``python-pptx``
PowerPoint authoring, and :mod:`.pdf` for PyMuPDF + Pillow rendering.
Each submodule is guarded by an optional dependency extra.
"""
