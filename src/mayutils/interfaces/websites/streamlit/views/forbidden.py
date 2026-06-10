"""
Render the packaged default forbidden view for gated Streamlit apps.

This script is the page that
:meth:`mayutils.interfaces.websites.streamlit.StreamlitManager.check_authorisation`
routes authenticated but non-whitelisted users to when no custom
``forbidden_page`` override is supplied. It delegates entirely to
:meth:`~mayutils.interfaces.websites.streamlit.StreamlitManager.forbidden`,
which renders the access-denied notice, the configured contact for
access requests, and a log-out button. The application name and contact
shown are read from ``st.session_state`` as seeded by
:meth:`~mayutils.interfaces.websites.streamlit.StreamlitManager.setup_app`.

See Also
--------
mayutils.interfaces.websites.streamlit.StreamlitManager.forbidden :
    Page body rendered by this view.
mayutils.interfaces.websites.streamlit.StreamlitManager.check_authorisation :
    Gate that registers this view for non-whitelisted users.
mayutils.interfaces.websites.streamlit.StreamlitManager.setup_app :
    High-level wrapper that seeds the session state this view reads.

Examples
--------
>>> import streamlit as st
>>> from mayutils.interfaces.websites.streamlit import VIEWS_PATH
>>> forbidden_page = st.Page(  # doctest: +SKIP
...     page=VIEWS_PATH / "forbidden.py",
...     title="Forbidden",
...     icon=":material/block:",
... )
"""

from mayutils.interfaces.websites.streamlit import StreamlitManager

StreamlitManager.forbidden()
