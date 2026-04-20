"""Google OAuth credential management with encrypted keyring storage.

This module provides a thin layer over ``google-auth-oauthlib`` that
persists OAuth tokens in the operating system keyring, optionally
encrypting them at rest with a symmetric Fernet key sourced from the
``OAUTH_ENCRYPTION_KEY`` environment variable. It exposes low-level
helpers for generating keys, encrypting and decrypting token payloads,
and reading and writing tokens keyed by ``(service, username)``
pairs, together with a high-level :func:`oauth_wrapper` decorator that
composes those primitives into a complete load / refresh / save cycle
around a user-supplied OAuth routine. A ready-made :func:`google_oauth`
entry point drives Google's ``InstalledAppFlow`` using this machinery.
"""

import base64
import getpass
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, cast

from mayutils.core.extras import may_require_extras
from mayutils.environment.filesystem import get_root
from mayutils.environment.logging import Logger
from mayutils.objects.decorators import flexwrap
from mayutils.objects.hashing import serialise
from mayutils.objects.types import JsonParsed, JsonString

with may_require_extras():
    import keyring
    from cryptography.fernet import Fernet, InvalidToken
    from dotenv import load_dotenv
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

logger = Logger.spawn()


def generate_fernet_key() -> str:
    """Generate a fresh URL-safe Fernet key as a decoded string.

    Thin wrapper around :meth:`cryptography.fernet.Fernet.generate_key`
    that decodes the ``bytes`` result to a native ``str`` so the value
    can be pasted straight into an ``.env`` file or similar
    configuration source without further encoding.

    Returns
    -------
    str
        A 44-character URL-safe base64 string suitable for use as the
        ``OAUTH_ENCRYPTION_KEY`` environment variable consumed by the
        other helpers in this module.
    """
    key = Fernet.generate_key()

    return key.decode()


def get_encryption_key() -> bytes | None:
    """Return the ambient Fernet encryption key from the environment.

    Reads ``OAUTH_ENCRYPTION_KEY`` from the process environment and
    encodes it to ``bytes`` so it can be passed directly to
    :class:`cryptography.fernet.Fernet`. When the variable is unset,
    ``None`` is returned so callers can fall back to plaintext storage
    behaviour.

    Returns
    -------
    bytes or None
        The UTF-8 encoded encryption key when the variable is defined,
        otherwise ``None`` to indicate no key is configured.
    """
    key = os.getenv("OAUTH_ENCRYPTION_KEY", None)

    return key.encode() if key is not None else None


def encrypt_token(
    token: JsonString,
    /,
    *,
    encryption_key: bytes | None = None,
) -> bytes:
    """Encrypt a JSON-encoded OAuth token with Fernet when a key is available.

    When an explicit ``encryption_key`` is not supplied the key is
    resolved from the environment via :func:`get_encryption_key`. If no
    key can be found the token is returned as raw UTF-8 bytes and a
    warning is logged, allowing the caller to still persist something
    to the keyring at the cost of storing the token in plaintext.

    Parameters
    ----------
    token : JsonString
        JSON-serialised OAuth token text (credentials, refresh token,
        expiry, etc.) that should be protected at rest.
    encryption_key : bytes or None, optional
        Explicit Fernet key to use for encryption. When ``None`` the
        key is resolved from ``OAUTH_ENCRYPTION_KEY`` via
        :func:`get_encryption_key`; passing this argument explicitly
        overrides the environment lookup and is useful for tests.

    Returns
    -------
    bytes
        The Fernet ciphertext when a key is available, otherwise the
        UTF-8 encoded plaintext of ``token``.
    """
    if encryption_key is None:
        encryption_key = get_encryption_key()

    token_bytes = token.encode()
    if encryption_key:
        cipher_suite = Fernet(key=encryption_key)
        token_bytes = cipher_suite.encrypt(data=token_bytes)
    else:
        logger.warning(
            msg="No encryption key `OAUTH_ENCRYPTION_KEY` found in environment variables. Storing token in plaintext.",
        )

    return token_bytes


