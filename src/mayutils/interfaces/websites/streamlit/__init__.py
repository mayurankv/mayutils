"""
Provide a Streamlit helper facade for session state, styling, and auth.

This module exposes :class:`StreamlitManager`, a stateless namespace of
static helpers that wrap the most common boilerplate encountered when
authoring a Streamlit app: seeding :data:`streamlit.session_state` with
default values, injecting inline or file-sourced CSS into the page via
``st.markdown`` with ``unsafe_allow_html=True``, self-launching the app
entry point through a ``streamlit run`` subprocess, and gating an app
behind authentication. The auth helpers support two identity sources —
native OAuth via :func:`streamlit.login` (with
:meth:`StreamlitManager.configure_oauth` supplying secrets from
explicit values rather than ``secrets.toml``) and a master-password
fallback verified against a pre-computed bcrypt hash — and route
unauthenticated or non-whitelisted users to packaged login/forbidden
views through :meth:`StreamlitManager.check_authorisation`. The heavy
``streamlit`` and ``bcrypt`` dependencies are imported lazily inside
the helpers under :func:`mayutils.core.extras.may_require_extras`, so
this module imports cleanly without the optional extra installed and a
missing install surfaces an actionable hint at call time rather than a
raw :class:`ModuleNotFoundError`. Importing streamlit normally hijacks
the global Plotly default template with its own ``"streamlit"`` theme;
:func:`import_streamlit` reasserts whichever Plotly default was active
beforehand (for example ``"base"`` from
:mod:`mayutils.visualisation.graphs.plotly.templates`) so registered
mayutils templates keep winning.

See Also
--------
streamlit : Upstream library whose ``markdown``, ``session_state``, and
    auth surfaces this module wraps.
streamlit.session_state : The per-session mutable mapping seeded by
    :meth:`StreamlitManager.initialise`.
streamlit.login : Native OAuth entry point driven by the secrets that
    :meth:`StreamlitManager.configure_oauth` injects.
bcrypt : Password-hash verification backend for the master-password
    login fallback.
mayutils.core.extras.may_require_extras : Lazy-import guard used to turn
    missing ``streamlit`` installs into actionable hints.

Examples
--------
>>> from mayutils.interfaces.websites.streamlit import StreamlitManager
>>> StreamlitManager.initialise(counter=0, username="guest")
>>> StreamlitManager.add_style("body { background: #111; }")
>>> StreamlitManager.add_css("style.css")  # doctest: +SKIP
>>> StreamlitManager.setup_app(  # doctest: +SKIP
...     "My Dashboard",
...     pages=[],
...     email_whitelist=["me@example.com"],
... )
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from mayutils.core.extras import may_require_extras

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping, Sequence

    from streamlit.navigation.page import StreamlitPage

MODULE_PATH = Path(__file__).parent
CSS_PATH = MODULE_PATH / "css"
IMAGES_PATH = MODULE_PATH / "images"
VIEWS_PATH = MODULE_PATH / "views"


def import_streamlit() -> None:
    """
    Import ``streamlit`` while preserving the active Plotly default template.

    Importing streamlit registers its own Plotly template and silently
    makes it the global default
    (``streamlit/elements/lib/streamlit_plotly_theme.py``), overriding
    any default already chosen — e.g. ``"base"`` as set by
    :mod:`mayutils.visualisation.graphs.plotly.templates` at import.
    Snapshot whichever Plotly default is active, perform the guarded
    streamlit import, and reassert the snapshot so registered mayutils
    templates keep winning. When streamlit is already imported the
    import is a no-op and the reassert harmlessly rewrites the current
    default. Every :class:`StreamlitManager` helper calls this before
    importing streamlit itself, so the heavy dependency stays lazy and a
    missing install surfaces an actionable extras hint instead of a raw
    :class:`ModuleNotFoundError`.

    See Also
    --------
    streamlit : Upstream library whose import is wrapped here.
    mayutils.core.extras.may_require_extras : Guard that converts a
        missing streamlit install into an actionable hint.
    mayutils.visualisation.graphs.plotly.templates : Module whose
        ``"base"`` default this helper protects.
    StreamlitManager : Facade whose helpers call this before touching
        streamlit.

    Examples
    --------
    >>> import sys
    >>> from mayutils.interfaces.websites.streamlit import import_streamlit
    >>> import_streamlit()
    >>> "streamlit" in sys.modules
    True
    """
    plotly_templates = getattr(sys.modules.get("plotly.io"), "templates", None)
    plotly_template_default = getattr(plotly_templates, "default", None)

    with may_require_extras():
        import streamlit  # pyright: ignore[reportUnusedImport] # noqa: F401

    if plotly_templates is not None:
        plotly_templates.default = plotly_template_default


class StreamlitManager:
    """
    Group static helpers for Streamlit session, styling, and auth setup.

    The class holds no instance state — every method is a
    :func:`staticmethod` — and exists solely to gather related utilities
    behind a shared prefix so call sites read as
    ``StreamlitManager.initialise(...)`` or
    ``StreamlitManager.setup_app(...)``. The helpers cover the recurring
    needs of a Streamlit app: populating
    :data:`streamlit.session_state` with default values without
    clobbering existing entries, pushing raw or file-sourced CSS into
    the rendered page, launching the app itself as a subprocess, and
    gating the app behind authentication — native OAuth via
    :func:`streamlit.login` or a master-password fallback verified
    against a pre-computed bcrypt hash — with whitelist-based
    authorisation routing. Because Streamlit re-executes the script
    top-to-bottom on every user interaction, these helpers are designed
    to be idempotent across reruns — they detect existing state and only
    perform work when it is necessary.

    See Also
    --------
    streamlit : Upstream framework whose primitives this class wraps.
    streamlit.session_state : Mutable per-session mapping seeded by
        :meth:`initialise`.
    streamlit.login : OAuth flow triggered from the packaged login view.
    bcrypt : Verifier for the master-password login fallback.
    mayutils.core.extras.may_require_extras : Guard that produces
        actionable install hints when ``streamlit`` is missing.

    Notes
    -----
    ``streamlit`` and ``bcrypt`` are imported lazily via
    :func:`mayutils.core.extras.may_require_extras`; callers must have
    the ``streamlit`` extra installed for any of these methods to
    succeed.

    Examples
    --------
    >>> from mayutils.interfaces.websites.streamlit import StreamlitManager
    >>> StreamlitManager.initialise(counter=0)  # doctest: +SKIP
    >>> StreamlitManager.add_style(".stApp { padding: 2rem; }")  # doctest: +SKIP
    >>> StreamlitManager.setup_app(  # doctest: +SKIP
    ...     "My Dashboard",
    ...     pages=[],
    ...     email_whitelist=["me@example.com"],
    ... )
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
        >>> from mayutils.interfaces.websites.streamlit import StreamlitManager
        >>> StreamlitManager.initialise(  # doctest: +SKIP
        ...     counter=0,
        ...     username="guest",
        ...     filters={"region": "uk"},
        ... )  # doctest: +SKIP
        """
        import_streamlit()
        from streamlit import session_state as ss

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
        >>> from mayutils.interfaces.websites.streamlit import StreamlitManager
        >>> StreamlitManager.add_style(  # doctest: +SKIP
        ...     ".stApp { background-color: #0f172a; color: #f8fafc; }",
        ... )  # doctest: +SKIP
        """
        import_streamlit()
        import streamlit as st

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
        >>> from mayutils.interfaces.websites.streamlit import StreamlitManager
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
        >>> from mayutils.interfaces.websites.streamlit import StreamlitManager
        >>> StreamlitManager.run()  # doctest: +SKIP
        """
        subprocess.run(
            args="uv run streamlit run main.py",
            check=True,
        )

    @staticmethod
    def configure_oauth(
        redirect_uri: str,
        /,
        *,
        cookie_secret: str,
        providers: Mapping[str, Mapping[str, str]],
    ) -> None:
        """
        Inject ``st.login`` auth secrets from explicit values.

        Populate Streamlit's secrets singleton with the ``auth`` block
        that :func:`streamlit.login` requires, sourced from the supplied
        arguments instead of a ``secrets.toml`` file. This is the
        deployment-friendly path: containerised apps typically receive
        client identifiers and cookie secrets through environment
        variables, and Streamlit currently offers no public API to feed
        those values into the OAuth flow — see
        https://github.com/streamlit/streamlit/issues/10543. Call this
        before :meth:`check_authorisation` (or :meth:`setup_app`) on
        every script run, and only in environments where the values are
        available — local development with a real ``secrets.toml``
        should skip the call so the file is honoured instead.

        Parameters
        ----------
        redirect_uri
            Absolute callback URL registered with the identity
            provider, ending in ``/oauth2callback`` (for example
            ``"https://my-app.example.com/oauth2callback"``).
        cookie_secret
            Random secret used to sign the identity cookie. Must be
            stable across replicas of the same deployment so sessions
            survive load-balancer hops.
        providers
            Mapping from provider name (the value later passed to
            ``st.login(provider=...)``) to that provider's
            configuration, for example ``client_id``,
            ``client_secret``, and ``server_metadata_url``.

        See Also
        --------
        streamlit.login : Consumer of the injected ``auth`` secrets.
        streamlit.user : Identity surface populated after a successful
            OAuth round trip.
        StreamlitManager.check_authorisation : Gating helper that routes
            unauthenticated users to the login view.
        StreamlitManager.setup_app : High-level wrapper typically called
            immediately after this helper.

        Notes
        -----
        Writes to the private ``secrets_singleton._secrets`` attribute
        because no public setter exists; remove once
        https://github.com/streamlit/streamlit/issues/10543 lands. Any
        ``secrets.toml`` content already loaded is replaced wholesale.

        Examples
        --------
        >>> import os
        >>> from mayutils.interfaces.websites.streamlit import StreamlitManager
        >>> StreamlitManager.configure_oauth(  # doctest: +SKIP
        ...     "https://my-app.example.com/oauth2callback",
        ...     cookie_secret=os.environ["COOKIE_SECRET"],
        ...     providers={
        ...         "google": {
        ...             "client_id": os.environ["GOOGLE_CLIENT_ID"],
        ...             "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        ...             "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
        ...         },
        ...     },
        ... )
        """
        import_streamlit()
        from streamlit.runtime.secrets import secrets_singleton

        # TODO(@mayurankv): Remove when streamlit can pass auth config to st.login directly
        # https://github.com/streamlit/streamlit/issues/10543
        secrets_singleton._secrets = {  # noqa: SLF001 # pyright: ignore[reportPrivateUsage]
            "auth": {
                "redirect_uri": redirect_uri,
                "cookie_secret": cookie_secret,
                **{name: dict(config) for name, config in providers.items()},
            },
        }

    @staticmethod
    def current_user_email() -> str | None:
        """
        Resolve the current user's email across both identity sources.

        Check the password-login identity first —
        ``st.session_state.user_email``, set by :meth:`login` after a
        successful master-password check — and fall back to the OAuth
        identity exposed on :data:`streamlit.user`, trusted only when
        ``st.user.is_logged_in`` reports an active :func:`streamlit.login`
        session. Returning ``None`` signals
        that no identity is established under either mechanism, which
        :meth:`check_authorisation` interprets as "route to the login
        view". Centralising this lookup keeps every other helper
        agnostic of which login mechanism produced the session.

        Returns
        -------
            The authenticated user's email address, or ``None`` when no
            user is logged in via either OAuth or the master-password
            fallback.

        See Also
        --------
        streamlit.user : OAuth identity mapping consulted as the
            fallback source.
        StreamlitManager.login : Page renderer that establishes the
            password-login identity read here.
        StreamlitManager.check_authorisation : Primary consumer that
            gates navigation on the resolved email.
        StreamlitManager.log_out : Tears down whichever identity this
            helper resolves.

        Examples
        --------
        >>> from mayutils.interfaces.websites.streamlit import StreamlitManager
        >>> StreamlitManager.current_user_email() is None
        True
        """
        import_streamlit()
        import streamlit as st
        from streamlit import session_state as ss

        if "user_email" in ss:
            email = ss.user_email
        elif st.user.get("is_logged_in"):
            email = st.user.get("email")
        else:
            email = None

        return email if isinstance(email, str) else None

    @staticmethod
    def get_password_hash(
        var_name: str = "MASTER_PASSWORD_HASH",
        /,
    ) -> bytes | None:
        """
        Read the master-password bcrypt hash from the environment.

        Fetch the environment variable named ``var_name`` and return its
        value encoded to bytes, ready for
        :func:`bcrypt.checkpw`. The variable must hold a *pre-computed*
        bcrypt hash (for example generated once with
        ``bcrypt.hashpw(password, bcrypt.gensalt())``), never the
        plaintext password itself — storing the plaintext and hashing it
        at runtime would reduce the check to a string comparison and
        leak the secret to anything that can read the process
        environment listing. A return of ``None`` means no master
        password is configured, which switches :meth:`login` to its
        OAuth-only mode.

        Parameters
        ----------
        var_name
            Name of the environment variable holding the bcrypt hash.
            Defaults to ``"MASTER_PASSWORD_HASH"``.

        Returns
        -------
            The UTF-8 encoded bcrypt hash, or ``None`` when the variable
            is unset or empty.

        See Also
        --------
        bcrypt.checkpw : Verifier the returned hash is intended for.
        bcrypt.hashpw : Generator used to produce the hash stored in the
            environment.
        StreamlitManager.login : Consumer that switches between OAuth
            and password login based on this value.
        StreamlitManager.check_authorisation : Downstream gate applied
            after a successful password check.

        Examples
        --------
        >>> import bcrypt
        >>> import os
        >>> from mayutils.interfaces.websites.streamlit import StreamlitManager
        >>> StreamlitManager.get_password_hash("UNSET_EXAMPLE_VAR") is None
        True
        >>> os.environ["EXAMPLE_PASSWORD_HASH"] = bcrypt.hashpw(
        ...     b"hunter2",
        ...     bcrypt.gensalt(),
        ... ).decode(encoding="utf-8")
        >>> hashed = StreamlitManager.get_password_hash("EXAMPLE_PASSWORD_HASH")
        >>> bcrypt.checkpw(password=b"hunter2", hashed_password=hashed)
        True
        >>> del os.environ["EXAMPLE_PASSWORD_HASH"]
        """
        password_hash = os.getenv(var_name, None)

        return (
            password_hash.encode(
                encoding="utf-8",
            )
            if password_hash
            else None
        )

    @staticmethod
    def login(
        contact: str | None = None,
        /,
        *,
        provider: str = "google",
    ) -> None:
        """
        Render the login page for a gated Streamlit app.

        Display a welcome header naming the application (from
        ``st.session_state.application_name`` when seeded) and a
        confidentiality notice, then offer whichever login mechanism is
        configured: when :meth:`get_password_hash` finds no master
        password, a single button triggers the native OAuth flow via
        :func:`streamlit.login`; otherwise an email/password form is
        shown and the password is verified against the pre-computed
        bcrypt hash with :func:`bcrypt.checkpw`. A successful password
        check records the entered email in
        ``st.session_state.user_email`` and reruns the script so
        :meth:`check_authorisation` can re-evaluate access. This is the
        body of the packaged ``views/login.py`` and can be called from a
        custom login page as well.

        Parameters
        ----------
        contact
            Markdown fragment naming who to contact about access (for
            example a ``[Name](mailto:...)`` link). When ``None``, falls
            back to ``st.session_state.application_contact`` (seeded by
            :meth:`setup_app`) and finally to a generic phrase.
        provider
            Name of the OAuth provider passed to
            ``st.login(provider=...)``; must match a provider configured
            via :meth:`configure_oauth` or ``secrets.toml``.

        See Also
        --------
        streamlit.login : OAuth flow triggered by the login button.
        bcrypt.checkpw : Verifier applied to the password form input.
        StreamlitManager.get_password_hash : Switch deciding which login
            mechanism is offered.
        StreamlitManager.check_authorisation : Gate that routes
            unauthenticated users to this page.
        StreamlitManager.forbidden : Companion page for authenticated
            but non-whitelisted users.

        Examples
        --------
        >>> from mayutils.interfaces.websites.streamlit import StreamlitManager
        >>> StreamlitManager.login(  # doctest: +SKIP
        ...     "[Jane Doe](mailto:jane.doe@example.com)",
        ...     provider="google",
        ... )
        """
        import_streamlit()
        import streamlit as st
        from streamlit import session_state as ss

        with may_require_extras():
            import bcrypt

        application_name = ss.application_name if "application_name" in ss else "this application"
        if contact is None:
            contact = ss.application_contact if "application_contact" in ss else "the application owner"

        st.markdown(
            body=f"""
                # {application_name}

                **Welcome!**

                This is a private and confidential tool so if you do not have authorised access to see this dashboard,
                contact {contact} immediately.
            """
        )

        password_hash = StreamlitManager.get_password_hash()

        if password_hash is None:
            if st.button(label="Log In", key="log_in"):
                st.login(provider=provider)

        else:
            email = st.text_input(
                label="Email",
            )
            password = st.text_input(
                label="Password",
                type="password",
            ).encode(
                encoding="utf-8",
            )

            if st.button(label="Log In", key="log_in_password"):
                if bcrypt.checkpw(
                    password=password,
                    hashed_password=password_hash,
                ):
                    ss.user_email = email
                    st.rerun()

                else:
                    st.error(
                        body="Incorrect Password",
                        icon=":material/block:",
                    )

    @staticmethod
    def forbidden(
        contact: str | None = None,
        /,
    ) -> None:
        """
        Render the access-denied page for non-whitelisted users.

        Display a prominent ``FORBIDDEN`` notice naming the application
        (from ``st.session_state.application_name`` when seeded),
        greeting the authenticated user by OAuth display name or email
        where available, and directing them to the configured contact
        for access requests. A log-out button is offered so the user can
        switch identities without clearing cookies manually. This is the
        body of the packaged ``views/forbidden.py`` and is shown by
        :meth:`check_authorisation` whenever an authenticated user's
        email is missing from the whitelist.

        Parameters
        ----------
        contact
            Markdown fragment naming who to contact about access (for
            example a ``[Name](mailto:...)`` link). When ``None``, falls
            back to ``st.session_state.application_contact`` (seeded by
            :meth:`setup_app`) and finally to a generic phrase.

        See Also
        --------
        StreamlitManager.check_authorisation : Gate that routes
            non-whitelisted users to this page.
        StreamlitManager.login : Companion page for unauthenticated
            users.
        StreamlitManager.log_out : Handler invoked by the log-out
            button rendered here.
        streamlit.user : Source of the display name used in the
            greeting.

        Examples
        --------
        >>> from mayutils.interfaces.websites.streamlit import StreamlitManager
        >>> StreamlitManager.forbidden(  # doctest: +SKIP
        ...     "[Jane Doe](mailto:jane.doe@example.com)",
        ... )
        """
        import_streamlit()
        import streamlit as st
        from streamlit import session_state as ss

        application_name = ss.application_name if "application_name" in ss else "this application"
        if contact is None:
            contact = ss.application_contact if "application_contact" in ss else "the application owner"

        display_name = st.user.get("name")
        if not isinstance(display_name, str):
            display_name = StreamlitManager.current_user_email()
        greeting = f"Hello {display_name}, this" if display_name is not None else "This"

        st.markdown(
            body=f"""
                # :red[FORBIDDEN]

                :red[Access to **{application_name}** Not Authorised]

                {greeting} is a private and confidential tool and you do not have authorisation to see this dashboard.
                Contact {contact} if you think this is incorrect.
            """
        )

        if st.button(label="Log Out", key="log_out"):
            StreamlitManager.log_out()

    @staticmethod
    def log_out() -> None:
        """
        Log the current user out of whichever identity is active.

        Reset the one-shot welcome flag, then tear down the session
        identity: a password-login session (identified by
        ``st.session_state.user_email``) is cleared and the script is
        rerun so :meth:`check_authorisation` routes back to the login
        view, while an OAuth session is ended through
        :func:`streamlit.logout`, which clears the identity cookie and
        redirects. Handling both mechanisms here means callers can wire
        a single log-out button regardless of how the user signed in —
        something the OAuth-only ``st.logout`` cannot do for
        password-based sessions.

        See Also
        --------
        streamlit.logout : Native cookie-clearing logout used for OAuth
            sessions.
        StreamlitManager.login : Establishes the password-login identity
            cleared here.
        StreamlitManager.current_user_email : Identity lookup spanning
            both mechanisms.
        StreamlitManager.setup_app : Renders the sidebar log-out button
            that calls this handler.

        Examples
        --------
        >>> import streamlit as st
        >>> from mayutils.interfaces.websites.streamlit import StreamlitManager
        >>> if st.button("Log Out"):  # doctest: +SKIP
        ...     StreamlitManager.log_out()
        """
        import_streamlit()
        import streamlit as st
        from streamlit import session_state as ss

        ss.welcomed = False

        if "user_email" in ss:
            del ss.user_email
            st.rerun()

        else:
            st.logout()

    @staticmethod
    def check_authorisation(
        pages: Sequence[StreamlitPage] | Mapping[str, Sequence[StreamlitPage]],
        /,
        *,
        email_whitelist: Collection[str],
        login_page: StreamlitPage | None = None,
        forbidden_page: StreamlitPage | None = None,
        navigation_position: Literal["sidebar", "top", "hidden"] = "sidebar",
    ) -> tuple[StreamlitPage, bool]:
        """
        Gate the app's navigation behind login and a whitelist.

        Resolve the current identity via :meth:`current_user_email` and
        swap the requested page set accordingly: an unauthenticated user
        sees only the login page, an authenticated user whose email is
        not in ``email_whitelist`` sees only the forbidden page, and a
        whitelisted user sees the real ``pages`` (with a one-shot
        welcome toast on first arrival, tracked through
        ``st.session_state.welcomed``). The selected set is registered
        with :func:`streamlit.navigation` and the chosen page is
        returned alongside the authorisation verdict so the caller can
        render privileged chrome (titles, sidebars) only when
        authorised, then invoke ``page.run()``.

        Parameters
        ----------
        pages
            The app's real page set, as accepted by
            :func:`streamlit.navigation` — either a sequence of pages or
            a mapping from section header to pages.
        email_whitelist
            Email addresses permitted to access the app. Matched exactly
            against the resolved identity email.
        login_page
            Page to show unauthenticated users. Defaults to the packaged
            ``views/login.py``, which renders :meth:`login`.
        forbidden_page
            Page to show authenticated but non-whitelisted users.
            Defaults to the packaged ``views/forbidden.py``, which
            renders :meth:`forbidden`.
        navigation_position
            Forwarded to ``st.navigation(position=...)`` — where the
            navigation menu is rendered, or ``"hidden"`` to suppress it.

        Returns
        -------
            A two-tuple of the :class:`~streamlit.navigation.page.StreamlitPage`
            selected by :func:`streamlit.navigation` (which the caller
            must ``run()``) and a boolean that is ``True`` only when the
            current user is authenticated and whitelisted.

        See Also
        --------
        streamlit.navigation : Router this helper feeds the gated page
            set into.
        StreamlitManager.current_user_email : Identity lookup used for
            the gate.
        StreamlitManager.login : Default unauthenticated page body.
        StreamlitManager.forbidden : Default non-whitelisted page body.
        StreamlitManager.setup_app : High-level wrapper that calls this
            helper and renders the surrounding chrome.

        Examples
        --------
        >>> import streamlit as st
        >>> from mayutils.interfaces.websites.streamlit import StreamlitManager
        >>> page, authorised = StreamlitManager.check_authorisation(  # doctest: +SKIP
        ...     [st.Page("views/home.py", title="Home", default=True)],
        ...     email_whitelist=["jane.doe@example.com"],
        ... )
        >>> page.run()  # doctest: +SKIP
        """
        import_streamlit()
        import streamlit as st
        from streamlit import session_state as ss

        authorised = False
        email = StreamlitManager.current_user_email()

        if email is None:
            pages = [
                login_page
                if login_page is not None
                else st.Page(
                    page=VIEWS_PATH / "login.py",
                    title="Login",
                    icon=":material/key:",
                ),
            ]

        elif email not in email_whitelist:
            pages = [
                forbidden_page
                if forbidden_page is not None
                else st.Page(
                    page=VIEWS_PATH / "forbidden.py",
                    title="Forbidden",
                    icon=":material/block:",
                ),
            ]

        else:
            authorised = True
            if "welcomed" not in ss:
                ss.welcomed = False

            if not ss.welcomed:
                display_name = st.user.get("name")
                st.toast(
                    body=f"Welcome {display_name if isinstance(display_name, str) else email}!",
                    icon=":material/lock_open:",
                )
                ss.welcomed = True

        page = st.navigation(
            pages=pages,
            position=navigation_position,
        )

        return page, authorised

    @staticmethod
    def setup_app(
        application_name: str,
        /,
        *,
        pages: Sequence[StreamlitPage] | Mapping[str, Sequence[StreamlitPage]],
        email_whitelist: Collection[str],
        description: str | None = None,
        long_description: str | None = None,
        contact: str | None = None,
        help_url: str | None = None,
        icon: str = "bar_chart",
        tab_icon: str = "monitoring",
        layout: Literal["centered", "wide"] = "wide",
        initial_sidebar_state: Literal["auto", "expanded", "collapsed"] = "collapsed",
        logo: Path | str | None = None,
        css: Path | str | None = None,
        navigation_position: Literal["sidebar", "top", "hidden"] = "sidebar",
        login_page: StreamlitPage | None = None,
        forbidden_page: StreamlitPage | None = None,
        persistent_content: Callable[[], None] | None = None,
        **session_defaults: object,
    ) -> None:
        """
        Bootstrap a gated Streamlit app in a single call.

        Run the full top-of-script sequence for a private dashboard:
        configure the page (title, tab icon, layout, menu items), seed
        :data:`streamlit.session_state` via :meth:`initialise` with the
        application name, contact, and any extra defaults, inject the
        packaged base stylesheet plus an optional app stylesheet, render
        an optional logo, then gate navigation through
        :meth:`check_authorisation`. Whitelisted users get the page
        title, the optional persistent content block, the selected page,
        and a sidebar log-out button; everyone else lands on the login
        or forbidden view. Deployed OAuth apps should call
        :meth:`configure_oauth` immediately before this. The temptation
        to forward navigation options through ``session_defaults`` is
        deliberately avoided — ``navigation_position`` is an explicit
        parameter so it can never leak into session state.

        Parameters
        ----------
        application_name
            Human-readable app name used for the browser tab title, the
            page title, and ``st.session_state.application_name``.
        pages
            The app's real page set, as accepted by
            :func:`streamlit.navigation`.
        email_whitelist
            Email addresses permitted to access the app.
        description
            Short tagline appended to the page title after a colon.
        long_description
            Markdown body for the hamburger menu's *About* entry; the
            entry is hidden when ``None``.
        contact
            Markdown fragment naming who to contact about access; seeded
            into ``st.session_state.application_contact`` for the login
            and forbidden views.
        help_url
            Target for the hamburger menu's *Get help* entry (for
            example a ``mailto:`` link); the entry is hidden when
            ``None``.
        icon
            Material icon name rendered before the page title.
        tab_icon
            Material icon name for the browser tab favicon.
        layout
            Page layout forwarded to ``st.set_page_config``.
        initial_sidebar_state
            Sidebar state forwarded to ``st.set_page_config``.
        logo
            Image path forwarded to :func:`streamlit.logo`; skipped when
            ``None``.
        css
            Additional stylesheet applied via :meth:`add_css` after the
            packaged base stylesheet; skipped when ``None``.
        navigation_position
            Forwarded to ``st.navigation(position=...)``.
        login_page
            Override for the packaged login view, forwarded to
            :meth:`check_authorisation`.
        forbidden_page
            Override for the packaged forbidden view, forwarded to
            :meth:`check_authorisation`.
        persistent_content
            Callback rendered between the title and the routed page on
            every authorised run — navigation bars, filters, or banners
            shared by all pages.
        **session_defaults
            Extra defaults seeded into
            :data:`streamlit.session_state` via :meth:`initialise`.

        See Also
        --------
        StreamlitManager.configure_oauth : Secrets injection to run
            immediately before this in deployed OAuth apps.
        StreamlitManager.check_authorisation : Gating logic this wrapper
            delegates to.
        StreamlitManager.initialise : Session seeding used for the
            application metadata and ``session_defaults``.
        StreamlitManager.add_css : Stylesheet injection used for the
            base and optional app CSS.
        streamlit.set_page_config : Page configuration applied first.

        Examples
        --------
        >>> import streamlit as st
        >>> from mayutils.interfaces.websites.streamlit import StreamlitManager
        >>> StreamlitManager.setup_app(  # doctest: +SKIP
        ...     "My Dashboard",
        ...     pages=[st.Page("views/home.py", title="Home", default=True)],
        ...     email_whitelist=["jane.doe@example.com"],
        ...     description="KPIs at a glance",
        ...     contact="[Jane Doe](mailto:jane.doe@example.com)",
        ...     help_url="mailto:jane.doe@example.com",
        ... )
        """
        import_streamlit()
        import streamlit as st

        st.set_page_config(
            page_title=application_name,
            page_icon=f":material/{tab_icon}:",
            layout=layout,
            initial_sidebar_state=initial_sidebar_state,
            menu_items={
                "About": long_description,
                "Get help": help_url,
                "Report a bug": None,
            },
        )

        StreamlitManager.initialise(
            application_name=application_name,
            **({"application_contact": contact} if contact is not None else {}),
            **session_defaults,
        )

        StreamlitManager.add_css(CSS_PATH / "default.css")
        if css is not None:
            StreamlitManager.add_css(css)

        if logo is not None:
            st.logo(image=str(logo))

        page, authorised = StreamlitManager.check_authorisation(
            pages,
            email_whitelist=email_whitelist,
            login_page=login_page,
            forbidden_page=forbidden_page,
            navigation_position=navigation_position,
        )

        if authorised:
            st.title(
                body=(
                    f":material/{icon}: **:primary[{application_name}]"
                    f"{':' if description is not None else ''}**"
                    f"{f' {description}' if description is not None else ''}"
                ),
            )

            if persistent_content is not None:
                persistent_content()

        page.run()

        if authorised:
            with st.sidebar:
                if st.button(label="Log Out", key="log_out"):
                    StreamlitManager.log_out()
