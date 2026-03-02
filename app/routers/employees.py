"""
app/routers/employees.py
-------------------------
CRUD endpoints for Employee + manual override and point history.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import (
    EmployeeCreate,
    EmployeeDetailResponse,
    EmployeeResponse,
    EmployeeUpdate,
    OverrideRequest,
    PointHistoryResponse,
)

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("/", response_model=List[EmployeeResponse])
def list_employees(
    organization_id: Optional[str] = None,
    region_id: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Employee)
    if organization_id:
        q = q.filter(models.Employee.organization_id == organization_id)
    if region_id:
        q = q.filter(models.Employee.region_id == region_id)
    if search:
        like = f"%{search}%"
        q = q.filter(
            models.Employee.first_name.ilike(like)
            | models.Employee.last_name.ilike(like)
            | models.Employee.email.ilike(like)
            | models.Employee.department.ilike(like)
        )
    return q.all()


@router.post("/", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(body: EmployeeCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Employee).filter(models.Employee.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Employee with email '{body.email}' already exists")

    emp = models.Employee(
        **body.model_dump(),
        points=0.0,
        trend="stable",
        next_reset=date.today() + timedelta(days=180),
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@router.get("/{employee_id}", response_model=EmployeeDetailResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    emp = db.get(models.Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int, body: EmployeeUpdate, db: Session = Depends(get_db)
):
    emp = db.get(models.Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(emp, field, value)
    db.commit()
    db.refresh(emp)
    return emp


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    emp = db.get(models.Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.delete(emp)
    db.commit()


@router.get("/{employee_id}/history", response_model=List[PointHistoryResponse])
def get_point_history(employee_id: int, db: Session = Depends(get_db)):
    emp = db.get(models.Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp.point_history


@router.post("/{employee_id}/override", response_model=EmployeeDetailResponse)
def apply_override(
    employee_id: int, body: OverrideRequest, db: Session = Depends(get_db)
):
    emp = db.get(models.Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    override_points = 0.0

    if body.type == "reset":
        # Mark all active history as excused
        for h in emp.point_history:
            if h.status == "Active":
                h.status = "Excused"
        emp.points = 0.0

    elif body.type == "reduce":
        amount = body.amount or 0.0
        emp.points = max(0.0, round(emp.points - amount, 1))
        override_points = -amount

    elif body.type == "excuse":
        # Excuse the latest Active violation
        latest = next((h for h in emp.point_history if h.status == "Active"), None)
        if latest:
            latest.status = "Excused"
            emp.points = max(0.0, round(emp.points - latest.points, 1))
            override_points = -latest.points
    else:
        raise HTTPException(status_code=400, detail="type must be 'excuse', 'reduce', or 'reset'")

    # Audit trail entry
    audit = models.PointHistory(
        employee_id=emp.id,
        date=date.today(),
        type=f"Manual Override: {body.type}",
        points=override_points,
        status="Excused",
        reason=body.reason or "",
    )
    db.add(audit)
    db.commit()
    db.refresh(emp)
    return emp
