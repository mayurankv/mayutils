"""Adapters for third-party services, document formats, and application runtimes.

This package groups the integration layers that connect ``mayutils`` to
systems it does not own: filetype-specific document authoring, cloud
storage clients, and Streamlit applications. Each submodule is guarded
by an optional dependency extra so that installing the library stays
lightweight; the full mapping of submodule to extra is documented in
``docs/guides/dependency-groups.md``.

Submodules
----------
cloud
    Cloud storage service facades — e.g. ``google`` for Google Drive.
filetypes
    Filetype-dependent authoring and rendering helpers — ``markdown``
    (Mistune), ``pptx`` (python-pptx), ``pdf`` (PyMuPDF + Pillow),
    ``sheets`` (Google Sheets), ``slides`` (Google Slides), ``docx``,
    and ``xlsx``.
streamlit
    Utilities for building Streamlit dashboards (``streamlit`` extra).
"""