def decrypt_token(
    encrypted_token: bytes,
    /,
    *,
    encryption_key: bytes | None = None,
) -> JsonString:
    """Decrypt a Fernet-encrypted OAuth token back to its JSON text form.

    When an explicit ``encryption_key`` is not supplied the key is
    resolved from the environment via :func:`get_encryption_key`. If no
    key can be found ``encrypted_token`` is treated as UTF-8 plaintext
    JSON, mirroring the fallback behaviour of :func:`encrypt_token`,
    and a warning is logged.

    Parameters
    ----------
    encrypted_token : bytes
        The ciphertext (or plaintext JSON bytes, in unencrypted mode)
        previously produced by :func:`encrypt_token` and retrieved from
        the keyring.
    encryption_key : bytes or None, optional
        Explicit Fernet key to use for decryption. When ``None`` the
        key is resolved from ``OAUTH_ENCRYPTION_KEY`` via
        :func:`get_encryption_key`.

    Returns
    -------
    JsonString
        The decoded JSON text of the OAuth token, ready to be parsed by
        the caller.

    Raises
    ------
    cryptography.fernet.InvalidToken
        If a key is supplied or resolved but the ciphertext is
        malformed, corrupted, or encrypted under a different key.
    """
    if encryption_key is None:
        encryption_key = get_encryption_key()

    if encryption_key:
        cipher_suite = Fernet(key=encryption_key)
        token_json = cipher_suite.decrypt(token=encrypted_token).decode()
    else:
        logger.warning(
            msg="No encryption key `OAUTH_ENCRYPTION_KEY` found in environment variables. Assuming token stored in plaintext.",
        )
        token_json = encrypted_token.decode()

    return cast("JsonString", token_json)


def save_token(
    token: JsonString,
    /,
    *,
    service: str,
    username: str,
) -> None:
    """Persist an encrypted OAuth token to the OS keyring.

    Encrypts ``token`` via :func:`encrypt_token` and base64-encodes the
    resulting bytes so they can be stored safely as the "password"
    field of a keyring entry indexed by ``(service, username)``. Any
    existing entry under the same key is overwritten.

    Parameters
    ----------
    token : JsonString
        JSON-encoded OAuth token text to store.
    service : str
        Logical identifier of the OAuth provider used to namespace the
        keyring entry (for example ``"google-slides"``).
    username : str
        Account name within the service, typically the local OS user
        or a user-supplied label that distinguishes multiple accounts.
    """
    encrypted_token = encrypt_token(token)
    keyring.set_password(
        service_name=service,
        username=username,
        password=base64.b64encode(encrypted_token).decode(encoding="utf-8"),
    )


def load_token(
    service: str,
    /,
    *,
    username: str,
) -> JsonString:
    """Load a stored OAuth token from the OS keyring.

    Fetches the keyring entry for ``(service, username)``, base64
    decodes it, and delegates to :func:`decrypt_token` to recover the
    original JSON text. If the stored bytes cannot be decrypted or
    parsed as JSON the corrupt entry is deleted from the keyring so the
    next authentication attempt starts from a clean state, and a
    :class:`ValueError` is raised to signal that the caller must
    re-authenticate.

    Parameters
    ----------
    service : str
        Logical identifier of the OAuth provider used when the token
        was saved.
    username : str
        Account name within the service used when the token was saved.

    Returns
    -------
    JsonString
        The decoded JSON text of the OAuth token.

    Raises
    ------
    ValueError
        If no entry exists for ``(service, username)``, or if the
        stored value cannot be decrypted / parsed and was therefore
        cleared.
    """
    encrypted_token = keyring.get_password(
        service_name=service,
        username=username,
    )

    if encrypted_token:
        try:
            encrypted_token_bytes = base64.b64decode(encrypted_token.encode(encoding="utf-8"))
            return decrypt_token(encrypted_token_bytes)

        except (InvalidToken, json.JSONDecodeError) as err:
            logger.warning(
                msg=f"Resetting token as failed to decrypt or parse: {err}.",
            )

            keyring.delete_password(
                service_name=service,
                username=username,
            )

    msg = "No valid token found in keyring"
    raise ValueError(msg)


class StoreToken(Protocol):
    """Callable protocol for serialising credentials into a keyring payload.

    Implementations take a provider-specific credentials object (which
    may be a plain JSON-compatible structure or a richer SDK object)
    and produce the canonical JSON text that will be handed to
    :func:`save_token` for encryption and persistence.
    """

    def __call__(
        self,
        credentials: JsonParsed,
        /,
    ) -> JsonString:
        """Serialise ``credentials`` into JSON text suitable for storage.

        Parameters
        ----------
        credentials : JsonParsed
            The in-memory credentials object returned by the wrapped
            OAuth routine.

        Returns
        -------
        JsonString
            The JSON text representation of ``credentials`` to be
            persisted in the keyring.
        """
        ...


class ParseToken(Protocol):
    """Callable protocol for deserialising stored token JSON.

    Implementations take the JSON text recovered from the keyring by
    :func:`load_token` and return a structure understood by the wrapped
    OAuth routine (typically a plain ``dict`` shaped for a provider's
    ``from_authorized_user_info`` constructor).
    """

    def __call__(
        self,
        token: JsonString,
        /,
    ) -> JsonParsed:
        """Parse ``token`` JSON text into an in-memory representation.

        Parameters
        ----------
        token : JsonString
            JSON text previously produced by a matching
            :class:`StoreToken` implementation.

        Returns
        -------
        JsonParsed
            The deserialised token structure to feed back into the
            OAuth routine on subsequent runs.
        """
        ...


