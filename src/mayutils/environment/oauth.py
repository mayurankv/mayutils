import base64
import getpass
import json
import os
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

import keyring
from cryptography.fernet import Fernet, InvalidToken
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from mayutils.environment.filesystem import get_root
from mayutils.environment.logging import Logger

logger = Logger.spawn()


def generate_fernet_key() -> str:
    key = Fernet.generate_key()

    return key.decode()


def get_encryption_key() -> bytes | None:
    encryption_key = (
        key.encode()
        if (key := os.getenv("OAUTH_ENCRYPTION_KEY", None)) is not None
        else None
    )

    return encryption_key


def encrypt_token(
    token_str: str,
    encryption_key: bytes | None = None,
) -> bytes:
    if encryption_key is None:
        encryption_key = get_encryption_key()

    token_bytes = token_str.encode()
    if encryption_key:
        cipher_suite = Fernet(key=encryption_key)
        token_bytes = cipher_suite.encrypt(data=token_bytes)
    else:
        logger.warning(
            msg="No encryption key `OAUTH_ENCRYPTION_KEY` found in environment variables. Storing token in plaintext.",
        )

    return token_bytes


def decrypt_token(
    stored_token: bytes,
    encryption_key: bytes | None = None,
) -> dict:
    if encryption_key is None:
        encryption_key = get_encryption_key()

    if encryption_key:
        cipher_suite = Fernet(key=encryption_key)
        token_json = cipher_suite.decrypt(token=stored_token).decode()
    else:
        logger.warning(
            msg="No encryption key `OAUTH_ENCRYPTION_KEY` found in environment variables. Assuming token stored in plaintext.",
        )
        token_json = stored_token.decode()

    return json.loads(token_json)


def save_token(
    service_name: str,
    token_str: str,
    username: str,
) -> None:
    encrypted_token = encrypt_token(token_str=token_str)
    keyring.set_password(
        service_name=service_name,
        username=username,
        password=base64.b64encode(encrypted_token).decode(encoding="utf-8"),
    )


def load_token(
    service_name: str,
    username: str,
) -> dict:
    encrypted_token = keyring.get_password(
        service_name=service_name,
        username=username,
    )

    if encrypted_token:
        try:
            token = decrypt_token(
                stored_token=base64.b64decode(encrypted_token.encode(encoding="utf-8")),
            )

            return token

        except (InvalidToken, json.JSONDecodeError) as err:
            logger.warning(
                msg=f"Resetting token as failed to decrypt or parse: {err}.",
            )

            keyring.delete_password(
                service_name=service_name,
                username=username,
            )

    raise ValueError("No valid token found in keyring")


def oauth_wrapper(
    oauth_internal: Callable,
):
    def wrapper(
        service_name: str,
        username: str = getpass.getuser(),
        **kwargs,
    ) -> dict:
        load_dotenv()

        try:
            token = load_token(
                service_name=service_name,
                username=username,
            )

        except ValueError:
            token = None

        creds, updated = oauth_internal(
            token=token,
            **kwargs,
        )

        if updated:
            save_token(
                service_name=service_name,
                token_str=creds.to_json(),
                username=username,
            )

        return creds

    return wrapper


# def _google_oauth(
#     service_name: str,
#     scopes: list[str],
#     credentials_file: Path | str = get_root() / ".secrets" / "credentials.json",
#     username: str = getpass.getuser(),
# ) -> Credentials:
#     load_dotenv()
#     credentials_file = Path(credentials_file)

#     try:
#         token = load_token(
#             service_name=service_name,
#             username=username,
#         )

#         creds = Credentials.from_authorized_user_info(
#             info=token,
#             scopes=scopes,
#         )

#     except ValueError:
#         creds = None

#     if not creds or not creds.valid:
#         if creds and creds.expired:
#             logger.info(
#                 msg=f"Token for {username} expired at {creds.expiry}",
#             )

#         if creds and creds.expired and creds.refresh_token:
#             creds.refresh(request=Request())
#         else:
#             flow = InstalledAppFlow.from_client_secrets_file(
#                 client_secrets_file=credentials_file,
#                 scopes=scopes,
#             )
#             creds = flow.run_local_server(port=0)
#             logger.info(
#                 msg=f"New token for {username} created at {creds.expiry}",
#             )

#         save_token(
#             service_name=service_name,
#             token_str=creds.to_json(),
#             username=username,
#         )

#     if not creds.valid:
#         raise ValueError("Authentication failed, please check your credentials.")

#     return creds  # type: ignore


@oauth_wrapper
def google_oauth(
    token: dict | None,
    **kwargs,
) -> tuple[Credentials, bool]:
    scopes = kwargs.pop("scopes", [])
    credentials_file = Path(
        kwargs.pop(
            "credentials_file",
            get_root() / ".secrets" / "credentials.json",
        )
    )

    creds = (
        Credentials.from_authorized_user_info(
            info=token,
            scopes=scopes,
        )
        if token is not None
        else None
    )

    updated = False
    if not creds or not creds.valid:
        if creds and creds.expired:
            logger.info(
                msg=f"Token expired at {creds.expiry}",
            )

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(request=Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_file=credentials_file,
                scopes=scopes,
            )
            creds = flow.run_local_server(port=0)
            logger.info(
                msg=f"New token created at {creds.expiry}",
            )

        updated = True

    if not creds.valid:
        raise ValueError("Authentication failed, please check your credentials.")

    return creds, updated  # type: ignore


def reset_service_oauth(
    service_name: str,
    username: str = getpass.getuser(),
) -> None:
    keyring.delete_password(
        service_name=service_name,
        username=username,
    )

    logger.debug(
        msg=f"OAuth token for {service_name} and user {username} has been reset.",
    )
