"""
app/routers/feedback.py
------------------------
Endpoints for saving analysis feedback and retrieving model rating stats.

    POST /feedback       — save a Good/Partial/Bad rating
    GET  /feedback/stats — aggregated rating percentages + avg token usage per model
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy import case, func as sa_func
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import FeedbackCreate, FeedbackResponse, ModelRatingStats

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(body: FeedbackCreate, db: Session = Depends(get_db)):
    fb = models.AnalysisFeedback(**body.model_dump())
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


@router.get("/stats", response_model=List[ModelRatingStats])
def get_stats(
    step: Optional[str] = None,
    llm_model: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return aggregated rating percentages + avg token usage per (model, step)."""
    results: list[ModelRatingStats] = []

    # Build feedback aggregation query
    fb_q = db.query(
        models.AnalysisFeedback.llm_model,
        models.AnalysisFeedback.step,
        sa_func.count().label("rating_count"),
        sa_func.sum(case((models.AnalysisFeedback.rating == "good", 1), else_=0)).label("good"),
        sa_func.sum(case((models.AnalysisFeedback.rating == "partial", 1), else_=0)).label("partial"),
        sa_func.sum(case((models.AnalysisFeedback.rating == "bad", 1), else_=0)).label("bad"),
    ).group_by(models.AnalysisFeedback.llm_model, models.AnalysisFeedback.step)

    if step:
        fb_q = fb_q.filter(models.AnalysisFeedback.step == step)
    if llm_model:
        fb_q = fb_q.filter(models.AnalysisFeedback.llm_model == llm_model)

    fb_rows = {(r.llm_model, r.step): r for r in fb_q.all()}

    # Build token usage aggregation query
    log_q = db.query(
        models.AnalysisLog.llm_model,
        models.AnalysisLog.step,
        sa_func.count().label("total_runs"),
        sa_func.avg(models.AnalysisLog.total_tokens).label("avg_tokens"),
    ).group_by(models.AnalysisLog.llm_model, models.AnalysisLog.step)

    if step:
        log_q = log_q.filter(models.AnalysisLog.step == step)
    if llm_model:
        log_q = log_q.filter(models.AnalysisLog.llm_model == llm_model)

    log_rows = {(r.llm_model, r.step): r for r in log_q.all()}

    # Merge keys from both tables
    all_keys = set(fb_rows.keys()) | set(log_rows.keys())

    for key in sorted(all_keys):
        model_id, step_name = key
        fb = fb_rows.get(key)
        log = log_rows.get(key)
        rc = fb.rating_count if fb else 0
        results.append(ModelRatingStats(
            llm_model=model_id,
            step=step_name,
            total_runs=log.total_runs if log else 0,
            avg_tokens=round(log.avg_tokens or 0, 1) if log else 0.0,
            rating_count=rc,
            good_pct=round(fb.good / rc * 100, 1) if fb and rc else 0.0,
            partial_pct=round(fb.partial / rc * 100, 1) if fb and rc else 0.0,
            bad_pct=round(fb.bad / rc * 100, 1) if fb and rc else 0.0,
        ))

    return results