def default_store_token(
    credentials: JsonParsed,
    /,
) -> JsonString:
    """Serialise arbitrary credentials using :func:`json.dumps`.

    Uses :func:`mayutils.objects.hashing.serialise` as the ``default``
    hook so that non-JSON-native objects commonly emitted by SDKs
    (dates, sets, dataclasses, etc.) are coerced to JSON-safe values.

    Parameters
    ----------
    credentials : JsonParsed
        The credentials object to serialise. May be a plain ``dict`` or
        any structure accepted by :func:`json.dumps` when paired with
        the ``serialise`` fallback.

    Returns
    -------
    JsonString
        The JSON text form of ``credentials``.
    """
    return cast(
        "JsonString",
        json.dumps(
            obj=credentials,
            default=serialise,
        ),
    )


def default_parse_token(
    token: JsonString,
    /,
) -> JsonParsed:
    """Parse stored JSON text into a Python object via :func:`json.loads`.

    Parameters
    ----------
    token : JsonString
        JSON text loaded from the keyring.

    Returns
    -------
    JsonParsed
        The decoded Python structure, typically a ``dict`` suitable for
        re-hydrating an OAuth credentials object.
    """
    return json.loads(
        s=token,
    )


@flexwrap
def oauth_wrapper(
    oauth: Callable[..., tuple[Any, bool]],
    *,
    store_token: StoreToken = default_store_token,
    parse_token: ParseToken = default_parse_token,
) -> Callable[..., Any]:
    """Decorate an OAuth routine with keyring load / save bookkeeping.

    The decorated callable is expected to return a
    ``(credentials, updated)`` tuple: ``credentials`` is the usable
    authentication object to return to callers, and ``updated`` is a
    truthy flag indicating that the token material has changed and
    should be re-persisted. The wrapper reads any existing token from
    the keyring, parses it via ``parse_token`` and passes it to the
    underlying routine as the ``token`` keyword argument, then — if the
    routine reports an update — re-serialises the credentials with
    ``store_token`` and writes them back. Because the function is
    decorated with :func:`mayutils.objects.decorators.flexwrap` it can
    be applied both with and without parentheses.

    Parameters
    ----------
    oauth : Callable
        The underlying OAuth routine being decorated. Must accept a
        ``token`` keyword argument (a parsed token structure or
        ``None`` when no token is available) alongside any additional
        provider-specific keyword arguments, and must return a
        ``(credentials, updated)`` tuple.
    store_token : StoreToken, optional
        Callable converting the credentials produced by ``oauth`` into
        the JSON text written to the keyring. Defaults to
        :func:`default_store_token`.
    parse_token : ParseToken, optional
        Callable converting JSON text read from the keyring into the
        structure passed back into ``oauth`` as ``token``. Defaults to
        :func:`default_parse_token`.

    Returns
    -------
    Callable
        A wrapper function taking ``(service, *, username, **kwargs)``
        that orchestrates the load / refresh / save cycle and returns
        the credentials object produced by ``oauth``.
    """

    def wrapper(
        service: str,
        /,
        *,
        username: str = getpass.getuser(),
        **kwargs: Any,  # noqa: ANN401
    ) -> JsonParsed:
        """Execute the wrapped OAuth routine with keyring persistence.

        Loads ``.env`` via :func:`dotenv.load_dotenv` so that the
        encryption key and any provider-specific environment variables
        referenced inside ``oauth`` are available, attempts to hydrate
        a previously-stored token, calls the wrapped routine, and
        writes any refreshed credentials back to the keyring when the
        routine reports an update.

        Parameters
        ----------
        service : str
            Logical identifier of the OAuth provider, used both to key
            the keyring entry and (typically) by the wrapped routine to
            select provider-specific configuration.
        username : str, optional
            Account name within the service. Defaults to the current
            OS user from :func:`getpass.getuser`, which is appropriate
            for single-user machines.
        **kwargs
            Additional keyword arguments forwarded verbatim to the
            wrapped ``oauth`` callable (for example ``scopes`` or a
            ``credentials_file`` path for :func:`google_oauth`).

        Returns
        -------
        JsonParsed
            The credentials object returned by the wrapped OAuth
            routine. The exact type depends on the provider — for
            Google this is a :class:`google.oauth2.credentials.Credentials`.
        """
        load_dotenv()

        try:
            parsed_token = parse_token(
                load_token(
                    service,
                    username=username,
                )
            )

        except ValueError:
            parsed_token = None

        credentials, updated = oauth(
            token=parsed_token,
            **kwargs,
        )

        if updated:
            save_token(
                store_token(credentials),
                service=service,
                username=username,
            )

        return credentials

    return wrapper


