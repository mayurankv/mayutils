"""
Manage Google OAuth credentials with encrypted keyring storage.

Provide a thin layer over ``google-auth-oauthlib`` that persists OAuth
tokens in the operating system keyring, optionally encrypting them at
rest with a symmetric Fernet key sourced from the
``OAUTH_ENCRYPTION_KEY`` environment variable. Expose low-level helpers
for generating keys, encrypting and decrypting token payloads, and
reading and writing tokens keyed by ``(service, username)`` pairs,
together with a high-level :func:`oauth_wrapper` decorator that composes
those primitives into a complete load / refresh / save cycle around a
user-supplied OAuth routine. A ready-made :func:`google_oauth` entry
point drives Google's ``InstalledAppFlow`` using this machinery.

See Also
--------
keyring : Native OS credential backend used for token persistence.
cryptography.fernet : Symmetric authenticated encryption primitive.
google_auth_oauthlib.flow.InstalledAppFlow : Underlying OAuth installed-app flow.
mayutils.environment.secrets : Shared secret-retrieval helpers.

Examples
--------
>>> from mayutils.environment.oauth import generate_fernet_key
>>> key = generate_fernet_key()
>>> isinstance(key, str)
True
>>> len(key)
44
"""

from __future__ import annotations

import base64
import getpass
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

from mayutils.core.extras import may_require_extras
from mayutils.environment.filesystem import get_root
from mayutils.environment.logging import Logger
from mayutils.objects.decorators import flexwrap
from mayutils.objects.hashing import serialise

if TYPE_CHECKING:
    from collections.abc import Callable

    from google.oauth2.credentials import Credentials

    from mayutils.objects.types import JsonParsed, JsonString

logger = Logger.spawn()


def generate_fernet_key() -> str:
    """
    Generate a fresh URL-safe Fernet key as a decoded string.

    Wrap :meth:`cryptography.fernet.Fernet.generate_key` and decode the
    resulting bytes to a native ``str`` so the value can be pasted
    straight into an ``.env`` file or similar configuration source
    without further encoding. The produced secret is cryptographically
    random 32-byte material URL-safe base64 encoded, and should be
    rotated whenever you suspect compromise so that previously-encrypted
    tokens become unreadable.

    Returns
    -------
        A 44-character URL-safe base64 string suitable for use as the
        ``OAUTH_ENCRYPTION_KEY`` environment variable consumed by the
        other helpers in this module.

    See Also
    --------
    cryptography.fernet.Fernet.generate_key : Underlying key generator.
    get_encryption_key : Read the resulting key from the environment.
    encrypt_token : Consumer that uses a Fernet key for encryption.

    Examples
    --------
    >>> key = generate_fernet_key()
    >>> isinstance(key, str)
    True
    >>> len(key)
    44
    """
    with may_require_extras():
        from cryptography.fernet import Fernet

    key = Fernet.generate_key()

    return key.decode()


def get_encryption_key() -> bytes | None:
    """
    Return the ambient Fernet encryption key from the environment.

    Read ``OAUTH_ENCRYPTION_KEY`` from the process environment and
    encode it to ``bytes`` so it can be passed directly to
    :class:`cryptography.fernet.Fernet`. When the variable is unset,
    return ``None`` so callers can fall back to plaintext storage
    behaviour. Sourcing the key from the environment keeps the secret
    out of source control while still letting ``dotenv`` or a shell
    profile inject it at startup.

    Returns
    -------
        The UTF-8 encoded encryption key when the variable is defined,
        otherwise ``None`` to indicate no key is configured.

    See Also
    --------
    generate_fernet_key : Produce a value suitable for this variable.
    cryptography.fernet.Fernet : Symmetric cipher that consumes the key.
    dotenv.load_dotenv : Loader used to populate the environment.

    Examples
    --------
    >>> import os
    >>> os.environ["OAUTH_ENCRYPTION_KEY"] = generate_fernet_key()
    >>> try:
    ...     key = get_encryption_key()
    ...     isinstance(key, bytes)
    ... finally:
    ...     del os.environ["OAUTH_ENCRYPTION_KEY"]
    True
    """
    key = os.getenv("OAUTH_ENCRYPTION_KEY", None)

    return key.encode() if key is not None else None


