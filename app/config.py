from dataclasses import dataclass
import os
from urllib.parse import quote_plus


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, os.getenv(name.lower(), default))


@dataclass(frozen=True)
class Settings:
    db_host: str = _env("DB_HOST")
    db_port: str = _env("DB_PORT", "5432")
    db_name: str = _env("DB_NAME")
    db_user: str = _env("DB_USER")
    db_password: str = _env("DB_PASSWORD")
    pool_size: int = int(_env("DB_POOL_SIZE", "5"))
    statement_timeout_ms: int = int(_env("DB_STATEMENT_TIMEOUT_MS", "10000"))
    jwt_secret: str = _env("JWT_SECRET", "change-me")
    jwt_algorithm: str = _env("JWT_ALGORITHM", "HS256")
    access_token_expires_seconds: int = int(_env("ACCESS_TOKEN_EXPIRES_SECONDS", "86400"))
    refresh_token_expires_seconds: int = int(_env("REFRESH_TOKEN_EXPIRES_SECONDS", "604800"))
    allowed_origins: str = _env("ALLOWED_ORIGINS", "*")


def build_db_dsn(settings: Settings) -> str:
    password = quote_plus(settings.db_password)
    return (
        f"postgresql+psycopg2://{settings.db_user}:{password}@"
        f"{settings.db_host}:{settings.db_port}/{settings.db_name}?sslmode=require"
    )


settings = Settings()
