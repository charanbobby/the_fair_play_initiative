"""
app/routers/policies.py
------------------------
CRUD endpoints for Policy (filterable by org/region).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import PolicyCreate, PolicyResponse, PolicyUpdate

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("/", response_model=List[PolicyResponse])
def list_policies(
    organization_id: Optional[str] = None,
    region_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Policy)
    if organization_id:
        q = q.filter(models.Policy.organization_id == organization_id)
    if region_id:
        q = q.filter(models.Policy.region_id == region_id)
    return q.all()


@router.post("/", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
def create_policy(body: PolicyCreate, db: Session = Depends(get_db)):
    if db.get(models.Policy, body.id):
        raise HTTPException(status_code=400, detail=f"Policy '{body.id}' already exists")
    policy = models.Policy(**body.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.get("/{policy_id}", response_model=PolicyResponse)
def get_policy(policy_id: str, db: Session = Depends(get_db)):
    policy = db.get(models.Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.put("/{policy_id}", response_model=PolicyResponse)
def update_policy(policy_id: str, body: PolicyUpdate, db: Session = Depends(get_db)):
    policy = db.get(models.Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(policy, field, value)
    db.commit()
    db.refresh(policy)
    return policy


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy(policy_id: str, db: Session = Depends(get_db)):
    policy = db.get(models.Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    db.delete(policy)
    db.commit()