def encrypt_token(
    token: JsonString,
    /,
    *,
    encryption_key: bytes | None = None,
) -> bytes:
    """
    Encrypt a JSON-encoded OAuth token with Fernet when a key is available.

    Resolve the key from the environment via :func:`get_encryption_key`
    when an explicit ``encryption_key`` is not supplied. If no key can be
    found, return the token as raw UTF-8 bytes and log a warning,
    allowing the caller to still persist something to the keyring at the
    cost of storing the token in plaintext. Fernet tokens include a
    128-bit MAC and a timestamp, giving authenticated encryption and the
    ability to detect tampering at decryption time.

    Parameters
    ----------
    token
        JSON-serialised OAuth token text (credentials, refresh token,
        expiry, etc.) that should be protected at rest.
    encryption_key
        Explicit Fernet key to use for encryption. When ``None`` the
        key is resolved from ``OAUTH_ENCRYPTION_KEY`` via
        :func:`get_encryption_key`; passing this argument explicitly
        overrides the environment lookup and is useful for tests.

    Returns
    -------
        The Fernet ciphertext when a key is available, otherwise the
        UTF-8 encoded plaintext of ``token``.

    See Also
    --------
    decrypt_token : Inverse operation.
    cryptography.fernet.Fernet.encrypt : Underlying cipher primitive.
    save_token : High-level persistence helper built on this function.

    Examples
    --------
    >>> key = generate_fernet_key().encode()
    >>> ciphertext = encrypt_token('{"access_token": "xyz"}', encryption_key=key)
    >>> isinstance(ciphertext, bytes)
    True
    """
    with may_require_extras():
        from cryptography.fernet import Fernet

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
    """
    Decrypt a Fernet-encrypted OAuth token back to its JSON text form.

    Resolve the key from the environment via :func:`get_encryption_key`
    when an explicit ``encryption_key`` is not supplied. If no key can
    be found, treat ``encrypted_token`` as UTF-8 plaintext JSON,
    mirroring the fallback behaviour of :func:`encrypt_token`, and log a
    warning. A mismatch between the key used to encrypt and the key used
    here raises :class:`~cryptography.fernet.InvalidToken`, which the
    caller can catch to trigger a full re-authentication.

    Parameters
    ----------
    encrypted_token
        The ciphertext (or plaintext JSON bytes, in unencrypted mode)
        previously produced by :func:`encrypt_token` and retrieved from
        the keyring.
    encryption_key
        Explicit Fernet key to use for decryption. When ``None`` the
        key is resolved from ``OAUTH_ENCRYPTION_KEY`` via
        :func:`get_encryption_key`.

    Returns
    -------
        The decoded JSON text of the OAuth token, ready to be parsed by
        the caller.

    See Also
    --------
    encrypt_token : Inverse operation.
    cryptography.fernet.Fernet.decrypt : Underlying cipher primitive.
    load_token : High-level retrieval helper built on this function.

    Examples
    --------
    >>> key = generate_fernet_key().encode()
    >>> blob = encrypt_token('{"access_token": "xyz"}', encryption_key=key)
    >>> decrypt_token(blob, encryption_key=key)
    '{"access_token": "xyz"}'
    """
    with may_require_extras():
        from cryptography.fernet import Fernet

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
    """
    Persist an encrypted OAuth token to the OS keyring.

    Encrypt ``token`` via :func:`encrypt_token` and base64-encode the
    resulting bytes so they can be stored safely as the "password"
    field of a keyring entry indexed by ``(service, username)``. Any
    existing entry under the same key is overwritten, so this is also
    the correct entry point for rotating a token after a refresh.
    Storage is delegated to :mod:`keyring`, which defers to the native
    credential manager (macOS Keychain, Windows Credential Vault, or
    Secret Service on Linux).

    Parameters
    ----------
    token
        JSON-encoded OAuth token text to store.
    service
        Logical identifier of the OAuth provider used to namespace the
        keyring entry (for example ``"google-slides"``).
    username
        Account name within the service, typically the local OS user
        or a user-supplied label that distinguishes multiple accounts.

    See Also
    --------
    load_token : Complementary retrieval helper.
    encrypt_token : Encryption step used before storage.
    keyring.set_password : Underlying credential-store primitive.
    reset_service_oauth : Remove a saved token.

    Examples
    --------
    >>> from mayutils.environment.oauth import save_token
    >>> save_token(  # doctest: +SKIP
    ...     '{"access_token": "xyz"}',
    ...     service="google-slides",
    ...     username="mayuran",
    ... )  # doctest: +SKIP
    """
    with may_require_extras():
        import keyring

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
    """
    Load a stored OAuth token from the OS keyring.

    Fetch the keyring entry for ``(service, username)``, base64 decode
    it, and delegate to :func:`decrypt_token` to recover the original
    JSON text. If the stored bytes cannot be decrypted or parsed as
    JSON, delete the corrupt entry from the keyring so the next
    authentication attempt starts from a clean state, and raise a
    :class:`ValueError` to signal that the caller must re-authenticate.
    This self-healing behaviour avoids the common failure mode of being
    locked out by a stale token after a key rotation.

    Parameters
    ----------
    service
        Logical identifier of the OAuth provider used when the token
        was saved.
    username
        Account name within the service used when the token was saved.

    Returns
    -------
        The decoded JSON text of the OAuth token.

    Raises
    ------
    ValueError
        If no entry exists for ``(service, username)``, or if the
        stored value cannot be decrypted / parsed and was therefore
        cleared.

    See Also
    --------
    save_token : Complementary persistence helper.
    decrypt_token : Decryption step used during retrieval.
    keyring.get_password : Underlying credential-store primitive.
    reset_service_oauth : Manual equivalent of the self-healing reset.

    Examples
    --------
    >>> from mayutils.environment.oauth import load_token
    >>> token = load_token("google-slides", username="mayuran")  # doctest: +SKIP
    >>> isinstance(token, str)  # doctest: +SKIP
    True
    """
    with may_require_extras():
        import keyring
        from cryptography.fernet import InvalidToken

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
    """
    Define the callable protocol for serialising credentials into a payload.

    Describe the callable shape used by :func:`oauth_wrapper` to convert
    a provider-specific credentials object (which may be a plain
    JSON-compatible structure or a richer SDK object) into the canonical
    JSON text that will be handed to :func:`save_token` for encryption
    and persistence. Custom implementations let callers integrate with
    providers whose credentials require bespoke serialisation (for
    example Google's :meth:`Credentials.to_json`).

    See Also
    --------
    ParseToken : Complementary protocol for deserialisation.
    default_store_token : Reference implementation using ``json.dumps``.
    oauth_wrapper : Consumer that calls instances of this protocol.

    Examples
    --------
    >>> def my_store(creds):
    ...     return cast("JsonString", json.dumps(creds))
    >>> my_store({"access_token": "xyz"})
    '{"access_token": "xyz"}'
    """

    def __call__(
        self,
        credentials: object,
        /,
    ) -> JsonString:
        """
        Serialise ``credentials`` into JSON text suitable for storage.

        Convert the in-memory credentials object produced by the wrapped
        OAuth routine into a JSON text payload that can safely round
        trip through :func:`encrypt_token` and the OS keyring. The
        returned value is expected to be consumable by the matching
        :class:`ParseToken` implementation.

        Parameters
        ----------
        credentials
            The in-memory credentials object returned by the wrapped
            OAuth routine.

        Returns
        -------
            The JSON text representation of ``credentials`` to be
            persisted in the keyring.

        See Also
        --------
        ParseToken : Inverse callable protocol.
        default_store_token : Reference implementation.

        Examples
        --------
        >>> store: StoreToken = default_store_token
        >>> store({"access_token": "xyz"})
        '{"access_token": "xyz"}'
        """
        ...


