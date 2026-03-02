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
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# ---------------------------------------------------------------------------
# Engine
# SQLite needs check_same_thread=False for multi-threaded use.
# For Postgres, the connect_args dict is ignored.
# ---------------------------------------------------------------------------
connect_args: dict = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
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
