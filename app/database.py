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

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# ---------------------------------------------------------------------------
# Engine
# SQLite needs check_same_thread=False for multi-threaded use.
# Supabase pooler uses dotted usernames (postgres.ref) which SQLAlchemy's
# string URL parser mishandles, so we build the URL object explicitly.
# ---------------------------------------------------------------------------
_raw_url = settings.DATABASE_URL
connect_args: dict = {}

if _raw_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    _engine_url = _raw_url
elif _raw_url.startswith("postgresql"):
    # Use Python's urlparse (handles dots in username correctly)
    from urllib.parse import urlparse
    _parsed = urlparse(_raw_url)
    _engine_url = URL.create(
        "postgresql+psycopg2",
        username=_parsed.username,
        password=_parsed.password,
        host=_parsed.hostname,
        port=_parsed.port,
        database=(_parsed.path or "/postgres").lstrip("/"),
        query={"sslmode": "require"},
    )
else:
    _engine_url = _raw_url

engine = create_engine(
    _engine_url,
    connect_args=connect_args,
    echo=False,  # set True to log SQL queries during development
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
