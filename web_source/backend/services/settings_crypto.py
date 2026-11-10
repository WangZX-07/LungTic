"""Authenticated encryption for administrator-managed application secrets."""

import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from services.record_crypto import IntegrityFailure, KeyUnavailable, load_keyring

SMTP_AAD = b"lungtic/settings/smtp/v1"


def _settings_key(master_key: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=SMTP_AAD,
    ).derive(master_key)


def encrypt_smtp_password(password: str) -> tuple[str, str, str]:
    active_key_id, keys = load_keyring()
    nonce = os.urandom(12)
    ciphertext = AESGCM(_settings_key(keys[active_key_id])).encrypt(
        nonce, password.encode("utf-8"), SMTP_AAD
    )
    return (
        active_key_id,
        base64.b64encode(nonce).decode("ascii"),
        base64.b64encode(ciphertext).decode("ascii"),
    )


def decrypt_smtp_password(*, key_id: str, nonce: str, ciphertext: str) -> str:
    _, keys = load_keyring()
    master_key = keys.get(key_id)
    if master_key is None:
        raise KeyUnavailable("SMTP settings key ID is unavailable")
    try:
        plaintext = AESGCM(_settings_key(master_key)).decrypt(
            base64.b64decode(nonce, validate=True),
            base64.b64decode(ciphertext, validate=True),
            SMTP_AAD,
        )
        return plaintext.decode("utf-8")
    except Exception as exc:
        raise IntegrityFailure("SMTP password authentication failed") from exc
