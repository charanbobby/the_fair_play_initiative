"""
app/database.py
---------------
SQLAlchemy 2.0 database setup.

- engine: SQLite by default (swappable via DATABASE_URL env var)
- SessionLocal: per-request session factory
- Base: declarative base for all ORM models
- get_db: FastAPI dependency that yields a scoped session
"""

from __future__ import annotations

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine
# Supabase pooler uses dotted usernames (postgres.ref) which SQLAlchemy's
# URL parser mishandles.  We bypass all URL handling for PostgreSQL by passing
# connection params directly to psycopg2 via a creator function.
# ---------------------------------------------------------------------------
_raw_url = settings.DATABASE_URL

if _raw_url.startswith("sqlite"):
    engine = create_engine(
        _raw_url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
        echo=False,
    )
elif _raw_url.startswith("postgresql"):
    from urllib.parse import urlparse
    import psycopg2

    _parsed = urlparse(_raw_url)
    _pg_user = _parsed.username or "postgres"
    _pg_pass = _parsed.password or ""
    _pg_host = _parsed.hostname or "localhost"
    _pg_port = _parsed.port or 6543
    _pg_db = (_parsed.path or "/postgres").lstrip("/") or "postgres"

    logger.info(
        "PostgreSQL connect: user=%s host=%s port=%s db=%s",
        _pg_user, _pg_host, _pg_port, _pg_db,
    )

    def _pg_creator():
        return psycopg2.connect(
            host=_pg_host,
            port=_pg_port,
            user=_pg_user,
            password=_pg_pass,
            dbname=_pg_db,
            sslmode="require",
        )

    engine = create_engine(
        "postgresql+psycopg2://",
        creator=_pg_creator,
        pool_pre_ping=True,
        echo=False,
    )
else:
    engine = create_engine(
        _raw_url,
        pool_pre_ping=True,
        echo=False,
    )

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# FastAPI dependency — yields a DB session, closes it on exit
# ---------------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
