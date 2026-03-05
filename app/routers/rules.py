"""
app/routers/rules.py
---------------------
CRUD endpoints for Rule (with toggle active endpoint).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import RuleCreate, RuleResponse, RuleUpdate

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=List[RuleResponse])
def list_rules(
    policy_id: Optional[str] = None,
    active_only: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Rule)
    if policy_id is not None:
        q = q.filter(models.Rule.policy_id == policy_id)
    if active_only is not None:
        q = q.filter(models.Rule.active == active_only)
    return q.all()


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(body: RuleCreate, db: Session = Depends(get_db)):
    rule = models.Rule(**body.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/{rule_id}", response_model=RuleResponse)
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(models.Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.put("/{rule_id}", response_model=RuleResponse)
def update_rule(rule_id: int, body: RuleUpdate, db: Session = Depends(get_db)):
    rule = db.get(models.Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/{rule_id}/toggle", response_model=RuleResponse)
def toggle_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(models.Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.active = not rule.active
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(models.Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
