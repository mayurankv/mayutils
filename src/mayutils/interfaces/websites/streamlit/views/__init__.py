"""
Package the default views shipped with the Streamlit helper facade.

The scripts in this package are standalone Streamlit pages registered by
:meth:`mayutils.interfaces.websites.streamlit.StreamlitManager.check_authorisation`
when no custom override is supplied: ``login.py`` for unauthenticated
users and ``forbidden.py`` for authenticated users missing from the
whitelist. They are referenced by filesystem path (via the package's
``VIEWS_PATH`` constant) rather than imported, because Streamlit
executes page scripts directly through :func:`streamlit.navigation`;
this ``__init__`` exists so the directory ships as a regular package
inside the wheel.

See Also
--------
mayutils.interfaces.websites.streamlit.StreamlitManager.check_authorisation :
    Gate that registers these views as fallback pages.
mayutils.interfaces.websites.streamlit.StreamlitManager.login : Body of
    the packaged login view.
mayutils.interfaces.websites.streamlit.StreamlitManager.forbidden :
    Body of the packaged forbidden view.

Examples
--------
>>> import streamlit as st
>>> from mayutils.interfaces.websites.streamlit import VIEWS_PATH
>>> login_page = st.Page(  # doctest: +SKIP
...     page=VIEWS_PATH / "login.py",
...     title="Login",
...     icon=":material/key:",
... )
"""