class ParseToken(Protocol):
    """
    Define the callable protocol for deserialising stored token JSON.

    Describe the callable shape used by :func:`oauth_wrapper` to convert
    the JSON text recovered from the keyring by :func:`load_token` into
    a structure understood by the wrapped OAuth routine (typically a
    plain ``dict`` shaped for a provider's ``from_authorized_user_info``
    constructor). Supplying a custom implementation lets callers inject
    provider-specific validation or coercion during rehydration.

    See Also
    --------
    StoreToken : Complementary protocol for serialisation.
    default_parse_token : Reference implementation using ``json.loads``.
    oauth_wrapper : Consumer that calls instances of this protocol.

    Examples
    --------
    >>> def my_parse(token):
    ...     return json.loads(token)
    >>> my_parse('{"access_token": "xyz"}')
    {'access_token': 'xyz'}
    """

    def __call__(
        self,
        token: JsonString,
        /,
    ) -> JsonParsed:
        """
        Parse ``token`` JSON text into an in-memory representation.

        Convert the JSON text returned from :func:`load_token` back into
        the Python structure that the wrapped OAuth routine expects (for
        example the ``info`` ``dict`` accepted by
        :meth:`google.oauth2.credentials.Credentials.from_authorized_user_info`).
        The returned object is passed unchanged to the wrapped routine
        as the ``token`` keyword argument.

        Parameters
        ----------
        token
            JSON text previously produced by a matching
            :class:`StoreToken` implementation.

        Returns
        -------
            The deserialised token structure to feed back into the
            OAuth routine on subsequent runs.

        See Also
        --------
        StoreToken : Inverse callable protocol.
        default_parse_token : Reference implementation.

        Examples
        --------
        >>> parse: ParseToken = default_parse_token
        >>> parse('{"access_token": "xyz"}')
        {'access_token': 'xyz'}
        """
        ...


