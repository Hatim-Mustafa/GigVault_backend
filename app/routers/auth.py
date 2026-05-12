from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from ..config import settings
from ..dependencies import get_db
from ..errors import raise_app_error
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from ..tables import refresh_tokens, users

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str
    role: Literal["MUSICIAN", "VENUE_OWNER"]
    city: str | None = None
    bio: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db=Depends(get_db)):
    existing = db.execute(select(users.c.user_id).where(users.c.email == payload.email)).first()
    if existing:
        raise_app_error("CONFLICT", "Email already registered", status_code=409)

    password_hash = hash_password(payload.password)
    stmt = (
        insert(users)
        .values(
            email=payload.email,
            password_hash=password_hash,
            name=payload.name,
            role=payload.role,
            city=payload.city,
            bio=payload.bio,
        )
        .returning(
            users.c.user_id,
            users.c.email,
            users.c.name,
            users.c.role,
            users.c.created_at,
        )
    )
    try:
        row = db.execute(stmt).mappings().first()
    except IntegrityError:
        raise_app_error("CONFLICT", "Email already registered", status_code=409)

    return {
        "user_id": row["user_id"],
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.post("/login")
def login(payload: LoginRequest, db=Depends(get_db)):
    user = db.execute(select(users).where(users.c.email == payload.email)).mappings().first()
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise_app_error("INVALID_CREDENTIALS", "Email or password incorrect", status_code=401)

    access_token = create_access_token(user["user_id"], user["role"])
    refresh_token, refresh_expires_at = create_refresh_token(user["user_id"], user["role"])

    db.execute(
        insert(refresh_tokens).values(
            user_id=user["user_id"],
            token=refresh_token,
            expires_at=refresh_expires_at,
        )
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": settings.access_token_expires_seconds,
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
        },
    }


@router.post("/refresh")
def refresh_token(authorization: str | None = Header(default=None), db=Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise_app_error("UNAUTHORIZED", "Missing refresh token", status_code=401)
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token, token_type="refresh")
    except Exception:
        raise_app_error("UNAUTHORIZED", "Invalid refresh token", status_code=401)

    token_row = (
        db.execute(select(refresh_tokens).where(refresh_tokens.c.token == token))
        .mappings()
        .first()
    )
    if not token_row:
        raise_app_error("UNAUTHORIZED", "Refresh token not found", status_code=401)
    if token_row["revoked_at"] is not None:
        raise_app_error("UNAUTHORIZED", "Refresh token revoked", status_code=401)
    if token_row["expires_at"] < datetime.now(timezone.utc):
        raise_app_error("UNAUTHORIZED", "Refresh token expired", status_code=401)

    access_token = create_access_token(int(payload.get("sub", 0)), payload.get("role", ""))
    return {"access_token": access_token, "expires_in": settings.access_token_expires_seconds}


@router.post("/logout")
def logout(authorization: str | None = Header(default=None), db=Depends(get_db)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        db.execute(
            update(refresh_tokens)
            .where(refresh_tokens.c.token == token)
            .values(revoked_at=datetime.now(timezone.utc))
        )
    return {"message": "Logged out successfully"}
