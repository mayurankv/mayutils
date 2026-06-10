"""
Collect integrations with interactive coding environments.

This package groups the ``mayutils`` helpers that plug into the tools a
developer codes in, rather than into external services:
:mod:`mayutils.interfaces.code.notebooks` integrates with Jupyter,
registering the ``%sql`` / ``%%sql`` magics that run queries through
:func:`mayutils.data.read.read_query`, while
:mod:`mayutils.interfaces.code.tui` builds terminal user interfaces on
Textual, including plotting widgets. Each subpackage keeps its optional
dependencies (IPython, Textual) behind dedicated extras so importing
this namespace stays cheap.

See Also
--------
mayutils.interfaces.code.notebooks : Jupyter/IPython notebook integrations.
mayutils.interfaces.code.tui : Terminal user interfaces built on Textual.
mayutils.interfaces : Parent integration namespace.

Examples
--------
>>> from mayutils.interfaces import code
>>> code.__name__
'mayutils.interfaces.code'
"""
