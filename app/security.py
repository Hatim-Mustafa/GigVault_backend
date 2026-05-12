from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ROLE_TO_DB = {
    "ADMIN": "Admin",
    "MUSICIAN": "Musician",
    "VENUE_OWNER": "Venue_Owner",
}

ROLE_TO_API = {db_role: api_role for api_role, db_role in ROLE_TO_DB.items()}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _create_token(user_id: int, role: str, token_type: str, expires_seconds: int):
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=expires_seconds)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def create_access_token(user_id: int, role: str) -> str:
    token, _ = _create_token(
        user_id,
        role,
        token_type="access",
        expires_seconds=settings.access_token_expires_seconds,
    )
    return token


def create_refresh_token(user_id: int, role: str):
    return _create_token(
        user_id,
        role,
        token_type="refresh",
        expires_seconds=settings.refresh_token_expires_seconds,
    )


def decode_token(token: str, token_type: str | None = None) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if token_type and payload.get("type") != token_type:
        raise ValueError("Invalid token type")
    return payload


def to_db_role(role: str) -> str:
    normalized = role.strip().upper()
    return ROLE_TO_DB.get(normalized, role)


def to_api_role(role: str) -> str:
    if role in ROLE_TO_API:
        return ROLE_TO_API[role]
    return role.strip().upper()
