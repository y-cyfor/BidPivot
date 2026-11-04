import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import settings


def _derive_key() -> bytes:
    encryption_key = settings.ENCRYPTION_KEY
    secret = (
        encryption_key.get_secret_value()
        if encryption_key is not None
        else settings.JWT_SECRET.get_secret_value()
    )
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())


def encrypt_api_key(plain_key: str) -> str:
    if not plain_key:
        return ""
    f = Fernet(_derive_key())
    return f.encrypt(plain_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    if not encrypted_key:
        return ""
    f = Fernet(_derive_key())
    return f.decrypt(encrypted_key.encode()).decode()
