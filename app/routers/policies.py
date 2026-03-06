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
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db, get_analytics_db
from app import models
from app.schemas import (
    ExecuteSQLRequest,
    PolicyCreate,
    PolicyResponse,
    PolicyUpdate,
    PolicyAnalysisResponse,
    QueryResults,
)

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
    model_sql: Optional[str] = None,
    execute: bool = False,
    db: Session = Depends(get_db),
    analytics_db: Session = Depends(get_analytics_db),
):
    """
    Analyse a policy document and receive:
      - Extracted keywords mapped to the FPI schema entities
      - A structured SQL ingestion plan
      - Optionally: generated SQL and execution results

    Supply EITHER a file upload (PDF, DOCX, TXT) or raw text via the
    ``text`` form field.  At least one must be provided.

    Optional query parameters:
      - model_extract: model for keyword extraction
      - model_plan: model for SQL ingestion planning
      - model_sql: model for SQL generation (enables step 3)
      - execute: if true AND model_sql is set, execute SQL (playground only)
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
        from app.services.policy_analyzer import (
            analyze_policy_document, execute_sql_against_db, fetch_existing_records,
        )

        # Pre-query existing records for entity reconciliation
        existing_records = fetch_existing_records(db)

        result = await analyze_policy_document(
            filename, content,
            model_extract=model_extract,
            model_plan=model_plan,
            model_sql=model_sql,
            existing_records=existing_records,
        )

        # ── Execute SQL if requested (playground only) ────────────────
        if execute and result.sql_result and result.sql_result.sql_query:
            if not settings.IS_PLAYGROUND:
                raise HTTPException(
                    status_code=400,
                    detail="SQL execution is only available in Playground mode.",
                )
            is_sqlite = settings.DATABASE_URL.startswith("sqlite")
            query_results = execute_sql_against_db(db, result.sql_result, is_sqlite)
            result.query_results = query_results

        # Auto-save analysis logs to analytics DB (always PG, non-fatal)
        try:
            default_model = settings.LLM_MODEL or "gpt-4o-mini"
            usage = result.token_usage
            if usage:
                analytics_db.add(models.AnalysisLog(
                    filename=filename,
                    step="extract",
                    llm_model=model_extract or default_model,
                    prompt_tokens=usage.extract_prompt,
                    completion_tokens=usage.extract_completion,
                    total_tokens=usage.extract_total,
                    duration_ms=usage.extract_duration_ms,
                ))
                if usage.reconcile_total > 0:
                    analytics_db.add(models.AnalysisLog(
                        filename=filename,
                        step="reconcile",
                        llm_model=default_model,
                        prompt_tokens=usage.reconcile_prompt,
                        completion_tokens=usage.reconcile_completion,
                        total_tokens=usage.reconcile_total,
                        duration_ms=usage.reconcile_duration_ms,
                    ))
                analytics_db.add(models.AnalysisLog(
                    filename=filename,
                    step="plan",
                    llm_model=model_plan or default_model,
                    prompt_tokens=usage.plan_prompt,
                    completion_tokens=usage.plan_completion,
                    total_tokens=usage.plan_total,
                    duration_ms=usage.plan_duration_ms,
                ))
                if usage.sql_total > 0:
                    analytics_db.add(models.AnalysisLog(
                        filename=filename,
                        step="sql",
                        llm_model=model_sql or default_model,
                        prompt_tokens=usage.sql_prompt,
                        completion_tokens=usage.sql_completion,
                        total_tokens=usage.sql_total,
                        duration_ms=usage.sql_duration_ms,
                    ))
                analytics_db.commit()
        except Exception:
            import logging
            logging.getLogger(__name__).warning("Failed to save analysis logs", exc_info=True)
            analytics_db.rollback()

        return result
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


# ---------------------------------------------------------------------------
# Streaming analysis (SSE)
# ---------------------------------------------------------------------------

@router.post("/analyze/stream", tags=["policies"])
async def analyze_policy_stream(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    model_extract: Optional[str] = None,
    model_plan: Optional[str] = None,
    model_sql: Optional[str] = None,
    db: Session = Depends(get_db),
    analytics_db: Session = Depends(get_analytics_db),
):
    """
    Stream policy analysis results as Server-Sent Events.

    Each pipeline step emits an SSE event as it completes:
      - event: step_start  (step about to begin)
      - event: extract     (keyword extraction results)
      - event: plan        (SQL ingestion plan results)
      - event: sql         (SQL generation results — only if model_sql set)
      - event: done        (pipeline complete)
      - event: error       (if a step fails)
    """
    from pathlib import Path
    from app.config import settings
    from app.services.policy_analyzer import stream_policy_analysis, fetch_existing_records

    if file and file.filename:
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
        content = text.strip().encode("utf-8")
        filename = "pasted_policy.txt"
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either a file upload or paste policy text.",
        )

    # Pre-query existing records for entity reconciliation
    existing_records = fetch_existing_records(db)

    async def event_generator():
        async for event in stream_policy_analysis(
            filename, content,
            model_extract=model_extract,
            model_plan=model_plan,
            model_sql=model_sql,
            existing_records=existing_records,
            db=db,
            analytics_db=analytics_db,
            default_model=settings.LLM_MODEL,
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Decoupled SQL execution
# ---------------------------------------------------------------------------

@router.post("/execute-sql", response_model=QueryResults, tags=["policies"])
async def execute_sql_endpoint(
    body: ExecuteSQLRequest,
    db: Session = Depends(get_db),
):
    """
    Execute LLM-generated SQL against the database (playground only).

    This is a separate step from analysis — the user reviews the SQL
    first, then explicitly triggers execution.
    """
    from app.config import settings
    from app.services.policy_analyzer import execute_sql_against_db
    from app.schemas import SQLGeneration

    if not settings.IS_PLAYGROUND:
        raise HTTPException(
            status_code=400,
            detail="SQL execution is only available in Playground mode.",
        )

    if not body.sql_query.strip():
        raise HTTPException(status_code=400, detail="SQL query is empty.")

    # Wrap in SQLGeneration so execute_sql_against_db can process it
    sql_gen = SQLGeneration(
        sql_query=body.sql_query,
        tables_affected=body.tables_affected,
    )
    is_sqlite = settings.DATABASE_URL.startswith("sqlite")
    return execute_sql_against_db(db, sql_gen, is_sqlite)
