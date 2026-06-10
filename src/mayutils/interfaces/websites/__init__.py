"""
Group web application framework helpers for the ``mayutils`` library.

This package collects integrations with frameworks used to serve
``mayutils``-powered tools on the web, one subpackage per framework.
Currently it hosts :mod:`mayutils.interfaces.websites.streamlit`, whose
:class:`~mayutils.interfaces.websites.streamlit.StreamlitManager` wraps
common Streamlit boilerplate — session-state seeding, CSS injection,
self-launching apps, and OAuth or master-password authentication gates
— alongside the packaged login and forbidden views it routes
unauthenticated users to. Framework dependencies stay behind optional
extras so importing this namespace remains cheap.

See Also
--------
mayutils.interfaces.websites.streamlit : Streamlit session, styling, and auth facade.
mayutils.interfaces : Parent integration namespace.

Examples
--------
>>> from mayutils.interfaces import websites
>>> websites.__name__
'mayutils.interfaces.websites'
"""
