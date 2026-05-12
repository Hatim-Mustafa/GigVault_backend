from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError


def error_payload(code: str, message: str, details=None) -> dict:
    payload = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return payload


def raise_app_error(code: str, message: str, status_code: int = 400, details=None):
    raise HTTPException(
        status_code=status_code,
        detail=error_payload(code, message, details),
    )


def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload("INTERNAL_ERROR", str(exc.detail)),
    )


def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content=error_payload("VALIDATION_ERROR", "Invalid request data", exc.errors()),
    )


def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=500,
        content=error_payload("DB_ERROR", "Database error", str(exc)),
    )
