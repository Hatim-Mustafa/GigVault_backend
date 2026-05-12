from fastapi import Depends, Header
from sqlalchemy import select

from .db import SessionLocal
from .errors import raise_app_error
from .security import decode_token
from .tables import users


def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_current_user(authorization: str | None = Header(default=None), db=Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise_app_error("UNAUTHORIZED", "Missing or invalid token", status_code=401)
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token, token_type="access")
    except Exception:
        raise_app_error("UNAUTHORIZED", "Invalid or expired token", status_code=401)
    user_id = int(payload.get("sub", 0))
    stmt = select(users).where(users.c.user_id == user_id)
    user = db.execute(stmt).mappings().first()
    if not user:
        raise_app_error("UNAUTHORIZED", "User not found", status_code=401)
    if user.get("is_active") is False:
        raise_app_error("FORBIDDEN", "User is inactive", status_code=403)
    return user


def require_role(*roles: str):
    def _role_dependency(current_user=Depends(get_current_user)):
        if current_user.get("role") not in roles:
            raise_app_error("FORBIDDEN", "User lacks permission", status_code=403)
        return current_user

    return _role_dependency
