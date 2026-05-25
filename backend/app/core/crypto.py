import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings, get_settings
from app.core.errors import ValidationAppError


class PasswordEncryptor:
    def __init__(self, secret_key: str):
        digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
        fernet_key = base64.urlsafe_b64encode(digest)
        self._fernet = Fernet(fernet_key)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "PasswordEncryptor":
        settings = settings or get_settings()
        return cls(settings.secret_key)

    def encrypt(self, plaintext: str) -> str:
        if plaintext == "":
            raise ValidationAppError("password must not be empty")
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValidationAppError("encrypted password cannot be decrypted") from exc
