"""
Provide a Streamlit helper facade for session-state bootstrap and CSS injection.

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

See Also
--------
streamlit : Upstream library whose ``markdown`` and ``session_state``
    surfaces this module wraps.
streamlit.session_state : The per-session mutable mapping seeded by
    :meth:`StreamlitManager.initialise`.
streamlit.cache_data : Complementary decorator for memoising pure
    computations across reruns; pairs well with session defaults seeded
    here.
mayutils.core.extras.may_require_extras : Lazy-import guard used to turn
    missing ``streamlit`` installs into actionable hints.

Examples
--------
>>> from mayutils.interfaces.streamlit import StreamlitManager
>>> StreamlitManager.initialise(counter=0, username="guest")
>>> StreamlitManager.add_style("body { background: #111; }")
>>> StreamlitManager.add_css("style.css")  # doctest: +SKIP
"""

import subprocess
from pathlib import Path

from mayutils.core.extras import may_require_extras

with may_require_extras():
    import streamlit as st
    from streamlit import session_state as ss


class StreamlitManager:
    """
    Group static helpers for Streamlit session and styling setup.

    The class holds no instance state — every method is a
    :func:`staticmethod` — and exists solely to gather related utilities
    behind a shared prefix so call sites read as
    ``StreamlitManager.initialise(...)`` or
    ``StreamlitManager.add_css(...)``. The helpers cover the three
    recurring needs of a Streamlit app: populating
    :data:`streamlit.session_state` with default values without
    clobbering existing entries, pushing raw or file-sourced CSS into
    the rendered page, and launching the app itself as a subprocess.
    Because Streamlit re-executes the script top-to-bottom on every user
    interaction, these helpers are designed to be idempotent across
    reruns — they detect existing state and only perform work when it is
    necessary.

    See Also
    --------
    streamlit : Upstream framework whose primitives this class wraps.
    streamlit.session_state : Mutable per-session mapping seeded by
        :meth:`initialise`.
    streamlit.cache_data : Decorator for memoising expensive computations
        across script reruns, complementary to session defaults.
    mayutils.core.extras.may_require_extras : Guard that produces
        actionable install hints when ``streamlit`` is missing.

    Notes
    -----
    ``streamlit`` is imported lazily via
    :func:`mayutils.core.extras.may_require_extras`; callers must have
    the ``streamlit`` extra installed for any of these methods to
    succeed.

    Examples
    --------
    >>> from mayutils.interfaces.streamlit import StreamlitManager
    >>> StreamlitManager.initialise(counter=0)  # doctest: +SKIP
    >>> StreamlitManager.add_style(".stApp { padding: 2rem; }")  # doctest: +SKIP
    >>> StreamlitManager.add_css("assets/theme.css")  # doctest: +SKIP
    >>> StreamlitManager.run()  # doctest: +SKIP
    """

    @staticmethod
    def initialise(
        **kwargs: object,
    ) -> None:
        """
        Seed missing keys in ``st.session_state`` with default values.

        Iterate the provided keyword arguments and assign each one to
        :data:`streamlit.session_state` only when the key is not already
        present. Existing values are left untouched, which makes the
        call idempotent across Streamlit's script reruns — user
        interactions that mutate the session survive the next rerun
        without being reset to the defaults supplied here. This is the
        recommended pattern for bootstrapping counters, form inputs, and
        any other persistent per-user state at the top of the script.

        Parameters
        ----------
        **kwargs
            Default values to register against
            :data:`streamlit.session_state`, keyed by the attribute
            name under which they should be exposed. Keys that already
            exist in the session are skipped, so this acts as a
            ``setdefault``-style initialiser rather than an overwriting
            assignment.

        See Also
        --------
        streamlit.session_state : The mapping mutated by this helper.
        streamlit.cache_data : Decorator for memoising expensive work
            keyed off values seeded here.
        StreamlitManager.add_style : Sibling helper for injecting CSS
            alongside the state it accompanies.
        StreamlitManager.add_css : Sibling helper that loads CSS from
            disk rather than an in-memory string.

        Examples
        --------
        >>> from mayutils.interfaces.streamlit import StreamlitManager
        >>> StreamlitManager.initialise(  # doctest: +SKIP
        ...     counter=0,
        ...     username="guest",
        ...     filters={"region": "uk"},
        ... )  # doctest: +SKIP
        """
        for key, value in kwargs.items():
            if key not in ss:
                setattr(ss, key, value)

    @staticmethod
    def add_style(
        css: str,
        /,
    ) -> None:
        """
        Inject an inline CSS rule block into the current Streamlit page.

        Wrap the supplied source in ``<style>`` tags and emit it via
        :func:`streamlit.markdown` with ``unsafe_allow_html=True`` so
        that the browser applies the declarations to the rendered app.
        The block is appended on every script rerun, so prefer idempotent
        rule sets that do not rely on ordering relative to other calls.
        Use this for small, dynamically-built style blocks; for
        stylesheet files on disk prefer :meth:`add_css` to keep the
        CSS under version control.

        Parameters
        ----------
        css
            Raw CSS source — the body that will sit between the opening
            and closing ``<style>`` tags. Passed verbatim into the
            rendered HTML, so any selectors, media queries, or
            declarations it contains are honoured as-is.

        See Also
        --------
        streamlit.markdown : Renderer used to emit the ``<style>`` block.
        StreamlitManager.add_css : Wrapper that reads CSS from disk
            before delegating to this helper.
        StreamlitManager.initialise : Sibling helper for seeding session
            state alongside the styling applied here.
        streamlit.session_state : Mapping whose state may drive the
            dynamically-constructed CSS passed in.

        Examples
        --------
        >>> from mayutils.interfaces.streamlit import StreamlitManager
        >>> StreamlitManager.add_style(  # doctest: +SKIP
        ...     ".stApp { background-color: #0f172a; color: #f8fafc; }",
        ... )  # doctest: +SKIP
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
        """
        Read a stylesheet from disk and inject it into the page.

        Load the file at ``path`` with :meth:`pathlib.Path.read_text`
        and forward the contents to :meth:`add_style`, which wraps
        them in ``<style>`` tags and renders them through
        :func:`streamlit.markdown`. The file is re-read on every
        Streamlit rerun because the helper performs no caching; wrap it
        in :func:`streamlit.cache_data` if the stylesheet is large and
        stable. This is the preferred entry point for shipping
        hand-authored CSS alongside the app source.

        Parameters
        ----------
        path
            Filesystem location of the ``.css`` file to load. Accepts
            either a :class:`pathlib.Path` or a string, which is
            coerced to :class:`~pathlib.Path` before the read so
            relative paths are resolved against the current working
            directory.

        See Also
        --------
        streamlit.markdown : Ultimate renderer invoked via
            :meth:`add_style`.
        streamlit.cache_data : Decorator to memoise the file read across
            reruns when the stylesheet is large.
        StreamlitManager.add_style : Lower-level helper that emits the
            loaded CSS into the page.
        StreamlitManager.initialise : Sibling helper for seeding session
            state alongside the stylesheet applied here.

        Examples
        --------
        >>> from mayutils.interfaces.streamlit import StreamlitManager
        >>> StreamlitManager.add_css("assets/app.css")  # doctest: +SKIP
        """
        path = Path(path)
        css = Path(path).read_text()
        StreamlitManager.add_style(css)

    @staticmethod
    def run() -> None:
        """
        Launch ``main.py`` as a Streamlit app via a subprocess.

        Invoke ``uv run streamlit run main.py`` through
        :func:`subprocess.run`, delegating to ``uv`` to resolve the
        managed environment before handing off to the Streamlit CLI.
        The call blocks until the Streamlit server exits, and a non-zero
        return code raises :class:`subprocess.CalledProcessError`
        because ``check=True`` is set. Intended for modules that double
        as an executable entry point (for example ``python -m my_app``)
        and want to bootstrap the Streamlit server without the caller
        having to remember the exact command-line incantation.

        See Also
        --------
        streamlit : Framework whose CLI is invoked by the subprocess.
        streamlit.session_state : Per-session state populated once the
            launched app starts executing.
        StreamlitManager.initialise : Sibling helper typically called
            from inside the launched ``main.py`` to seed session state.
        StreamlitManager.add_css : Sibling helper for applying styling
            from the launched app.

        Notes
        -----
        The working directory at call time must contain a ``main.py``
        resolvable to the Streamlit CLI; this helper does not search
        for alternative entry points or forward additional arguments.
        A non-zero exit raises :class:`subprocess.CalledProcessError`
        because ``check=True`` is passed to :func:`subprocess.run`.

        Examples
        --------
        >>> from mayutils.interfaces.streamlit import StreamlitManager
        >>> StreamlitManager.run()  # doctest: +SKIP
        """
        subprocess.run(
            args="uv run streamlit run main.py",
            check=True,
        )