def default_store_token(
    credentials: object,
    /,
) -> JsonString:
    """
    Serialise arbitrary credentials using :func:`json.dumps`.

    Call :func:`json.dumps` with :func:`mayutils.objects.hashing.serialise`
    as the ``default`` hook so that non-JSON-native objects commonly
    emitted by SDKs (dates, sets, dataclasses, etc.) are coerced to
    JSON-safe values. This is the fallback :class:`StoreToken`
    implementation for providers whose credentials do not expose a
    dedicated serialiser such as :meth:`Credentials.to_json`.

    Parameters
    ----------
    credentials
        The credentials object to serialise. May be a plain ``dict`` or
        any structure accepted by :func:`json.dumps` when paired with
        the ``serialise`` fallback.

    Returns
    -------
        The JSON text form of ``credentials``.

    See Also
    --------
    StoreToken : Protocol this function implements.
    default_parse_token : Inverse used on the load path.
    mayutils.objects.hashing.serialise : JSON fallback encoder.

    Examples
    --------
    >>> default_store_token({"access_token": "xyz"})
    '{"access_token": "xyz"}'
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
    """
    Parse stored JSON text into a Python object via :func:`json.loads`.

    Invoke :func:`json.loads` directly without custom hooks because
    Google's OAuth token payload is already composed of JSON-native
    values. Serves as the default :class:`ParseToken` implementation
    paired with :func:`default_store_token` and is suitable for any
    provider whose credentials fit within the JSON data model.

    Parameters
    ----------
    token
        JSON text loaded from the keyring.

    Returns
    -------
        The decoded Python structure, typically a ``dict`` suitable for
        re-hydrating an OAuth credentials object.

    See Also
    --------
    ParseToken : Protocol this function implements.
    default_store_token : Inverse used on the save path.
    json.loads : Underlying JSON decoder.

    Examples
    --------
    >>> default_parse_token('{"access_token": "xyz"}')
    {'access_token': 'xyz'}
    """
    return json.loads(
        s=token,
    )


@flexwrap
def oauth_wrapper(
    oauth: Callable[..., tuple[object, bool]],
    *,
    store_token: StoreToken = default_store_token,
    parse_token: ParseToken = default_parse_token,
) -> Callable[..., object]:
    """
    Decorate an OAuth routine with keyring load / save bookkeeping.

    Expect the decorated callable to return a ``(credentials, updated)``
    tuple: ``credentials`` is the usable authentication object to return
    to callers, and ``updated`` is a truthy flag indicating that the
    token material has changed and should be re-persisted. Read any
    existing token from the keyring, parse it via ``parse_token`` and
    pass it to the underlying routine as the ``token`` keyword argument,
    then — if the routine reports an update — re-serialise the
    credentials with ``store_token`` and write them back. Because the
    function is itself decorated with
    :func:`mayutils.objects.decorators.flexwrap` it can be applied both
    with and without parentheses.

    Parameters
    ----------
    oauth
        The underlying OAuth routine being decorated. Must accept a
        ``token`` keyword argument (a parsed token structure or
        ``None`` when no token is available) alongside any additional
        provider-specific keyword arguments, and must return a
        ``(credentials, updated)`` tuple.
    store_token
        Callable converting the credentials produced by ``oauth`` into
        the JSON text written to the keyring. Defaults to
        :func:`default_store_token`.
    parse_token
        Callable converting JSON text read from the keyring into the
        structure passed back into ``oauth`` as ``token``. Defaults to
        :func:`default_parse_token`.

    Returns
    -------
        A wrapper function taking ``(service, *, username, **kwargs)``
        that orchestrates the load / refresh / save cycle and returns
        the credentials object produced by ``oauth``.

    See Also
    --------
    load_token : Hydration step executed before ``oauth`` runs.
    save_token : Persistence step executed when ``updated`` is truthy.
    google_oauth : Prebuilt routine wrapped with this decorator.
    mayutils.objects.decorators.flexwrap : Optional-parentheses helper.

    Examples
    --------
    >>> from mayutils.environment.oauth import oauth_wrapper
    >>> @oauth_wrapper
    ... def my_oauth(*, token, **kwargs):
    ...     return {"access_token": "xyz"}, True
    >>> creds = my_oauth("my-service", username="mayuran")  # doctest: +SKIP
    """

    def wrapper(
        service: str,
        /,
        *,
        username: str = getpass.getuser(),
        **kwargs: Any,  # noqa: ANN401
    ) -> object:
        """
        Execute the wrapped OAuth routine with keyring persistence.

        Load ``.env`` via :func:`dotenv.load_dotenv` so that the
        encryption key and any provider-specific environment variables
        referenced inside ``oauth`` are available, attempt to hydrate a
        previously-stored token, call the wrapped routine, and write
        any refreshed credentials back to the keyring when the routine
        reports an update. Missing or corrupt keyring entries are
        tolerated gracefully by treating them as a first-run scenario
        that triggers the full authentication flow inside ``oauth``.

        Parameters
        ----------
        service
            Logical identifier of the OAuth provider, used both to key
            the keyring entry and (typically) by the wrapped routine to
            select provider-specific configuration.
        username
            Account name within the service. Defaults to the current
            OS user from :func:`getpass.getuser`, which is appropriate
            for single-user machines.
        **kwargs
            Additional keyword arguments forwarded verbatim to the
            wrapped ``oauth`` callable (for example ``scopes`` or a
            ``credentials_file`` path for :func:`google_oauth`).

        Returns
        -------
            The credentials object returned by the wrapped OAuth
            routine. The exact type depends on the provider — for
            Google this is a :class:`google.oauth2.credentials.Credentials`.

        See Also
        --------
        load_token : Keyring retrieval used inside this wrapper.
        save_token : Keyring persistence used inside this wrapper.
        dotenv.load_dotenv : Environment loader invoked on entry.
        getpass.getuser : Source of the default ``username``.

        Examples
        --------
        >>> from mayutils.environment.oauth import google_oauth
        >>> creds = google_oauth(  # doctest: +SKIP
        ...     "google-slides",
        ...     username="mayuran",
        ...     scopes=["https://www.googleapis.com/auth/presentations"],
        ... )  # doctest: +SKIP
        >>> creds.valid  # doctest: +SKIP
        True
        """
        with may_require_extras():
            from dotenv import load_dotenv

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
    """
    Delete a cached OAuth token from the OS keyring.

    Remove the keyring entry for ``(service, username)`` so that the
    next invocation is forced back through the full authentication
    flow. Useful when the stored credentials are known to be stale (for
    example after scope changes, a revoked client secret, a manual
    logout, or rotation of the Fernet encryption key) and
    :func:`load_token`'s automatic self-heal has not yet been triggered.

    Parameters
    ----------
    service
        Logical identifier of the OAuth provider used when the token
        was saved.
    username
        Account name within the service. Defaults to the current OS
        user from :func:`getpass.getuser`.

    See Also
    --------
    load_token : Automatic reset path triggered on decryption failure.
    save_token : Complementary persistence helper.
    keyring.delete_password : Underlying credential-store primitive.

    Examples
    --------
    >>> from mayutils.environment.oauth import reset_service_oauth
    >>> reset_service_oauth("google-slides", username="mayuran")  # doctest: +SKIP
    """
    with may_require_extras():
        import keyring

    keyring.delete_password(
        service_name=service,
        username=username,
    )

    logger.debug(
        msg=f"OAuth token for {service} and user {username} has been reset.",
    )


@oauth_wrapper(store_token=lambda creds: creds.to_json())  # pyright: ignore[reportUnknownMemberType, reportUnknownLambdaType, reportAttributeAccessIssue]
def google_oauth(
    token: JsonParsed | None,
    **kwargs: Any,  # noqa: ANN401
) -> tuple[Credentials, bool]:
    """
    Obtain valid Google OAuth credentials, refreshing or re-authenticating as needed.

    Pursue three outcomes in order: hydrate a valid
    :class:`~google.oauth2.credentials.Credentials` directly from a
    stored ``token``; refresh credentials that have expired but still
    carry a ``refresh_token`` via
    :meth:`Credentials.refresh`; or, as a last resort, run the full
    :class:`google_auth_oauthlib.flow.InstalledAppFlow` against a local
    browser on an ephemeral port. The returned flag is always ``True``
    so that :func:`oauth_wrapper` re-saves the (possibly freshly
    refreshed) token, keeping the keyring copy in lockstep with the
    in-memory credentials.

    Parameters
    ----------
    token
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
        The hydrated, refreshed, or freshly-issued credentials object
        together with an ``updated`` flag signalling to
        :func:`oauth_wrapper` that the token should be persisted.

    Raises
    ------
    ValueError
        If the interactive flow completes but the resulting credentials
        are not valid, indicating an authentication failure.

    See Also
    --------
    oauth_wrapper : Decorator that supplies ``token`` and persists results.
    google_auth_oauthlib.flow.InstalledAppFlow : Interactive flow driver.
    google.oauth2.credentials.Credentials : Credential type returned.
    google.auth.transport.requests.Request : Transport used for refresh.

    Examples
    --------
    >>> from mayutils.environment.oauth import google_oauth
    >>> creds = google_oauth(  # doctest: +SKIP
    ...     "google-slides",
    ...     username="mayuran",
    ...     scopes=["https://www.googleapis.com/auth/presentations"],
    ... )  # doctest: +SKIP
    >>> creds.valid  # doctest: +SKIP
    True
    """
    with may_require_extras():
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

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
        msg=f"New token created at {creds.expiry}",  # pyright: ignore[reportUnknownMemberType]
    )

    if not creds.valid:
        msg = "Authentication failed, please check your credentials."
        raise ValueError(msg)

    return creds, True
