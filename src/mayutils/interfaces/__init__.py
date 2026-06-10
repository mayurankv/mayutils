"""
Group integrations with external services, formats, and frontends.

This package is the integration layer of the ``mayutils`` library:
code that talks to a system outside the Python process lives in a
dedicated subpackage here. :mod:`mayutils.interfaces.cloud` wraps
third-party cloud storage providers, :mod:`mayutils.interfaces.code`
hosts coding-environment integrations such as Jupyter magics and
Textual terminal UIs, :mod:`mayutils.interfaces.data` builds database
readers and streamers from environment configuration,
:mod:`mayutils.interfaces.filetypes` adapts document and tabular file
formats, and :mod:`mayutils.interfaces.websites` provides web
application framework helpers. Each subpackage guards its heavy
dependencies behind optional extras so a minimal install stays
lightweight.

See Also
--------
mayutils.interfaces.cloud : Cloud storage service facades.
mayutils.interfaces.code : Coding-environment integrations (notebooks, TUIs).
mayutils.interfaces.data : Environment-driven database reader factories.
mayutils.interfaces.filetypes : Filetype authoring and rendering adapters.
mayutils.interfaces.websites : Web application framework helpers.

Examples
--------
>>> from mayutils import interfaces
>>> interfaces.__name__
'mayutils.interfaces'
"""
