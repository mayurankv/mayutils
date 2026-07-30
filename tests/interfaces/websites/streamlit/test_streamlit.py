"""Tests for ``mayutils.interfaces.websites.streamlit``.

These cover the :class:`StreamlitManager` helpers: session-state
seeding, the dual-identity email resolution (OAuth vs master-password),
the bcrypt-hash environment lookup, the password login flow, log-out
for password sessions, whitelist-gated navigation, OAuth secrets
injection, and the ``setup_app`` bootstrap (including the fix that
keeps ``navigation_position`` out of session state). UI flows are
exercised through :class:`streamlit.testing.v1.AppTest`, whose script
functions must be self-contained — hence the function-local imports.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("bcrypt")

import bcrypt
from streamlit.runtime.secrets import secrets_singleton
from streamlit.testing.v1 import AppTest

from mayutils.interfaces.websites.streamlit import StreamlitManager

TEST_PASSWORD = b"hunter2"
TEST_PASSWORD_HASH = bcrypt.hashpw(TEST_PASSWORD, bcrypt.gensalt()).decode(encoding="utf-8")
WHITELISTED_EMAIL = "allowed@example.com"
LOGIN_FORM_FIELDS = 2
SEEDED_COUNTER = 5


def _initialise_script() -> None:
    from mayutils.interfaces.websites.streamlit import StreamlitManager

    StreamlitManager.initialise(
        counter=0,
        username="guest",
    )


def _email_script() -> None:
    import streamlit as st

    from mayutils.interfaces.websites.streamlit import StreamlitManager

    st.session_state.resolved_email = StreamlitManager.current_user_email()


def _login_script() -> None:
    from mayutils.interfaces.websites.streamlit import StreamlitManager

    StreamlitManager.login()


def _logout_script() -> None:
    import streamlit as st

    from mayutils.interfaces.websites.streamlit import StreamlitManager

    if not st.session_state.get("logged_out", False):
        st.session_state.logged_out = True
        StreamlitManager.log_out()


def _gate_script() -> None:
    import streamlit as st

    from mayutils.interfaces.websites.streamlit import StreamlitManager

    def home() -> None:
        st.write("home page body")

    page, authorised = StreamlitManager.check_authorisation(
        [st.Page(page=home, title="Home", default=True)],
        email_whitelist=["allowed@example.com"],
    )
    st.session_state.gate_result = (page.title, authorised)
    page.run()


def _setup_app_script() -> None:
    import streamlit as st

    from mayutils.interfaces.websites.streamlit import StreamlitManager

    def home() -> None:
        st.write("home page body")

    StreamlitManager.setup_app(
        "Test App",
        pages=[st.Page(page=home, title="Home", default=True)],
        email_whitelist=["allowed@example.com"],
        description="A test dashboard",
        contact="the test owner",
        counter=5,
    )


class TestInitialise:
    """Tests for :meth:`StreamlitManager.initialise` — setdefault-style session seeding."""

    def test_seeds_missing_keys(self) -> None:
        """Absent keys receive the supplied defaults."""
        at = AppTest.from_function(_initialise_script)
        at.run()

        assert at.session_state["counter"] == 0
        assert at.session_state["username"] == "guest"

    def test_does_not_clobber_existing_keys(self) -> None:
        """Keys already present in the session keep their values across reruns."""
        at = AppTest.from_function(_initialise_script)
        at.session_state["counter"] = SEEDED_COUNTER
        at.run()

        assert at.session_state["counter"] == SEEDED_COUNTER
        assert at.session_state["username"] == "guest"


class TestGetPasswordHash:
    """Tests for :meth:`StreamlitManager.get_password_hash` — env-sourced bcrypt hash."""

    def test_returns_none_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No environment variable means no master password is configured."""
        monkeypatch.delenv("MASTER_PASSWORD_HASH", raising=False)

        assert StreamlitManager.get_password_hash() is None

    def test_returns_none_when_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An empty string is treated the same as an unset variable."""
        monkeypatch.setenv("MASTER_PASSWORD_HASH", "")

        assert StreamlitManager.get_password_hash() is None

    def test_returns_encoded_hash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The stored hash is returned UTF-8 encoded, ready for ``bcrypt.checkpw``."""
        monkeypatch.setenv("MASTER_PASSWORD_HASH", TEST_PASSWORD_HASH)

        assert StreamlitManager.get_password_hash() == TEST_PASSWORD_HASH.encode(encoding="utf-8")

    def test_hash_verifies_against_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A pre-computed hash read from the environment verifies the original password."""
        monkeypatch.setenv("MASTER_PASSWORD_HASH", TEST_PASSWORD_HASH)
        hashed = StreamlitManager.get_password_hash()

        assert hashed is not None
        assert bcrypt.checkpw(password=TEST_PASSWORD, hashed_password=hashed)

    def test_custom_variable_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The environment variable name is overridable positionally."""
        monkeypatch.setenv("OTHER_HASH_VAR", TEST_PASSWORD_HASH)

        assert StreamlitManager.get_password_hash("OTHER_HASH_VAR") == TEST_PASSWORD_HASH.encode(encoding="utf-8")


