"""Encrypt small secrets (SSH passwords, private keys) before they touch the database.

AES-256-GCM, keyed from SECRET_KEY. A stolen higashi.db alone does not reveal
them; the key lives in settings.env, which sits outside the web root.
"""
import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import get_settings

_PREFIX = "v1:"
_CONTEXT = b"higashi/pull-profile-secret/v1"


def _key() -> bytes:
    return hashlib.sha256(_CONTEXT + get_settings().secret_key.encode()).digest()


def encrypt(plaintext: str) -> str:
    nonce = os.urandom(12)
    sealed = AESGCM(_key()).encrypt(nonce, plaintext.encode(), _CONTEXT)
    return _PREFIX + base64.b64encode(nonce + sealed).decode()


def decrypt(token: str) -> str:
    if not token.startswith(_PREFIX):
        raise ValueError("Unrecognised secret format")
    raw = base64.b64decode(token[len(_PREFIX):])
    return AESGCM(_key()).decrypt(raw[:12], raw[12:], _CONTEXT).decode()
