"""Field-level encryption for sensitive identifiers stored on reports.

Reports never store the reporter's user ID in plain text (RD US-13, US-18). Instead
each report stores two values:

* ``encrypt(user_id)`` - Fernet ciphertext (AES-128-CBC + HMAC). Only someone holding
  ``DATA_ENCRYPTION_KEY`` can recover who filed the report.
* ``blind_index(user_id)`` - keyed HMAC-SHA256. Deterministic, so the API can find
  "my reports" with an indexed lookup, but useless without ``DATA_HMAC_KEY``.

Fernet ciphertext is randomised, so it cannot be used for lookups on its own.
"""

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


class FieldCipher:
    def __init__(self, encryption_key: str, hmac_key: str):
        self._fernet = Fernet(encryption_key)
        self._hmac_key = hmac_key.encode()

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Ciphertext could not be decrypted with the current key.") from exc

    def blind_index(self, value: str) -> str:
        return hmac.new(self._hmac_key, value.encode(), hashlib.sha256).hexdigest()


def derive_dev_key(label: str) -> str:
    """Deterministic, obviously-insecure key for local development only."""
    digest = hashlib.sha256(f"reportsdstate-dev-{label}".encode()).digest()
    return base64.urlsafe_b64encode(digest).decode()


def get_cipher() -> FieldCipher:
    return current_app.extensions["field_cipher"]
