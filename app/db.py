from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import build_db_dsn, settings


def _build_engine():
    dsn = build_db_dsn(settings)
    return create_engine(
        dsn,
        pool_size=settings.pool_size,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"options": f"-c statement_timeout={settings.statement_timeout_ms}"},
    )


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
