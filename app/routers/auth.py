from typing import Literal
import re
import uuid

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import insert, select
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
from ..tables import users

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str
    role: Literal["MUSICIAN", "VENUE_OWNER"]
    city: str | None = None
    bio: str | None = None


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    if not parts:
        return "User", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _build_unique_username(email: str, db) -> str:
    local = email.split("@", 1)[0].strip().lower()
    base = re.sub(r"[^a-z0-9._]", "", local) or "user"
    base = base[:28]
    candidate = base
    for _ in range(5):
        exists = db.execute(select(users.c.user_id).where(users.c.username == candidate)).first()
        if not exists:
            return candidate
        candidate = f"{base}{uuid.uuid4().hex[:4]}"
    return f"user{uuid.uuid4().hex[:8]}"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db=Depends(get_db)):
    existing = db.execute(select(users.c.user_id).where(users.c.email == payload.email)).first()
    if existing:
        raise_app_error("CONFLICT", "Email already registered", status_code=409)

    password_hash = hash_password(payload.password)
    first_name, last_name = _split_name(payload.name)
    username = _build_unique_username(payload.email, db)
    stmt = (
        insert(users)
        .values(
            username=username,
            email=payload.email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            role=payload.role,
            city=payload.city,
            bio=payload.bio,
        )
        .returning(
            users.c.user_id,
            users.c.email,
            users.c.username,
            users.c.first_name,
            users.c.last_name,
            users.c.role,
            users.c.account_created_at,
        )
    )
    try:
        row = db.execute(stmt).mappings().first()
    except IntegrityError:
        raise_app_error("CONFLICT", "Email already registered", status_code=409)

    return {
        "user_id": row["user_id"],
        "email": row["email"],
        "username": row["username"],
        "name": f"{row['first_name']} {row['last_name']}".strip(),
        "role": row["role"],
        "created_at": (
            row["account_created_at"].isoformat() if row["account_created_at"] else None
        ),
    }


@router.post("/login")
def login(payload: LoginRequest, db=Depends(get_db)):
    user = db.execute(select(users).where(users.c.email == payload.email)).mappings().first()
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise_app_error("INVALID_CREDENTIALS", "Email or password incorrect", status_code=401)

    access_token = create_access_token(user["user_id"], user["role"])
    refresh_token, refresh_expires_at = create_refresh_token(user["user_id"], user["role"])

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": settings.access_token_expires_seconds,
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
            "name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
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

    user_id = int(payload.get("sub", 0))
    user = db.execute(select(users).where(users.c.user_id == user_id)).mappings().first()
    if not user:
        raise_app_error("UNAUTHORIZED", "User not found", status_code=401)

    access_token = create_access_token(user_id, payload.get("role", ""))
    return {"access_token": access_token, "expires_in": settings.access_token_expires_seconds}


@router.post("/logout")
def logout(authorization: str | None = Header(default=None), db=Depends(get_db)):
    # Stateless logout: client drops tokens. Kept for API contract compatibility.
    return {"message": "Logged out successfully"}
