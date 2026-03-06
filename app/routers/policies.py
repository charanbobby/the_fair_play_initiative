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

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File, status
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
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    model_extract: Optional[str] = None,
    model_plan: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Analyse a policy document and receive:
      - Extracted keywords mapped to the FPI schema entities
      - A structured SQL ingestion plan (no database writes performed)

    Supply EITHER a file upload (PDF, DOCX, TXT) or raw text via the
    ``text`` form field.  At least one must be provided.

    Optional query parameters override the default LLM model per step:
      - model_extract: model for keyword extraction
      - model_plan: model for SQL ingestion planning
    """
    from pathlib import Path
    from app.config import settings

    if file and file.filename:
        # ── File upload path ──
        allowed = {".pdf", ".docx", ".doc", ".txt"}
        ext = Path(file.filename).suffix.lower()
        if ext not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(allowed))}",
            )
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        filename = file.filename
    elif text and text.strip():
        # ── Pasted text path ──
        content = text.strip().encode("utf-8")
        filename = "pasted_policy.txt"
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either a file upload or paste policy text.",
        )

    try:
        from app.services.policy_analyzer import analyze_policy_document
        result = await analyze_policy_document(
            filename, content,
            model_extract=model_extract,
            model_plan=model_plan,
        )

        # Auto-save analysis logs for token tracking
        default_model = settings.LLM_MODEL or "gpt-4o-mini"
        usage = result.token_usage
        if usage:
            db.add(models.AnalysisLog(
                filename=filename,
                step="extract",
                llm_model=model_extract or default_model,
                prompt_tokens=usage.extract_prompt,
                completion_tokens=usage.extract_completion,
                total_tokens=usage.extract_total,
                duration_ms=usage.extract_duration_ms,
            ))
            db.add(models.AnalysisLog(
                filename=filename,
                step="plan",
                llm_model=model_plan or default_model,
                prompt_tokens=usage.plan_prompt,
                completion_tokens=usage.plan_completion,
                total_tokens=usage.plan_total,
                duration_ms=usage.plan_duration_ms,
            ))
            db.commit()

        return result
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")