class TestCurrentUserEmail:
    """Tests for :meth:`StreamlitManager.current_user_email` — dual-identity resolution."""

    def test_returns_none_when_anonymous(self) -> None:
        """Without a password identity or an active ``st.login`` session, no email resolves."""
        at = AppTest.from_function(_email_script)
        at.run()

        assert at.session_state["resolved_email"] is None

    def test_prefers_password_identity(self) -> None:
        """``st.session_state.user_email`` wins over the OAuth identity."""
        at = AppTest.from_function(_email_script)
        at.session_state["user_email"] = "someone@example.com"
        at.run()

        assert at.session_state["resolved_email"] == "someone@example.com"


class TestLogin:
    """Tests for :meth:`StreamlitManager.login` — OAuth button vs password form."""

    def test_oauth_mode_shows_login_button_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without a master password the page offers a single OAuth login button."""
        monkeypatch.delenv("MASTER_PASSWORD_HASH", raising=False)
        at = AppTest.from_function(_login_script)
        at.run()

        assert len(at.button) == 1
        assert at.button[0].key == "log_in"
        assert len(at.text_input) == 0

    def test_password_mode_shows_form(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A configured master password switches the page to an email/password form."""
        monkeypatch.setenv("MASTER_PASSWORD_HASH", TEST_PASSWORD_HASH)
        at = AppTest.from_function(_login_script)
        at.run()

        assert len(at.text_input) == LOGIN_FORM_FIELDS
        assert at.button[0].key == "log_in_password"

    def test_correct_password_sets_user_email(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A successful bcrypt check records the entered email as the session identity."""
        monkeypatch.setenv("MASTER_PASSWORD_HASH", TEST_PASSWORD_HASH)
        at = AppTest.from_function(_login_script)
        at.run()

        at.text_input[0].set_value("someone@example.com")
        at.text_input[1].set_value(TEST_PASSWORD.decode(encoding="utf-8"))
        at.button[0].click().run()

        assert at.session_state["user_email"] == "someone@example.com"

    def test_wrong_password_shows_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A failed bcrypt check surfaces an error and establishes no identity."""
        monkeypatch.setenv("MASTER_PASSWORD_HASH", TEST_PASSWORD_HASH)
        at = AppTest.from_function(_login_script)
        at.run()

        at.text_input[0].set_value("someone@example.com")
        at.text_input[1].set_value("not-the-password")
        at.button[0].click().run()

        assert "user_email" not in at.session_state
        assert len(at.error) == 1
        assert "Incorrect Password" in at.error[0].value


class TestLogOut:
    """Tests for :meth:`StreamlitManager.log_out` — password-session teardown."""

    def test_clears_password_identity_and_reruns(self) -> None:
        """Logging out removes ``user_email`` and resets the welcome flag."""
        at = AppTest.from_function(_logout_script)
        at.session_state["user_email"] = "someone@example.com"
        at.run()

        assert "user_email" not in at.session_state
        assert at.session_state["welcomed"] is False


class TestCheckAuthorisation:
    """Tests for :meth:`StreamlitManager.check_authorisation` — whitelist-gated navigation."""

    def test_anonymous_user_routed_to_login(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No identity routes to the packaged login view, unauthorised."""
        monkeypatch.delenv("MASTER_PASSWORD_HASH", raising=False)
        at = AppTest.from_function(_gate_script)
        at.run()

        assert at.session_state["gate_result"] == ("Login", False)
        assert any("Welcome!" in markdown.value for markdown in at.markdown)

    def test_non_whitelisted_user_routed_to_forbidden(self) -> None:
        """An authenticated email outside the whitelist routes to the forbidden view."""
        at = AppTest.from_function(_gate_script)
        at.session_state["user_email"] = "intruder@example.com"
        at.run()

        assert at.session_state["gate_result"] == ("Forbidden", False)
        assert any("FORBIDDEN" in markdown.value for markdown in at.markdown)

    def test_whitelisted_user_authorised(self) -> None:
        """A whitelisted email gets the real pages and the authorised verdict."""
        at = AppTest.from_function(_gate_script)
        at.session_state["user_email"] = WHITELISTED_EMAIL
        at.run()

        assert at.session_state["gate_result"] == ("Home", True)
        assert at.session_state["welcomed"] is True

    def test_welcome_toast_is_one_shot(self) -> None:
        """The welcome toast is suppressed once ``welcomed`` is set."""
        at = AppTest.from_function(_gate_script)
        at.session_state["user_email"] = WHITELISTED_EMAIL
        at.session_state["welcomed"] = True
        at.run()

        assert at.session_state["gate_result"] == ("Home", True)
        assert len(at.toast) == 0


class TestConfigureOauth:
    """Tests for :meth:`StreamlitManager.configure_oauth` — explicit-value secrets injection."""

    def test_injects_auth_secrets(self) -> None:
        """The injected ``auth`` block is readable back through the secrets singleton."""
        StreamlitManager.configure_oauth(
            "https://app.example.com/oauth2callback",
            cookie_secret="cookie-secret",  # noqa: S106
            providers={
                "google": {
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                    "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
                },
            },
        )

        try:
            auth = secrets_singleton["auth"]
            assert auth["redirect_uri"] == "https://app.example.com/oauth2callback"
            assert auth["cookie_secret"] == "cookie-secret"  # noqa: S105
            assert auth["google"]["client_id"] == "client-id"
        finally:
            secrets_singleton._secrets = None  # noqa: SLF001 # pyright: ignore[reportPrivateUsage]


class TestPlotlyDefaultPreservation:
    """Tests for the module import reasserting the prior Plotly default template."""

    def test_streamlit_import_preserves_plotly_default(self) -> None:
        """Importing the module must not leave streamlit's Plotly theme as the global default.

        Streamlit applies its own ``"streamlit"`` Plotly template as the
        global default at import time; the module snapshot-restores the
        previous default. Needs a fresh interpreter because the module is
        already imported (and cached) in the test process.
        """
        pytest.importorskip("plotly")
        code = (
            "import mayutils.visualisation.graphs.plotly.templates; "
            "import plotly.io as pio; "
            "assert pio.templates.default == 'base'; "
            "import mayutils.interfaces.websites.streamlit; "
            "print(pio.templates.default)"
        )
        result = subprocess.run(
            args=(sys.executable, "-c", code),
            capture_output=True,
            text=True,
            check=True,
        )

        assert result.stdout.strip() == "base"


class TestSetupApp:
    """Tests for :meth:`StreamlitManager.setup_app` — single-call gated bootstrap."""

    def test_authorised_user_sees_app(self) -> None:
        """A whitelisted user gets the seeded state, the title, and the routed page."""
        at = AppTest.from_function(_setup_app_script)
        at.session_state["user_email"] = WHITELISTED_EMAIL
        at.run()

        assert at.session_state["application_name"] == "Test App"
        assert at.session_state["application_contact"] == "the test owner"
        assert at.session_state["counter"] == SEEDED_COUNTER
        assert "Test App" in at.title[0].value
        assert any("home page body" in markdown.value for markdown in at.markdown)

    def test_authorised_user_gets_sidebar_logout(self) -> None:
        """The sidebar log-out button is rendered for authorised users."""
        at = AppTest.from_function(_setup_app_script)
        at.session_state["user_email"] = WHITELISTED_EMAIL
        at.run()

        assert any(button.key == "log_out" for button in at.sidebar.button)

    def test_anonymous_user_sees_login(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without an identity the login view renders and the app chrome does not."""
        monkeypatch.delenv("MASTER_PASSWORD_HASH", raising=False)
        at = AppTest.from_function(_setup_app_script)
        at.run()

        assert len(at.title) == 0
        assert any("Test App" in markdown.value for markdown in at.markdown)
        assert any("the test owner" in markdown.value for markdown in at.markdown)

    def test_navigation_position_never_leaks_into_session_state(self) -> None:
        """The temp-file bug: ``navigation_position`` must never be seeded into session state."""
        at = AppTest.from_function(_setup_app_script)
        at.session_state["user_email"] = WHITELISTED_EMAIL
        at.run()

        assert "navigation_position" not in at.session_state
