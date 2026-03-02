"""
app/routers/alerts.py
----------------------
Read-only alert listing endpoint.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import AlertCreate, AlertResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/", response_model=List[AlertResponse])
def list_alerts(
    organization_id: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    q = db.query(models.Alert).order_by(models.Alert.created_at.desc())
    if organization_id:
        q = q.filter(
            (models.Alert.organization_id == organization_id)
            | (models.Alert.organization_id.is_(None))
        )
    return q.limit(limit).all()


@router.post("/", response_model=AlertResponse, status_code=201)
def create_alert(body: AlertCreate, db: Session = Depends(get_db)):
    alert = models.Alert(**body.model_dump())
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
