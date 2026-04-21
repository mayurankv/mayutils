"""Streamlit helper facade for session-state bootstrap and CSS injection.

This module exposes :class:`StreamlitManager`, a stateless namespace of
static helpers that wrap the most common boilerplate encountered when
authoring a Streamlit app: seeding :data:`streamlit.session_state` with
default values, injecting inline or file-sourced CSS into the page via
``st.markdown`` with ``unsafe_allow_html=True``, and self-launching the
app entry point through a ``streamlit run`` subprocess. The heavy
``streamlit`` dependency is imported lazily under
:func:`mayutils.core.extras.may_require_extras` so importing this module
without the optional extra installed surfaces an actionable install
hint rather than a raw :class:`ModuleNotFoundError`.
"""

import subprocess
from pathlib import Path
from typing import Any

from mayutils.core.extras import may_require_extras

with may_require_extras():
    import streamlit as st
    from streamlit import session_state as ss


class StreamlitManager:
    """Namespace of static helpers for Streamlit session and styling setup.

    The class holds no instance state — every method is a
    :func:`staticmethod` — and exists solely to group related utilities
    behind a shared prefix so call sites read as
    ``StreamlitManager.initialise(...)`` or
    ``StreamlitManager.add_css(...)``. The helpers cover the three
    recurring needs of a Streamlit app: populating
    :data:`streamlit.session_state` with default values without
    clobbering existing entries, pushing raw or file-sourced CSS into
    the rendered page, and launching the app itself as a subprocess.

    Notes
    -----
    ``streamlit`` is imported lazily via
    :func:`mayutils.core.extras.may_require_extras`; callers must have
    the ``streamlit`` extra installed for any of these methods to
    succeed.
    """

    @staticmethod
    def initialise(
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Seed missing keys in ``st.session_state`` with default values.

        Iterates the provided keyword arguments and assigns each one
        to :data:`streamlit.session_state` only when the key is not
        already present. Existing values are left untouched, which
        makes the call idempotent across Streamlit's script reruns —
        user interactions that mutate the session survive the next
        rerun without being reset to the defaults supplied here.

        Parameters
        ----------
        **kwargs
            Default values to register against
            :data:`streamlit.session_state`, keyed by the attribute
            name under which they should be exposed. Keys that already
            exist in the session are skipped, so this acts as a
            ``setdefault``-style initialiser rather than an
            overwriting assignment.
        """
        for key, value in kwargs.items():
            if key not in ss:
                setattr(ss, key, value)

    @staticmethod
    def add_style(
        css: str,
        /,
    ) -> None:
        """Inject an inline CSS rule block into the current Streamlit page.

        The supplied source is wrapped in ``<style>`` tags and emitted
        via :func:`streamlit.markdown` with ``unsafe_allow_html=True``
        so that the browser applies the declarations to the rendered
        app. Use this for small, dynamically-built style blocks; for
        stylesheet files on disk prefer :meth:`add_css` to keep the
        CSS under version control.

        Parameters
        ----------
        css : str
            Raw CSS source — the body that will sit between the opening
            and closing ``<style>`` tags. Passed verbatim into the
            rendered HTML, so any selectors, media queries, or
            declarations it contains are honoured as-is.
        """
        st.markdown(
            body=f"<style>{css}</style>",
            unsafe_allow_html=True,
        )

    @staticmethod
    def add_css(
        path: Path | str,
        /,
    ) -> None:
        """Read a stylesheet from disk and inject it into the page.

        Loads the file at ``path`` with :meth:`pathlib.Path.read_text`
        and forwards the contents to :meth:`add_style`, which wraps
        them in ``<style>`` tags and renders them through
        :func:`streamlit.markdown`. This is the preferred entry point
        for shipping hand-authored CSS alongside the app source.

        Parameters
        ----------
        path : Path or str
            Filesystem location of the ``.css`` file to load. Accepts
            either a :class:`pathlib.Path` or a string, which is
            coerced to :class:`~pathlib.Path` before the read so
            relative paths are resolved against the current working
            directory.
        """
        path = Path(path)
        css = Path(path).read_text()
        StreamlitManager.add_style(css)

    @staticmethod
    def run() -> None:
        """Launch ``main.py`` as a Streamlit app via a subprocess.

        Invokes ``uv run streamlit run main.py`` through
        :func:`subprocess.run`, delegating to ``uv`` to resolve the
        managed environment before handing off to the Streamlit CLI.
        Intended for modules that double as an executable entry point
        (for example ``python -m my_app``) and want to bootstrap the
        Streamlit server without the caller having to remember the
        exact command-line incantation.

        Notes
        -----
        The working directory at call time must contain a ``main.py``
        resolvable to the Streamlit CLI; this helper does not search
        for alternative entry points or forward additional arguments.
        """
        subprocess.run(
            args="uv run streamlit run main.py",
            check=True,
        )
