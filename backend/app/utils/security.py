import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    token_type: str = "access",
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES))
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": now,
        "jti": uuid.uuid4().hex,
        "type": token_type,
    }
    return jwt.encode(payload, settings.JWT_SECRET.get_secret_value(), algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    return create_access_token(subject, expires_delta=timedelta(days=7), token_type="refresh")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET.get_secret_value(), algorithms=[settings.JWT_ALGORITHM])
