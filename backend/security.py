from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from config import get_settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
settings = get_settings()


def _normalize_key(raw_key: str) -> bytes:
    if not raw_key:
        raise ValueError("APP_ENCRYPTION_KEY is required")
    try:
        # already fernet format
        Fernet(raw_key.encode("utf-8"))
        return raw_key.encode("utf-8")
    except Exception:
        # derive deterministic fernet-compatible key from any secret
        padded = raw_key.encode("utf-8")[:32].ljust(32, b"0")
        return base64.urlsafe_b64encode(padded)


fernet = Fernet(_normalize_key(settings.app_encryption_key))


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    return payload.get("sub")


def encrypt_text(plaintext: str) -> str:
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_text(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
