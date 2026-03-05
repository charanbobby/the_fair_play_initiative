"""
app/routers/attendance.py
--------------------------
Attendance log endpoints:
  - GET  /attendance           list processed logs (filterable by org/region)
  - POST /attendance/upload    upload CSV file, parse and score violations
  - POST /attendance/process   trigger processing of any pending queue
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import AttendanceLogResponse

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("", response_model=List[AttendanceLogResponse])
def list_attendance(
    organization_id: Optional[str] = None,
    region_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(models.AttendanceLog).order_by(models.AttendanceLog.date.desc())
    if organization_id:
        q = q.filter(models.AttendanceLog.organization_id == organization_id)
    if region_id:
        q = q.filter(models.AttendanceLog.region_id == region_id)
    return q.limit(limit).all()


def _parse_time(t: str) -> Optional[datetime]:
    """Try to parse a time string like '09:12 AM' or '09:12'."""
    for fmt in ("%I:%M %p", "%H:%M", "%I:%M%p"):
        try:
            return datetime.strptime(t.strip(), fmt)
        except ValueError:
            continue
    return None


def _score_row(row: dict, rules: List[models.Rule]) -> tuple[Optional[str], float]:
    """
    Given a parsed attendance row and a list of active rules,
    return (violation_name, points).
    """
    violation = None
    points = 0.0

    scheduled_in = _parse_time(row.get("scheduled_in", "09:00 AM") or "09:00 AM")
    actual_in = _parse_time(row.get("actual_in", "") or "")
    scheduled_out = _parse_time(row.get("scheduled_out", "05:00 PM") or "05:00 PM")
    actual_out = _parse_time(row.get("actual_out", "") or "")

    for rule in rules:
        if not rule.active:
            continue

        if rule.condition == "late" and scheduled_in and actual_in:
            delta = (actual_in - scheduled_in).total_seconds() / 60
            if delta > rule.threshold:
                violation = rule.name
                points = rule.points
                break

        elif rule.condition == "early" and scheduled_out and actual_out:
            delta = (scheduled_out - actual_out).total_seconds() / 60
            if delta > rule.threshold:
                violation = rule.name
                points = rule.points
                break

        elif rule.condition == "absence" and not actual_in:
            violation = rule.name
            points = rule.points
            break

        elif rule.condition == "no-call" and not actual_in and not actual_out:
            violation = rule.name
            points = rule.points
            break

    return violation, points


@router.post("/upload", status_code=status.HTTP_200_OK)
async def upload_attendance(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a CSV attendance file with columns:
      employee_id, date, scheduled_in, scheduled_out, actual_in, actual_out

    Returns a summary of how many records were processed and violations found.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    contents = await file.read()
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = contents.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    records_processed = 0
    violations_found = 0

    for row in reader:
        emp_id_raw = row.get("employee_id", "").strip()
        if not emp_id_raw:
            continue

        try:
            emp_id = int(emp_id_raw)
        except ValueError:
            continue

        emp = db.get(models.Employee, emp_id)
        if not emp:
            continue

        # Parse date
        date_raw = row.get("date", "").strip()
        try:
            log_date = date.fromisoformat(date_raw)
        except ValueError:
            log_date = date.today()

        # Get rules for this employee's policy
        if emp.policy_id:
            rules = (
                db.query(models.Rule)
                .filter(models.Rule.policy_id == emp.policy_id, models.Rule.active == True)
                .all()
            )
        else:
            rules = db.query(models.Rule).filter(models.Rule.policy_id.is_(None), models.Rule.active == True).all()

        violation, pts = _score_row(row, rules)

        log = models.AttendanceLog(
            employee_id=emp.id,
            organization_id=emp.organization_id,
            region_id=emp.region_id,
            policy_id=emp.policy_id,
            date=log_date,
            scheduled_in=row.get("scheduled_in", "09:00 AM"),
            scheduled_out=row.get("scheduled_out", "05:00 PM"),
            actual_in=row.get("actual_in", ""),
            actual_out=row.get("actual_out", ""),
            violation=violation,
            points=pts,
            status="Violation" if violation else "Compliant",
        )
        db.add(log)

        if violation and pts > 0:
            violations_found += 1
            emp.points = round(emp.points + pts, 1)

            history = models.PointHistory(
                employee_id=emp.id,
                date=log_date,
                type=violation,
                points=pts,
                status="Active",
            )
            db.add(history)

            # Generate alert if employee crosses 8-point threshold
            if emp.points >= 8:
                alert = models.Alert(
                    organization_id=emp.organization_id,
                    type="danger",
                    message=f"{emp.first_name} {emp.last_name} has exceeded 8 points ({emp.points:.1f}) — review required",
                )
                db.add(alert)

        records_processed += 1

    db.commit()

    return {
        "filename": file.filename,
        "records_processed": records_processed,
        "violations_found": violations_found,
    }


@router.post("/process", status_code=status.HTTP_200_OK)
def process_pending(db: Session = Depends(get_db)):
    """
    Placeholder for processing queued (not yet uploaded) attendance batches.
    Currently returns a status message.
    """
    return {"status": "ok", "message": "No pending queue items — upload a CSV to process."}