def reset_service_oauth(
    service: str,
    /,
    *,
    username: str = getpass.getuser(),
) -> None:
    """Delete a cached OAuth token from the OS keyring.

    Useful when the stored credentials are known to be stale (for
    example after scope changes, a revoked client secret, or a manual
    logout) and the next invocation should be forced back through the
    full authentication flow.

    Parameters
    ----------
    service : str
        Logical identifier of the OAuth provider used when the token
        was saved.
    username : str, optional
        Account name within the service. Defaults to the current OS
        user from :func:`getpass.getuser`.
    """
    keyring.delete_password(
        service_name=service,
        username=username,
    )

    logger.debug(
        msg=f"OAuth token for {service} and user {username} has been reset.",
    )


@oauth_wrapper(store_token=lambda creds: creds.to_json())  # pyright: ignore[reportUnknownLambdaType, reportUntypedFunctionDecorator, reportUnknownMemberType, reportAttributeAccessIssue, reportCallIssue]  # ty:ignore[missing-argument]
def google_oauth(
    token: JsonParsed | None,
    **kwargs: Any,  # noqa: ANN401
) -> tuple[Credentials, bool]:
    """Obtain valid Google OAuth credentials, refreshing or re-authenticating as needed.

    Three outcomes are possible, tried in order: hydrate a valid
    :class:`~google.oauth2.credentials.Credentials` directly from a
    stored ``token``; refresh credentials that have expired but still
    carry a ``refresh_token`` via
    :meth:`Credentials.refresh`; or, as a last resort, run the full
    :class:`google_auth_oauthlib.flow.InstalledAppFlow` against a local
    browser on an ephemeral port. The returned flag is always ``True``
    so that :func:`oauth_wrapper` re-saves the (possibly freshly
    refreshed) token.

    Parameters
    ----------
    token : JsonParsed or None
        Previously-stored token structure produced by
        :meth:`Credentials.to_json` and re-parsed by
        :func:`default_parse_token`. ``None`` indicates no token is
        available, forcing a full interactive flow. Supplied by
        :func:`oauth_wrapper`.
    **kwargs
        Provider-specific options:

        ``scopes`` : list of str
            OAuth scopes to request. Required for a new authorization
            flow; should match the scopes used when the stored token
            was minted to avoid refresh failures.
        ``credentials_file`` : pathlib.Path or str, optional
            Filesystem path to the Google client-secrets JSON
            downloaded from the Cloud Console. Defaults to
            ``<repo_root>/.secrets/credentials.json``.

    Returns
    -------
    tuple of (Credentials, bool)
        The hydrated, refreshed, or freshly-issued credentials object
        together with an ``updated`` flag signalling to
        :func:`oauth_wrapper` that the token should be persisted.

    Raises
    ------
    ValueError
        If the interactive flow completes but the resulting credentials
        are not valid, indicating an authentication failure.
    """
    scopes = kwargs.pop("scopes", [])
    credentials_file = Path(
        kwargs.pop(
            "credentials_file",
            get_root() / ".secrets" / "credentials.json",
        )
    )

    creds: Credentials | None = (
        Credentials.from_authorized_user_info(  # pyright: ignore[reportUnknownMemberType]
            info=token,
            scopes=scopes,
        )
        if token is not None
        else None
    )

    if creds is not None and creds.valid:
        return creds, True

    if creds is not None and creds.expired:
        logger.info(
            msg=f"Token expired at {creds.expiry}",  # pyright: ignore[reportUnknownMemberType]
        )
        if creds.refresh_token:  # pyright: ignore[reportUnknownMemberType]
            creds.refresh(request=Request())  # pyright: ignore[reportUnknownMemberType]

            return creds, True

    flow = cast(
        "InstalledAppFlow",
        InstalledAppFlow.from_client_secrets_file(  # pyright: ignore[reportUnknownMemberType]
            client_secrets_file=credentials_file,
            scopes=scopes,
        ),
    )
    creds = cast("Credentials", flow.run_local_server(port=0))  # pyright: ignore[reportUnknownMemberType]
    logger.info(
        msg=f"New token created at {creds.expiry}",  # pyright: ignore[reportUnknownMemberType, reportOptionalMemberAccess]
    )

    if not creds.valid:  # pyright: ignore[reportUnknownMemberType, reportOptionalMemberAccess]
        msg = "Authentication failed, please check your credentials."
        raise ValueError(msg)

    return creds, True
