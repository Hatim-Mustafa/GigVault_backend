import time
from typing import Dict, Tuple

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from .config import settings
from .errors import (
    error_payload,
    http_exception_handler,
    sqlalchemy_exception_handler,
    validation_exception_handler,
)
from .routers import (
    admin,
    applications,
    auth,
    availability,
    bands,
    bookings,
    disputes,
    gigs,
    payments,
    recruitment_ads,
    reviews,
    setlists,
    users,
)
from .security import decode_token

ROLE_LIMITS = {
    "UNAUTH": 60,
    "MUSICIAN": 1000,
    "VENUE_OWNER": 2000,
    "ADMIN": 1000000,
}

_rate_state: Dict[str, Tuple[int, int]] = {}

app = FastAPI(title="GigVault API", version="1.0")
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)

origins = ["*"]
if settings.allowed_origins.strip() != "*":
    origins = [origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    ip = request.client.host if request.client else "unknown"
    role = "UNAUTH"
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token)
            role = payload.get("role", "UNAUTH")
        except Exception:
            role = "UNAUTH"

    limit = ROLE_LIMITS.get(role, ROLE_LIMITS["UNAUTH"])
    window = int(time.time() // 3600)
    key = f"{role}:{ip}:{window}"
    count, window_id = _rate_state.get(key, (0, window))
    if window_id != window:
        count = 0
    count += 1
    _rate_state[key] = (count, window)
    remaining = max(limit - count, 0)

    if count > limit:
        return JSONResponse(
            status_code=429,
            content=error_payload("RATE_LIMITED", "Rate limit exceeded"),
            headers={"X-RateLimit-Remaining": "0"},
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(auth, prefix="/api/v1")
app.include_router(users, prefix="/api/v1")
app.include_router(bands, prefix="/api/v1")
app.include_router(gigs, prefix="/api/v1")
app.include_router(applications, prefix="/api/v1")
app.include_router(bookings, prefix="/api/v1")
app.include_router(availability, prefix="/api/v1")
app.include_router(setlists, prefix="/api/v1")
app.include_router(payments, prefix="/api/v1")
app.include_router(recruitment_ads, prefix="/api/v1")
app.include_router(reviews, prefix="/api/v1")
app.include_router(disputes, prefix="/api/v1")
app.include_router(admin, prefix="/api/v1")
