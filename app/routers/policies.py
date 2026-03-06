"""
app/routers/policies.py
------------------------
CRUD endpoints for Policy (filterable by org/region).

Additional endpoint:
    POST /policies/analyze — upload a policy document and get keyword
                             extraction + SQL ingestion plan (no DB writes).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import PolicyCreate, PolicyResponse, PolicyUpdate, PolicyAnalysisResponse

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("", response_model=List[PolicyResponse])
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


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
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


@router.post("/analyze", response_model=PolicyAnalysisResponse, tags=["policies"])
async def analyze_policy(
    file: UploadFile = File(...),
    model_extract: Optional[str] = None,
    model_plan: Optional[str] = None,
):
    """
    Upload a policy document (PDF, DOCX, or TXT) and receive:
      - Extracted keywords mapped to the FPI schema entities
      - A structured SQL ingestion plan (no database writes performed)

    Optional query parameters override the default LLM model per step:
      - model_extract: model for keyword extraction
      - model_plan: model for SQL ingestion planning
    """
    allowed = {".pdf", ".docx", ".doc", ".txt"}
    from pathlib import Path
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(allowed))}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        from app.services.policy_analyzer import analyze_policy_document
        return await analyze_policy_document(
            file.filename, content,
            model_extract=model_extract,
            model_plan=model_plan,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")
