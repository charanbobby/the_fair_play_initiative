"""
app/routers/dashboard.py
-------------------------
Dashboard stats aggregation endpoint.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import DashboardStats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(
    organization_id: Optional[str] = None,
    region_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    emp_q = db.query(models.Employee)
    log_q = db.query(models.AttendanceLog).filter(
        models.AttendanceLog.violation.isnot(None)
    )
    org_q = db.query(models.Organization)

    if organization_id:
        emp_q = emp_q.filter(models.Employee.organization_id == organization_id)
        log_q = log_q.filter(models.AttendanceLog.organization_id == organization_id)
        org_q = org_q.filter(models.Organization.id == organization_id)

    if region_id:
        emp_q = emp_q.filter(models.Employee.region_id == region_id)
        log_q = log_q.filter(models.AttendanceLog.region_id == region_id)

    total_employees = emp_q.count()
    active_violations = log_q.count()
    red_flags = emp_q.filter(models.Employee.points >= 8).count()
    total_organizations = org_q.count()

    return DashboardStats(
        total_employees=total_employees,
        active_violations=active_violations,
        red_flags=red_flags,
        total_organizations=total_organizations,
    )
