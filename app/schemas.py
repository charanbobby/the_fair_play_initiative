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
    policy: list[str] = Field(default_factory=list, description="Policy-level keywords: codes, names, framework attributes, accrual model type, and scope.")
    organization: list[str] = Field(default_factory=list, description="Organization names and identifiers.")
    region: list[str] = Field(default_factory=list, description="Region names, jurisdictions, and applicable labor laws.")
    rule: list[str] = Field(default_factory=list, description="Rule names, tier definitions, conditions, point thresholds, and escalation criteria.")
    attendance_log: list[str] = Field(default_factory=list, description="Attendance event types, violation definitions, scheduled vs actual time terms, and log statuses.")
    point_history: list[str] = Field(default_factory=list, description="Point accrual, expiration, active status, and reason classification terms.")
    alert: list[str] = Field(default_factory=list, description="Alert types, automatic trigger conditions, escalation actions, and documentation levels.")
    other_relevant_terms: list[str] = Field(default_factory=list, description="Terms relevant to the policy but not directly mappable to a specific schema element.")
    confidence_score: float = Field(default=0.0, description="Confidence score of the extraction between 0.0 and 1.0.")


class TableUsage(BaseModel):
    table: str = Field(description="Exact table name from the FPI schema.")
    alias: str = Field(description="Short alias used in the SQL query (e.g. 'o' for organization).")
    purpose: str = Field(description="One sentence: why this table is needed for this query.")


class JoinStep(BaseModel):
    left: str = Field(description="Left-side table alias or name (child table holding the FK).")
    right: str = Field(description="Right-side table alias or name (parent table holding the PK).")
    condition: str = Field(description="FK dependency expression, e.g. 'organization_region.organization_id = organization.id'.")
    join_type: str = Field(description="JOIN type: INNER, LEFT, RIGHT, or FULL.")


class FilterCondition(BaseModel):
    description: str = Field(description="Plain-English description of what this filter does.")
    expression: str = Field(description="The natural-key expression for the existence check.")
    source_keyword: str = Field(description="The extracted keyword that motivated this filter.")


class AggregationStep(BaseModel):
    column_name: str = Field(description="Output column alias for this aggregation.")
    expression: str = Field(description="The aggregate SQL expression.")
    purpose: str = Field(description="What business question this aggregation answers.")


class SQLQueryPlan(BaseModel):
    objective: str = Field(
        default="",
        description="One sentence: what does this SQL operation accomplish? "
                    "For ingestion plans, describe what data is being inserted and into which tables. "
                    "Do NOT describe downstream analytics or reporting use cases.",
    )
    tables_required: list[TableUsage] = Field(
        default_factory=list,
        description="All tables needed, with aliases and purpose.",
    )
    joins: list[JoinStep] = Field(
        default_factory=list,
        description="FK dependency chains: child table (left) → parent table (right), in dependency order.",
    )
    where_filters: list[FilterCondition] = Field(
        default_factory=list,
        description="Existence checks using natural keys, each tied to a source keyword.",
    )
    grouping_columns: list[str] = Field(
        default_factory=list,
        description="Column references to include in GROUP BY. Leave empty for ingestion plans.",
    )
    aggregations: list[AggregationStep] = Field(
        default_factory=list,
        description="All aggregate columns to compute. Leave empty for ingestion plans.",
    )
    having_filters: list[FilterCondition] = Field(
        default_factory=list,
        description="Post-aggregation HAVING filters. Leave empty for ingestion plans.",
    )
    output_columns: list[str] = Field(
        default_factory=list,
        description="Final SELECT column names or aliases. Leave empty for ingestion plans.",
    )
    uses_cte: bool = Field(
        default=False,
        description="True if the plan requires CTE-style ID chaining across INSERT steps.",
    )
    cte_description: Optional[str] = Field(
        default=None,
        description="Complete procedural plan: per-table column mappings, all rule row enumerations, ID chaining summary, and operational reminders.",
    )
    confidence_score: float = Field(
        default=0.0,
        description="Confidence in the plan's correctness and completeness, 0.0–1.0. "
                    "Deduct for placeholder values, ambiguous clauses, unclear thresholds, "
                    "and incomplete source text. Typical range: 0.60–0.90. "
                    "1.0 means zero ambiguity — this is rare.",
    )


class PolicyAnalysisResponse(BaseModel):
    filename: str
    keywords: KeywordExtraction
    sql_plan: SQLQueryPlan
    formatted_keywords: str = Field(default="", description="Plain-text formatted keywords (matches notebook output).")
    formatted_plan: str = Field(default="", description="Plain-text formatted plan (matches notebook output).")
