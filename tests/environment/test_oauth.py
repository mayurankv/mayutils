"""Tests for ``mayutils.environment.oauth``."""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("keyring")

from mayutils.environment import oauth
from mayutils.environment.oauth import (
    decrypt_token,
    default_parse_token,
    default_store_token,
    encrypt_token,
    generate_fernet_key,
    get_encryption_key,
    load_token,
    oauth_wrapper,
    reset_service_oauth,
    save_token,
)
from mayutils.objects.types import JsonParsed, JsonString

if TYPE_CHECKING:
    from cryptography.fernet import Fernet, InvalidToken
else:
    _fernet = pytest.importorskip("cryptography.fernet")
    Fernet = _fernet.Fernet
    InvalidToken = _fernet.InvalidToken


ENV_KEY = "OAUTH_ENCRYPTION_KEY"


@pytest.fixture
def fake_keyring(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], str]:
    """Replace the real OS keyring with an in-memory ``dict`` store.

    Returns
    -------
        The backing dictionary keyed by ``(service, username)`` so tests can
        inspect what was persisted without touching the system keyring.
    """
    store: dict[tuple[str, str], str] = {}

    def set_password(*, service_name: str, username: str, password: str) -> None:
        store[(service_name, username)] = password

    def get_password(*, service_name: str, username: str) -> str | None:
        return store.get((service_name, username))

    def delete_password(*, service_name: str, username: str) -> None:
        store.pop((service_name, username), None)

    monkeypatch.setattr(oauth.keyring, "set_password", set_password)
    monkeypatch.setattr(oauth.keyring, "get_password", get_password)
    monkeypatch.setattr(oauth.keyring, "delete_password", delete_password)
    return store


@pytest.fixture
def no_env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure ``OAUTH_ENCRYPTION_KEY`` is absent from the environment."""
    monkeypatch.delenv(ENV_KEY, raising=False)


class TestGenerateFernetKey:
    """Tests for :func:`generate_fernet_key` — fresh URL-safe Fernet keys."""

    def test_returns_str_of_length_44(self) -> None:
        """The key is a 44-character ``str`` (URL-safe base64 of 32 bytes)."""
        key = generate_fernet_key()
        assert isinstance(key, str)
        assert len(key) == 44  # noqa: PLR2004

    def test_key_is_usable_by_fernet(self) -> None:
        """The generated key initialises a working :class:`Fernet` cipher."""
        key = generate_fernet_key()
        cipher = Fernet(key.encode())
        plaintext = b"round trip"
        assert cipher.decrypt(cipher.encrypt(plaintext)) == plaintext

    def test_keys_differ_across_calls(self) -> None:
        """Successive calls yield distinct random keys."""
        assert generate_fernet_key() != generate_fernet_key()


class TestGetEncryptionKey:
    """Tests for :func:`get_encryption_key` — reading the ambient key."""

    def test_returns_none_when_unset(self, no_env_key: None) -> None:  # noqa: ARG002
        """An unset ``OAUTH_ENCRYPTION_KEY`` resolves to ``None``."""
        assert get_encryption_key() is None

    def test_returns_encoded_bytes_when_set(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A set variable is returned UTF-8 encoded to ``bytes``."""
        key = generate_fernet_key()
        monkeypatch.setenv(ENV_KEY, key)
        assert get_encryption_key() == key.encode()


