"""
app/database.py
---------------
SQLAlchemy 2.0 database setup.

- engine / SessionLocal / get_db: main database (SQLite or PG)
- analytics_engine / AnalyticsSessionLocal / get_analytics_db:
      always PostgreSQL so feedback + analysis_logs persist across sessions
- Base: declarative base for all ORM models
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
            connect_timeout=10,
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
# Analytics engine — always PostgreSQL so feedback/logs survive across sessions
# Falls back to the main engine when ANALYTICS_DATABASE_URL is not set and
# DATABASE_URL is already PostgreSQL.
# ---------------------------------------------------------------------------
_analytics_url = settings.ANALYTICS_DATABASE_URL

if _analytics_url and _analytics_url.startswith("postgresql"):
    from urllib.parse import urlparse as _a_urlparse
    import psycopg2 as _a_psycopg2

    _a_parsed = _a_urlparse(_analytics_url)
    _a_user = _a_parsed.username or "postgres"
    _a_pass = _a_parsed.password or ""
    _a_host = _a_parsed.hostname or "localhost"
    _a_port = _a_parsed.port or 6543
    _a_db = (_a_parsed.path or "/postgres").lstrip("/") or "postgres"

    logger.info(
        "Analytics PostgreSQL: user=%s host=%s port=%s db=%s",
        _a_user, _a_host, _a_port, _a_db,
    )

    def _analytics_pg_creator():
        return _a_psycopg2.connect(
            host=_a_host,
            port=_a_port,
            user=_a_user,
            password=_a_pass,
            dbname=_a_db,
            sslmode="require",
            connect_timeout=10,
        )

    analytics_engine = create_engine(
        "postgresql+psycopg2://",
        creator=_analytics_pg_creator,
        pool_pre_ping=True,
        echo=False,
    )
elif _raw_url.startswith("postgresql"):
    # No separate ANALYTICS_DATABASE_URL but main DB is already PG — reuse it
    analytics_engine = engine
else:
    # Both are SQLite — analytics will use SQLite too (dev-only fallback)
    logger.warning("No PostgreSQL URL for analytics — feedback will use SQLite (not persistent)")
    analytics_engine = engine

AnalyticsSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=analytics_engine,
)


# ---------------------------------------------------------------------------
# FastAPI dependency — yields a DB session, closes it on exit
# ---------------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_analytics_db():
    """Yields a session bound to the analytics (PostgreSQL) engine."""
    db = AnalyticsSessionLocal()
    try:
        yield db
    finally:
        db.close()
