"""Authenticated encryption for private clinical attachments.

Each file receives a random AES-256 data key. The active master key wraps that
data key; only ciphertext is written to RECORD_DIR. GCM is finalized before
plaintext can be returned to a caller.
"""

import base64
import binascii
import hashlib
import hmac
import io
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

CHUNK_BYTES = 1024 * 1024
MAX_RECORD_BYTES = 512 * 1024 * 1024
KEY_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,32}\Z")


class KeyUnavailable(Exception):
    """Required wrapping key is absent or invalid."""


class IntegrityFailure(Exception):
    """Stored data or authenticated metadata failed verification."""


@dataclass(frozen=True)
class SealedFile:
    size_bytes: int
    sha256: str
    ciphertext_sha256: str
    head: bytes
    key_id: str
    wrapped_key: str
    wrap_nonce: str
    file_nonce: str
    file_tag: str


def _decode_b64(value: str, expected: int, label: str) -> bytes:
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error, TypeError) as exc:
        raise ValueError(f"Invalid {label}") from exc
    if len(raw) != expected:
        raise ValueError(f"Invalid {label} length")
    return raw


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def load_keyring() -> tuple[str, dict[str, bytes]]:
    """Validate configured wrapping keys without logging or returning them to API users."""
    active = os.getenv("LUNGTIC_RECORD_ACTIVE_KEY_ID", "")
    raw = os.getenv("LUNGTIC_RECORD_KEYS_JSON", "")
    if not KEY_ID_RE.fullmatch(active):
        raise KeyUnavailable("Set LUNGTIC_RECORD_ACTIVE_KEY_ID")
    try:
        encoded = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise KeyUnavailable("Set LUNGTIC_RECORD_KEYS_JSON") from exc
    if not isinstance(encoded, dict) or not encoded:
        raise KeyUnavailable("Record keyring must be a nonempty object")
    keys = {}
    for key_id, value in encoded.items():
        if not isinstance(key_id, str) or not KEY_ID_RE.fullmatch(key_id) or not isinstance(value, str):
            raise KeyUnavailable("Invalid record keyring entry")
        try:
            keys[key_id] = _decode_b64(value, 32, "record wrapping key")
        except ValueError as exc:
            raise KeyUnavailable("Invalid record wrapping key") from exc
    if active not in keys:
        raise KeyUnavailable("Active record key is missing")
    return active, keys


def _aad(kind: str, patient_id: int, storage_key: str) -> bytes:
    return f"lungtic/record/{kind}/v1:{patient_id}:{storage_key}".encode("ascii")


def seal_upload(
    source: BinaryIO, destination: Path, *, patient_id: int, storage_key: str
) -> SealedFile:
    """Encrypt in chunks, hash plaintext and ciphertext, and write only ciphertext."""
    key_id, keys = load_keyring()
    data_key = os.urandom(32)
    wrap_nonce = os.urandom(12)
    wrapped_key = AESGCM(keys[key_id]).encrypt(
        wrap_nonce, data_key, _aad("key", patient_id, storage_key)
    )
    file_nonce = os.urandom(12)
    encryptor = Cipher(algorithms.AES(data_key), modes.GCM(file_nonce)).encryptor()
    encryptor.authenticate_additional_data(_aad("file", patient_id, storage_key))
    plain_hash = hashlib.sha256()
    cipher_hash = hashlib.sha256()
    size = 0
    head = b""
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as target:
        while chunk := source.read(CHUNK_BYTES):
            size += len(chunk)
            if size > MAX_RECORD_BYTES:
                raise ValueError("Record exceeds 512 MB")
            if len(head) < 132:
                head = (head + chunk)[:132]
            plain_hash.update(chunk)
            ciphertext = encryptor.update(chunk)
            cipher_hash.update(ciphertext)
            target.write(ciphertext)
        tail = encryptor.finalize()
        if tail:
            cipher_hash.update(tail)
            target.write(tail)
        target.flush()
        os.fsync(target.fileno())
    return SealedFile(
        size_bytes=size,
        sha256=plain_hash.hexdigest(),
        ciphertext_sha256=cipher_hash.hexdigest(),
        head=head,
        key_id=key_id,
        wrapped_key=_b64(wrapped_key),
        wrap_nonce=_b64(wrap_nonce),
        file_nonce=_b64(file_nonce),
        file_tag=_b64(encryptor.tag),
    )


def _unwrap_data_key(record, keys: dict[str, bytes]) -> bytes:
    master = keys.get(record.key_id)
    if master is None:
        raise KeyUnavailable("Record key ID is unavailable")
    try:
        wrap_nonce = _decode_b64(record.wrap_nonce, 12, "wrap nonce")
        wrapped = _decode_b64(record.wrapped_key, 48, "wrapped data key")
        return AESGCM(master).decrypt(
            wrap_nonce, wrapped, _aad("key", record.patient_id, record.storage_key)
        )
    except (InvalidTag, ValueError) as exc:
        raise IntegrityFailure("Record data key authentication failed") from exc


def verify_record(record, path: Path, *, collect_plaintext: bool = False) -> bytes | None:
    """Authenticate the entire file and compare both SHA-256 values before returning bytes."""
    if record.encryption_version != 1:
        raise IntegrityFailure("Unencrypted legacy record")
    _, keys = load_keyring()
    try:
        if not path.is_file() or path.stat().st_size != record.size_bytes:
            raise IntegrityFailure("Record ciphertext size mismatch")
        data_key = _unwrap_data_key(record, keys)
        file_nonce = _decode_b64(record.file_nonce, 12, "file nonce")
        file_tag = _decode_b64(record.file_tag, 16, "file tag")
        decryptor = Cipher(algorithms.AES(data_key), modes.GCM(file_nonce, file_tag)).decryptor()
        decryptor.authenticate_additional_data(_aad("file", record.patient_id, record.storage_key))
        plain_hash = hashlib.sha256()
        cipher_hash = hashlib.sha256()
        result = io.BytesIO() if collect_plaintext else None
        with path.open("rb") as source:
            while chunk := source.read(CHUNK_BYTES):
                cipher_hash.update(chunk)
                plaintext = decryptor.update(chunk)
                plain_hash.update(plaintext)
                if result is not None:
                    result.write(plaintext)
        tail = decryptor.finalize()
        plain_hash.update(tail)
        if result is not None:
            result.write(tail)
        if not hmac.compare_digest(plain_hash.hexdigest(), record.sha256 or ""):
            raise IntegrityFailure("Record plaintext SHA-256 mismatch")
        if not hmac.compare_digest(cipher_hash.hexdigest(), record.ciphertext_sha256 or ""):
            raise IntegrityFailure("Record ciphertext SHA-256 mismatch")
        return result.getvalue() if result is not None else None
    except (InvalidTag, ValueError, TypeError, OSError) as exc:
        raise IntegrityFailure("Record integrity verification failed") from exc


def rewrap_record(record, new_key_id: str, keys: dict[str, bytes]) -> None:
    """Change the wrapping key without decrypting or rewriting the file ciphertext."""
    if record.encryption_version != 1 or new_key_id not in keys:
        raise KeyUnavailable("Cannot rewrap record")
    data_key = _unwrap_data_key(record, keys)
    nonce = os.urandom(12)
    record.wrapped_key = _b64(AESGCM(keys[new_key_id]).encrypt(
        nonce, data_key, _aad("key", record.patient_id, record.storage_key)
    ))
    record.wrap_nonce = _b64(nonce)
    record.key_id = new_key_id
