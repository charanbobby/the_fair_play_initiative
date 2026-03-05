"""
app/schemas.py
--------------
Pydantic v2 request/response models for all API endpoints.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field
import uuid


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"


# ---------------------------------------------------------------------------
# /chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Unique session identifier")
    message: str = Field(..., description="User message text")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    citations: list[Any] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# /quotes/draft
# ---------------------------------------------------------------------------

class QuoteDraftRequest(BaseModel):
    input_text: str = Field(..., description="Raw text to extract/draft quotes from")
    style: str = Field(
        default="neutral",
        description="Quote style: 'formal' | 'neutral' | 'informal'",
    )


class QuoteDraftResponse(BaseModel):
    draft_quotes: list[Any] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Error envelope (returned by global exception handler)
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    error: str
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    detail: dict[str, Any] = Field(default_factory=dict)


# ===========================================================================
# FPI Data Models
# ===========================================================================

# ---------------------------------------------------------------------------
# Region
# ---------------------------------------------------------------------------

class RegionBase(BaseModel):
    id: str
    name: str
    code: str
    timezone: str
    labor_laws: str = ""


class RegionCreate(RegionBase):
    pass


class RegionUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    timezone: Optional[str] = None
    labor_laws: Optional[str] = None


class RegionResponse(RegionBase):
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------

class OrganizationBase(BaseModel):
    id: str
    name: str
    code: str
    active: bool = True


class OrganizationCreate(OrganizationBase):
    region_ids: List[str] = Field(default_factory=list)


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    active: Optional[bool] = None
    region_ids: Optional[List[str]] = None


class OrganizationResponse(OrganizationBase):
    region_ids: List[str] = Field(default_factory=list)
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Rule  (declared before Policy so PolicyResponse can embed it)
# ---------------------------------------------------------------------------

class RuleBase(BaseModel):
    name: str
    condition: str
    threshold: int = 0
    points: float
    description: str = ""
    active: bool = True
    policy_id: Optional[str] = None


class RuleCreate(RuleBase):
    pass


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    condition: Optional[str] = None
    threshold: Optional[int] = None
    points: Optional[float] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    policy_id: Optional[str] = None


class RuleResponse(RuleBase):
    id: int
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

class PolicyBase(BaseModel):
    id: str
    name: str
    organization_id: str
    region_id: str
    active: bool = True
    effective_date: Optional[date] = None


class PolicyCreate(PolicyBase):
    pass


class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    organization_id: Optional[str] = None
    region_id: Optional[str] = None
    active: Optional[bool] = None
    effective_date: Optional[date] = None


class PolicyResponse(PolicyBase):
    rules: List[RuleResponse] = Field(default_factory=list)
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# PointHistory
# ---------------------------------------------------------------------------

class PointHistoryBase(BaseModel):
    date: date
    type: str
    points: float
    status: str = "Active"
    reason: Optional[str] = None


class PointHistoryCreate(PointHistoryBase):
    employee_id: int


class PointHistoryResponse(PointHistoryBase):
    id: int
    employee_id: int
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------

class EmployeeBase(BaseModel):
    first_name: str
    last_name: str
    email: str
    department: str = ""
    position: str = ""
    start_date: Optional[date] = None
    organization_id: str
    region_id: str
    policy_id: Optional[str] = None


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    start_date: Optional[date] = None
    organization_id: Optional[str] = None
    region_id: Optional[str] = None
    policy_id: Optional[str] = None


class EmployeeResponse(EmployeeBase):
    id: int
    points: float = 0.0
    trend: str = "stable"
    next_reset: Optional[date] = None
    model_config = {"from_attributes": True}


class EmployeeDetailResponse(EmployeeResponse):
    point_history: List[PointHistoryResponse] = Field(default_factory=list)
    model_config = {"from_attributes": True}


# Override endpoint
class OverrideRequest(BaseModel):
    type: str = Field(..., description="excuse | reduce | reset")
    amount: Optional[float] = None
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# AttendanceLog
# ---------------------------------------------------------------------------

class AttendanceLogBase(BaseModel):
    employee_id: int
    organization_id: str
    region_id: str
    policy_id: Optional[str] = None
    date: date
    scheduled_in: str = "09:00 AM"
    scheduled_out: str = "05:00 PM"
    actual_in: str = ""
    actual_out: str = ""
    violation: Optional[str] = None
    points: float = 0.0
    status: str = "Compliant"


class AttendanceLogCreate(AttendanceLogBase):
    pass


class AttendanceLogResponse(AttendanceLogBase):
    id: int
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------

class AlertBase(BaseModel):
    organization_id: Optional[str] = None
    type: str
    message: str


class AlertCreate(AlertBase):
    pass


class AlertResponse(AlertBase):
    id: int
    created_at: datetime
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardStats(BaseModel):
    total_employees: int
    active_violations: int
    red_flags: int
    total_organizations: int


# ===========================================================================
# Policy Analyzer — keyword extraction + ingestion plan models
# ===========================================================================

class KeywordExtraction(BaseModel):
    policy: list[str] = Field(default_factory=list)
    organization: list[str] = Field(default_factory=list)
    region: list[str] = Field(default_factory=list)
    rule: list[str] = Field(default_factory=list)
    attendance_log: list[str] = Field(default_factory=list)
    point_history: list[str] = Field(default_factory=list)
    alert: list[str] = Field(default_factory=list)
    other_relevant_terms: list[str] = Field(default_factory=list)
    confidence_score: float = 0.0


class TableUsage(BaseModel):
    table: str
    alias: str
    purpose: str


class JoinStep(BaseModel):
    left: str
    right: str
    condition: str
    join_type: str


class FilterCondition(BaseModel):
    description: str
    expression: str
    source_keyword: str


class AggregationStep(BaseModel):
    column_name: str
    expression: str
    purpose: str


class SQLQueryPlan(BaseModel):
    objective: str = ""
    tables_required: list[TableUsage] = Field(default_factory=list)
    joins: list[JoinStep] = Field(default_factory=list)
    where_filters: list[FilterCondition] = Field(default_factory=list)
    grouping_columns: list[str] = Field(default_factory=list)
    aggregations: list[AggregationStep] = Field(default_factory=list)
    having_filters: list[FilterCondition] = Field(default_factory=list)
    output_columns: list[str] = Field(default_factory=list)
    uses_cte: bool = False
    cte_description: Optional[str] = None
    confidence_score: float = 0.0


class PolicyAnalysisResponse(BaseModel):
    filename: str
    keywords: KeywordExtraction
    sql_plan: SQLQueryPlan
