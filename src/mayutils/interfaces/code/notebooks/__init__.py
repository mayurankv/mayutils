"""
Provide notebook-environment integrations for the ``mayutils`` library.

This package hosts helpers that hook ``mayutils`` into notebook front
ends. Its single submodule,
:mod:`mayutils.interfaces.code.notebooks.jupyter`, exposes the query
pipeline of :func:`mayutils.data.read.read_query` as IPython ``%sql`` /
``%%sql`` line and cell magics: templates are rendered from the
notebook's user namespace, executed through a
:class:`~mayutils.data.read.QueryReader` (defaulting to a cached
:func:`mayutils.interfaces.data.get_env_reader` connection), and the
resulting DataFrame is assigned back into the namespace. Registration
is opt-in via ``%load_ext mayutils.interfaces.code.notebooks.jupyter``
or an explicit ``setup_magic`` call.

See Also
--------
mayutils.interfaces.code.notebooks.jupyter : The ``%sql`` magic implementation.
mayutils.data.read.read_query : Query pipeline invoked by the magic.
mayutils.interfaces.data.get_env_reader : Default reader factory for the magic.

Examples
--------
>>> from mayutils.interfaces.code import notebooks
>>> notebooks.__name__
'mayutils.interfaces.code.notebooks'
"""
