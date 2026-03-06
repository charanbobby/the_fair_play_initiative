"""
app/routers/playground.py
-------------------------
Playground-mode endpoints: status, reset, seed, and sample policies.

Playground mode is controlled by the PLAYGROUND_MODE env var (true/false/auto).
When 'auto', it is active when DATABASE_URL points to SQLite.
Reset and seed endpoints return 403 when playground mode is off.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.database import get_db
from app.sample_policies import SAMPLE_POLICIES
from app.schemas import PlaygroundStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playground", tags=["playground"])

# Tables to truncate in reverse-FK order (children first)
_TRUNCATE_ORDER = [
    models.AnalysisFeedback,
    models.AnalysisLog,
    models.Alert,
    models.AttendanceLog,
    models.PointHistory,
    models.Employee,
    models.Rule,
    models.Policy,
    models.Organization,  # will cascade organization_region
    models.Region,
]


def _clear_all_data(db: Session) -> None:
    """Delete all rows from every table. Works on both SQLite and PostgreSQL."""
    for model_cls in _TRUNCATE_ORDER:
        db.query(model_cls).delete()
    db.commit()


# ---------------------------------------------------------------------------
# GET /playground/status — always accessible
# ---------------------------------------------------------------------------

@router.get("/status", response_model=PlaygroundStatus)
def playground_status(db: Session = Depends(get_db)):
    """Return current mode, DB engine type, record counts, and sample policy list."""
    db_engine = "sqlite" if settings.DATABASE_URL.startswith("sqlite") else "postgresql"

    counts = {}
    for model_cls, label in [
        (models.Organization, "organizations"),
        (models.Region, "regions"),
        (models.Policy, "policies"),
        (models.Rule, "rules"),
        (models.Employee, "employees"),
        (models.Alert, "alerts"),
    ]:
        try:
            counts[label] = db.query(model_cls).count()
        except Exception:
            counts[label] = 0

    # Strip full text from the summary — frontend fetches it via /sample-policies
    sample_list = [
        {"id": p["id"], "name": p["name"], "description": p["description"]}
        for p in SAMPLE_POLICIES
    ]

    return PlaygroundStatus(
        is_playground=settings.IS_PLAYGROUND,
        db_engine=db_engine,
        record_counts=counts,
        sample_policies=sample_list,
    )


# ---------------------------------------------------------------------------
# GET /playground/sample-policies — always accessible
# ---------------------------------------------------------------------------

@router.get("/sample-policies")
def get_sample_policies():
    """Return full text of all sample policy documents."""
    return SAMPLE_POLICIES


# ---------------------------------------------------------------------------
# POST /playground/reset — playground only
# ---------------------------------------------------------------------------

@router.post("/reset")
def reset_playground(db: Session = Depends(get_db)):
    """Clear all data from every table. Playground only."""
    if not settings.IS_PLAYGROUND:
        raise HTTPException(403, "Reset is only available in Playground mode")

    _clear_all_data(db)
    logger.info("playground: database reset complete")
    return {
        "status": "reset",
        "message": "All data cleared. Tables are empty.",
    }


# ---------------------------------------------------------------------------
# POST /playground/seed — playground only
# ---------------------------------------------------------------------------

@router.post("/seed")
def seed_playground(db: Session = Depends(get_db)):
    """Clear all data, then load demo seed data. Playground only."""
    if not settings.IS_PLAYGROUND:
        raise HTTPException(403, "Seed is only available in Playground mode")

    # Clear existing data first (seed() skips if data exists)
    _clear_all_data(db)

    from app.seed import seed
    seed(db)

    logger.info("playground: database seeded with demo data")
    return {
        "status": "seeded",
        "message": "Demo data loaded: 4 regions, 3 organizations, 5 policies, ~30 employees.",
    }
