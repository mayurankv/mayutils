"""
Render the packaged default login view for gated Streamlit apps.

This script is the page that
:meth:`mayutils.interfaces.websites.streamlit.StreamlitManager.check_authorisation`
routes unauthenticated users to when no custom ``login_page`` override
is supplied. It delegates entirely to
:meth:`~mayutils.interfaces.websites.streamlit.StreamlitManager.login`,
which renders the welcome header and confidentiality notice and offers
either the native OAuth flow or the master-password form depending on
whether a ``MASTER_PASSWORD_HASH`` is configured. The application name
and contact shown are read from ``st.session_state`` as seeded by
:meth:`~mayutils.interfaces.websites.streamlit.StreamlitManager.setup_app`.

See Also
--------
mayutils.interfaces.websites.streamlit.StreamlitManager.login : Page
    body rendered by this view.
mayutils.interfaces.websites.streamlit.StreamlitManager.check_authorisation :
    Gate that registers this view for unauthenticated users.
mayutils.interfaces.websites.streamlit.StreamlitManager.setup_app :
    High-level wrapper that seeds the session state this view reads.

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

from mayutils.interfaces.websites.streamlit import StreamlitManager

StreamlitManager.login()