class TestEncryptDecryptRoundTrip:
    """Tests for :func:`encrypt_token` / :func:`decrypt_token` with a key."""

    def test_round_trip_with_explicit_key(self) -> None:
        """Encrypting then decrypting with the same explicit key recovers the text."""
        key = generate_fernet_key().encode()
        token = JsonString('{"access_token": "xyz"}')
        ciphertext = encrypt_token(token, encryption_key=key)
        assert isinstance(ciphertext, bytes)
        assert ciphertext != token.encode()
        assert decrypt_token(ciphertext, encryption_key=key) == token

    def test_round_trip_with_env_key(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With no explicit key the cipher key is resolved from the environment."""
        monkeypatch.setenv(ENV_KEY, generate_fernet_key())
        token = JsonString('{"a": 1}')
        ciphertext = encrypt_token(token)
        assert decrypt_token(ciphertext) == token

    def test_wrong_key_raises_invalid_token(self) -> None:
        """Decrypting with a different key raises :class:`InvalidToken`."""
        ciphertext = encrypt_token(
            JsonString('{"a": 1}'),
            encryption_key=generate_fernet_key().encode(),
        )
        with pytest.raises(InvalidToken):
            decrypt_token(ciphertext, encryption_key=generate_fernet_key().encode())


class TestEncryptDecryptPlaintextFallback:
    """Tests for the plaintext fallback when no encryption key is available."""

    def test_encrypt_returns_plaintext_bytes(self, no_env_key: None) -> None:  # noqa: ARG002
        """Without a key the token is returned as raw UTF-8 bytes."""
        token = JsonString('{"a": 1}')
        assert encrypt_token(token) == token.encode()

    def test_decrypt_reads_plaintext_bytes(self, no_env_key: None) -> None:  # noqa: ARG002
        """Without a key the bytes are decoded back to text directly."""
        token = JsonString('{"a": 1}')
        assert decrypt_token(token.encode()) == token

    def test_plaintext_round_trip(self, no_env_key: None) -> None:  # noqa: ARG002
        """Encrypt then decrypt with no key is an identity round trip."""
        token = JsonString('{"nested": {"b": [1, 2]}}')
        assert decrypt_token(encrypt_token(token)) == token


class TestDefaultStoreParse:
    """Tests for :func:`default_store_token` / :func:`default_parse_token`."""

    def test_store_serialises_dict(self) -> None:
        """A plain mapping is serialised to JSON text."""
        assert default_store_token({"access_token": "xyz"}) == '{"access_token": "xyz"}'

    def test_parse_deserialises_json(self) -> None:
        """JSON text is parsed back into a mapping."""
        assert default_parse_token(JsonString('{"access_token": "xyz"}')) == {"access_token": "xyz"}

    def test_store_parse_round_trip(self) -> None:
        """``store`` then ``parse`` recovers an equivalent structure."""
        original = {"a": 1, "b": [True, None], "c": {"d": "e"}}
        assert default_parse_token(default_store_token(original)) == original


class TestSaveLoadToken:
    """Tests for :func:`save_token` / :func:`load_token` against a mocked keyring."""

    def test_save_then_load_round_trip(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fake_keyring: dict[tuple[str, str], str],  # noqa: ARG002
    ) -> None:
        """A token saved under ``(service, username)`` is recoverable verbatim."""
        monkeypatch.setenv(ENV_KEY, generate_fernet_key())
        token = JsonString('{"access_token": "xyz"}')

        save_token(token, service="svc", username="alice")
        assert load_token("svc", username="alice") == token

    def test_saved_value_is_base64_encoded(
        self,
        no_env_key: None,  # noqa: ARG002
        fake_keyring: dict[tuple[str, str], str],
    ) -> None:
        """The stored password is base64 text, decodable back to the token bytes."""
        token = JsonString('{"a": 1}')
        save_token(token, service="svc", username="bob")

        stored = fake_keyring[("svc", "bob")]
        assert base64.b64decode(stored.encode("utf-8")) == token.encode()

    def test_load_missing_entry_raises_value_error(
        self,
        fake_keyring: dict[tuple[str, str], str],  # noqa: ARG002
    ) -> None:
        """Loading a token that was never saved raises :class:`ValueError`."""
        with pytest.raises(ValueError, match="No valid token found"):
            load_token("svc", username="absent")

    def test_corrupt_entry_self_heals_and_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fake_keyring: dict[tuple[str, str], str],
    ) -> None:
        """An undecryptable entry is deleted from the keyring and ``ValueError`` is raised."""
        monkeypatch.setenv(ENV_KEY, generate_fernet_key())
        # Store ciphertext encrypted under a *different* key so decryption fails.
        wrong = encrypt_token(JsonString('{"a": 1}'), encryption_key=generate_fernet_key().encode())
        fake_keyring[("svc", "carol")] = base64.b64encode(wrong).decode("utf-8")

        with pytest.raises(ValueError, match="No valid token found"):
            load_token("svc", username="carol")
        assert ("svc", "carol") not in fake_keyring


class TestResetServiceOauth:
    """Tests for :func:`reset_service_oauth` — clearing a cached token."""

    def test_deletes_keyring_entry(
        self,
        no_env_key: None,  # noqa: ARG002
        fake_keyring: dict[tuple[str, str], str],
    ) -> None:
        """The keyring entry for ``(service, username)`` is removed."""
        save_token(JsonString('{"a": 1}'), service="svc", username="dave")
        assert ("svc", "dave") in fake_keyring

        reset_service_oauth("svc", username="dave")
        assert ("svc", "dave") not in fake_keyring


class TestOauthWrapper:
    """Tests for :func:`oauth_wrapper` — the load / refresh / save cycle."""

    @pytest.fixture(autouse=True)
    def _stub_dotenv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Neutralise the ``load_dotenv`` call made inside the wrapper."""

        def noop_load_dotenv(*_args: object, **_kwargs: object) -> bool:
            return False

        monkeypatch.setattr(oauth, "load_dotenv", noop_load_dotenv)

    def test_first_run_passes_none_token_and_persists(
        self,
        no_env_key: None,  # noqa: ARG002
        fake_keyring: dict[tuple[str, str], str],
    ) -> None:
        """On an empty keyring the routine gets ``token=None`` and the result is saved."""
        seen: dict[str, object] = {}

        @oauth_wrapper
        def routine(*, token: object, **_kwargs: object) -> tuple[dict[str, str], bool]:
            seen["token"] = token
            return {"access_token": "xyz"}, True

        creds = routine("svc", username="erin")
        assert seen["token"] is None
        assert creds == {"access_token": "xyz"}
        assert ("svc", "erin") in fake_keyring

    def test_second_run_hydrates_saved_token(
        self,
        no_env_key: None,  # noqa: ARG002
        fake_keyring: dict[tuple[str, str], str],  # noqa: ARG002
    ) -> None:
        """A subsequent run rehydrates and forwards the previously-saved token."""
        seen: list[object] = []

        @oauth_wrapper
        def routine(*, token: object, **_kwargs: object) -> tuple[dict[str, str], bool]:
            seen.append(token)
            return {"access_token": "xyz"}, True

        routine("svc", username="frank")
        routine("svc", username="frank")
        assert seen[0] is None
        assert seen[1] == {"access_token": "xyz"}

    def test_no_save_when_not_updated(
        self,
        no_env_key: None,  # noqa: ARG002
        fake_keyring: dict[tuple[str, str], str],
    ) -> None:
        """When the routine reports ``updated=False`` nothing is written to the keyring."""

        @oauth_wrapper
        def routine(*, token: object, **_kwargs: object) -> tuple[dict[str, str], bool]:  # noqa: ARG001
            return {"access_token": "xyz"}, False

        creds = routine("svc", username="grace")
        assert creds == {"access_token": "xyz"}
        assert ("svc", "grace") not in fake_keyring

    def test_forwards_extra_kwargs(
        self,
        no_env_key: None,  # noqa: ARG002
        fake_keyring: dict[tuple[str, str], str],  # noqa: ARG002
    ) -> None:
        """Additional keyword arguments are forwarded verbatim to the routine."""
        seen: dict[str, object] = {}

        @oauth_wrapper
        def routine(*, token: object, **kwargs: object) -> tuple[dict[str, str], bool]:  # noqa: ARG001
            seen.update(kwargs)
            return {"access_token": "xyz"}, False

        routine("svc", username="heidi", scopes=["a", "b"])
        assert seen["scopes"] == ["a", "b"]

    def test_custom_store_and_parse_hooks(
        self,
        no_env_key: None,  # noqa: ARG002
        fake_keyring: dict[tuple[str, str], str],  # noqa: ARG002
    ) -> None:
        """Custom ``store_token`` / ``parse_token`` hooks drive serialisation."""
        seen: list[object] = []

        def store(credentials: object, /) -> JsonString:
            return JsonString(json.dumps({"wrapped": credentials}))

        def parse(token: JsonString, /) -> JsonParsed:
            return JsonParsed(json.loads(token)["wrapped"])

        @oauth_wrapper(store_token=store, parse_token=parse)
        def routine(*, token: object, **_kwargs: object) -> tuple[dict[str, str], bool]:
            seen.append(token)
            return {"access_token": "xyz"}, True

        routine("svc", username="ivan")
        routine("svc", username="ivan")
        assert seen[0] is None
        assert seen[1] == {"access_token": "xyz"}
