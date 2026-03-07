"""
app/services/policy_analyzer.py
---------------------------------
LangGraph pipeline: PDF/DOCX/TXT → keyword extraction → entity reconciliation
                    → SQL ingestion plan → (optional) SQL generation.

Nodes:
    node_extract      — LLM extracts schema-mapped keywords from policy text
    node_reconcile    — LLM matches extracted entities against existing DB records
    node_plan         — LLM devises a structured INSERT plan from keywords
    node_generate_sql — LLM generates executable INSERT statements from the plan

Graph:  START → node_extract → node_reconcile → node_plan → [node_generate_sql]? → END

SQL execution happens outside the graph (in the endpoint) using the FastAPI
db session — see ``execute_sql_against_db()``.
"""

from __future__ import annotations

import asyncio
import io
import json
import re
import logging
import warnings
from pathlib import Path
from typing import AsyncGenerator, TypedDict

log = logging.getLogger(__name__)

# Suppress harmless Pydantic v2 serializer warning from LangChain's
# with_structured_output(include_raw=True) — the "parsed" field type
# annotation is Optional but always populated on success.
warnings.filterwarnings("ignore", message="Pydantic serializer warnings")

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.schemas import (
    ConflictWarning,
    KeywordExtraction,
    PolicyAnalysisResponse,
    QueryResults,
    Reconciliation,
    ReconciliationResult,
    SQLGeneration,
    SQLQueryPlan,
    TokenUsage,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# ---------------------------------------------------------------------------
# Load prompts at module level (fail fast if files are missing)
# ---------------------------------------------------------------------------

_KEYWORD_SYSTEM_MSG: str = (_PROMPTS_DIR / "01_keyword_extraction.md").read_text(encoding="utf-8")
_PLAN_SYSTEM_TEMPLATE: str = (_PROMPTS_DIR / "02_sql_query_plan.md").read_text(encoding="utf-8")
_SCHEMA_JSON: str = (_PROMPTS_DIR / "schema.json").read_text(encoding="utf-8")

# Inject schema into plan prompt once at load time
_PLAN_SYSTEM_MSG: str = _PLAN_SYSTEM_TEMPLATE.replace("{{schema}}", _SCHEMA_JSON)

_SQL_GEN_SYSTEM_TEMPLATE: str = (_PROMPTS_DIR / "03_sql_generation.md").read_text(encoding="utf-8")
_SQL_GEN_SYSTEM_MSG: str = _SQL_GEN_SYSTEM_TEMPLATE.replace("{{schema}}", _SCHEMA_JSON)

_RECONCILE_SYSTEM_MSG: str = (_PROMPTS_DIR / "01b_reconciliation.md").read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# LLM — ChatOpenAI pointed at OpenRouter
# ---------------------------------------------------------------------------

def _build_model(
    model_override: str | None = None,
    max_tokens: int | None = None,
) -> ChatOpenAI:
    api_key = settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY
    model_name = model_override or settings.LLM_MODEL or "google/gemini-3-flash-preview"
    kwargs: dict = dict(
        model=model_name,
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        temperature=0,
    )
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatOpenAI(**kwargs)


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------

class FPIState(TypedDict):
    pdf_text: str
    model_extract: str | None
    model_plan: str | None
    model_sql: str | None
    model_reconcile: str | None
    keywords: KeywordExtraction | None
    sql_plan: SQLQueryPlan | None
    sql_result: SQLGeneration | None
    # Pre-queried existing DB records (serializable dicts, not ORM objects)
    existing_organizations: list[dict] | None
    existing_regions: list[dict] | None
    existing_policies: list[dict] | None
    # Reconciliation output
    reconciliation: Reconciliation | None
    extract_tokens: dict | None
    reconcile_tokens: dict | None
    plan_tokens: dict | None
    sql_tokens: dict | None
    extract_duration_ms: int | None
    reconcile_duration_ms: int | None
    plan_duration_ms: int | None
    sql_duration_ms: int | None
    error: str | None


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def _extract_token_usage(raw_msg) -> dict:
    """Pull token counts from an AIMessage's usage_metadata."""
    usage = getattr(raw_msg, "usage_metadata", None) or {}
    log.info("RAW usage_metadata: %s", usage)
    result = {
        "prompt": usage.get("input_tokens", 0),
        "completion": usage.get("output_tokens", 0),
        "total": usage.get("total_tokens", 0),
    }
    details = usage.get("input_token_details") or {}
    cache_read = details.get("cache_read", 0) or 0
    cache_creation = details.get("cache_creation", 0) or 0
    if cache_read or cache_creation:
        result["cache_read"] = cache_read
        result["cache_creation"] = cache_creation
    return result


def _cacheable_system_msg(text: str) -> SystemMessage:
    """Wrap system prompt with cache_control for OpenRouter prompt caching."""
    return SystemMessage(content=[{
        "type": "text",
        "text": text,
        "cache_control": {"type": "ephemeral"},
    }])


def node_extract(state: FPIState) -> dict:
    """Categorise policy keywords into schema-mapped groups."""
    import time
    t0 = time.perf_counter()
    model = _build_model(state.get("model_extract")).with_structured_output(
        KeywordExtraction, include_raw=True
    )
    raw_result = model.invoke([
        _cacheable_system_msg(_KEYWORD_SYSTEM_MSG),
        HumanMessage(content=state["pdf_text"]),
    ])
    duration_ms = int((time.perf_counter() - t0) * 1000)
    result = raw_result["parsed"]
    tokens = _extract_token_usage(raw_result.get("raw"))
    # Post-process: enforce realistic confidence
    if result.confidence_score >= 1.0:
        result.confidence_score = 0.85
    result.confidence_score = round(min(result.confidence_score, 0.95), 2)
    return {"keywords": result, "extract_tokens": tokens, "extract_duration_ms": duration_ms}


# ---------------------------------------------------------------------------
# Reconciliation helpers
# ---------------------------------------------------------------------------

def _build_reconciliation_human_msg(
    keywords: KeywordExtraction,
    existing_orgs: list[dict],
    existing_regions: list[dict],
    existing_policies: list[dict],
) -> str:
    """Build the human message for the reconciliation LLM call."""
    lines = ["Match the extracted entities below against the existing database records.\n"]

    lines.append("## Extracted Entities (from policy document)\n")
    if keywords.organization:
        lines.append(f"Organizations: {', '.join(keywords.organization)}")
    if keywords.region:
        lines.append(f"Regions: {', '.join(keywords.region)}")
    if keywords.policy:
        lines.append(f"Policies: {', '.join(keywords.policy)}")

    lines.append("\n## Existing Database Records\n")

    if existing_orgs:
        lines.append("### Organizations")
        for org in existing_orgs:
            lines.append(f"  - id: {org['id']}, name: {org['name']}, code: {org.get('code', '')}")
    else:
        lines.append("### Organizations\n  (none)")

    if existing_regions:
        lines.append("### Regions")
        for r in existing_regions:
            lines.append(f"  - id: {r['id']}, name: {r['name']}, code: {r.get('code', '')}")
    else:
        lines.append("### Regions\n  (none)")

    if existing_policies:
        lines.append("### Policies")
        for p in existing_policies:
            lines.append(
                f"  - id: {p['id']}, name: {p['name']}, "
                f"org_id: {p['organization_id']}, "
                f"effective_date: {p.get('effective_date') or 'N/A'}"
            )
    else:
        lines.append("### Policies\n  (none)")

    return "\n".join(lines)


def _detect_conflicts(
    keywords: KeywordExtraction,
    matches: ReconciliationResult,
    existing_orgs: list[dict],
    existing_regions: list[dict],
    existing_policies: list[dict],
) -> list[ConflictWarning]:
    """Deterministic conflict detection: date overlaps, active-policy overwrites."""
    conflicts: list[ConflictWarning] = []

    # 1. Matched active policy → overwrite warning
    for pm in matches.policy_matches:
        if pm.confidence < 0.7:
            continue
        matched = next((p for p in existing_policies if p["id"] == pm.matched_id), None)
        if matched and matched.get("active", True):
            conflicts.append(ConflictWarning(
                severity="warning",
                conflict_type="active_overwrite",
                message=(
                    f"Policy '{pm.extracted_name}' matches existing active policy "
                    f"'{matched['name']}' (id: {matched['id']}). "
                    f"Proceeding will update the existing record via INSERT OR REPLACE."
                ),
                existing_record=matched,
                suggested_action="overwrite",
            ))

    # 2. Date overlap: new policy shares effective_date with another active
    #    policy for the same org+region
    for pm in matches.policy_matches:
        if pm.confidence < 0.7:
            continue
        matched = next((p for p in existing_policies if p["id"] == pm.matched_id), None)
        if not matched:
            continue
        org_id = matched.get("organization_id")
        region_id = matched.get("region_id")
        eff_date = matched.get("effective_date")
        if not eff_date:
            continue
        siblings = [
            p for p in existing_policies
            if p["organization_id"] == org_id
            and p.get("region_id") == region_id
            and p["id"] != matched["id"]
            and p.get("active", True)
            and p.get("effective_date") == eff_date
        ]
        for sib in siblings:
            conflicts.append(ConflictWarning(
                severity="error",
                conflict_type="date_overlap",
                message=(
                    f"Two active policies for org '{org_id}' in region '{region_id}' "
                    f"share effective_date {eff_date}: "
                    f"'{sib['name']}' and '{matched['name']}'."
                ),
                existing_record=sib,
                suggested_action="review",
            ))

    return conflicts


def _format_reconciliation_for_plan(recon: Reconciliation) -> str:
    """Format reconciliation results as instructions for the plan node."""
    lines = ["## Entity Reconciliation (MUST follow these ID assignments)\n"]
    lines.append(
        "The following entities already exist in the database. "
        "You MUST use the existing IDs shown below instead of generating new slug IDs. "
        "Use INSERT OR IGNORE for these existing records.\n"
    )

    if recon.existing_ids:
        lines.append("### Existing IDs to reuse:")
        for key, existing_id in recon.existing_ids.items():
            entity_type, extracted_name = key.split(":", 1)
            lines.append(f"  - {entity_type}: '{extracted_name}' -> use id = '{existing_id}'")
        lines.append("")

    if recon.matches.no_match_entities:
        lines.append("### New entities (generate new slug IDs):")
        for e in recon.matches.no_match_entities:
            lines.append(f"  - {e}")
        lines.append("")

    if recon.conflicts:
        lines.append("### Conflicts detected (include in operational_reminders):")
        for c in recon.conflicts:
            lines.append(f"  - [{c.severity.upper()}] {c.message}")
        lines.append("")

    return "\n".join(lines) + "\n\n"


def node_reconcile(state: FPIState) -> dict:
    """Match extracted entities against existing DB records using LLM semantic matching.

    Fast pass-through if no existing records are present in the DB.
    Deterministic conflict detection runs after LLM matching.
    """
    import time

    keywords = state.get("keywords")
    if not keywords:
        return {"error": "node_reconcile: no keywords in state"}

    existing_orgs = state.get("existing_organizations") or []
    existing_regions = state.get("existing_regions") or []
    existing_policies = state.get("existing_policies") or []

    has_existing = bool(existing_orgs or existing_regions or existing_policies)

    # Fast pass-through: empty DB, nothing to reconcile
    if not has_existing:
        return {
            "reconciliation": Reconciliation(is_pass_through=True),
            "reconcile_tokens": {"prompt": 0, "completion": 0, "total": 0},
            "reconcile_duration_ms": 0,
        }

    t0 = time.perf_counter()

    model = _build_model(state.get("model_reconcile")).with_structured_output(
        ReconciliationResult, include_raw=True
    )

    human_msg = _build_reconciliation_human_msg(
        keywords, existing_orgs, existing_regions, existing_policies
    )

    raw_result = model.invoke([
        _cacheable_system_msg(_RECONCILE_SYSTEM_MSG),
        HumanMessage(content=human_msg),
    ])

    duration_ms = int((time.perf_counter() - t0) * 1000)
    matches_result: ReconciliationResult = raw_result["parsed"]
    tokens = _extract_token_usage(raw_result.get("raw"))

    # Build existing_ids lookup from high-confidence LLM matches
    existing_ids: dict[str, str] = {}
    for m in matches_result.organization_matches:
        if m.confidence >= 0.7:
            existing_ids[f"organization:{m.extracted_name}"] = m.matched_id
    for m in matches_result.region_matches:
        if m.confidence >= 0.7:
            existing_ids[f"region:{m.extracted_name}"] = m.matched_id
    for m in matches_result.policy_matches:
        if m.confidence >= 0.7:
            existing_ids[f"policy:{m.extracted_name}"] = m.matched_id

    # Deterministic conflict detection
    conflicts = _detect_conflicts(
        keywords, matches_result,
        existing_orgs, existing_regions, existing_policies,
    )

    reconciliation = Reconciliation(
        matches=matches_result,
        conflicts=conflicts,
        existing_ids=existing_ids,
        is_pass_through=False,
    )

    return {
        "reconciliation": reconciliation,
        "reconcile_tokens": tokens,
        "reconcile_duration_ms": duration_ms,
    }


def _adjust_confidence(score: float, has_placeholders: bool) -> float:
    """Clamp LLM confidence to a realistic range.
    The input document is always truncated, so 1.0 is never valid.
    """
    if score >= 1.0:
        score = 0.82  # sensible default when LLM ignores instructions
    if has_placeholders and score > 0.85:
        score = 0.85
    return round(min(max(score, 0.0), 0.95), 2)


def node_plan(state: FPIState) -> dict:
    """Devise a structured INSERT/UPSERT plan from extracted keywords."""
    if not state.get("keywords"):
        return {"error": "node_plan: no keywords in state"}

    import time
    t0 = time.perf_counter()
    model = _build_model(
        state.get("model_plan"), max_tokens=32768
    ).with_structured_output(SQLQueryPlan, include_raw=True)
    recon = state.get("reconciliation")
    recon_section = ""
    if recon and not recon.is_pass_through:
        recon_section = _format_reconciliation_for_plan(recon)

    human_msg = (
        "Devise an ingestion plan for the following keywords extracted from the "
        "attendance policy document. The plan must describe how to INSERT this "
        "policy's data into the FPI configuration tables. Do NOT write SQL.\n\n"
        f"## Extracted Keywords\n\n{_format_keywords(state['keywords'])}\n\n"
        f"{recon_section}"
        f"## Policy Document (for context)\n\n{state['pdf_text']}"
    )
    raw_result = model.invoke([
        _cacheable_system_msg(_PLAN_SYSTEM_MSG),
        HumanMessage(content=human_msg),
    ])
    duration_ms = int((time.perf_counter() - t0) * 1000)
    result = raw_result["parsed"]
    tokens = _extract_token_usage(raw_result.get("raw"))
    # Post-process: enforce realistic confidence scores
    has_placeholders = any(
        "[uncertain]" in cm.value_source.lower()
        for step in result.table_steps
        for cm in step.columns
    ) or any(
        "uncertain" in r.lower()
        for r in result.operational_reminders
    )
    result.confidence_score = _adjust_confidence(result.confidence_score, has_placeholders)
    # Synthesize legacy cte_description from structured fields
    if result.table_steps or result.rule_rows:
        result.cte_description = _synthesize_cte_description(result)
    return {"sql_plan": result, "plan_tokens": tokens, "plan_duration_ms": duration_ms}


def node_generate_sql(state: FPIState) -> dict:
    """Generate executable SQL INSERT statements from the approved plan."""
    if not state.get("sql_plan"):
        return {"error": "node_generate_sql: no sql_plan in state"}
    if not state.get("keywords"):
        return {"error": "node_generate_sql: no keywords in state"}

    import time
    t0 = time.perf_counter()
    model = _build_model(
        state.get("model_sql"), max_tokens=32768
    ).with_structured_output(SQLGeneration, include_raw=True)
    recon = state.get("reconciliation")
    recon_ids_section = ""
    if recon and not recon.is_pass_through and recon.existing_ids:
        id_lines = "\n".join(
            f"  - {k}: '{v}'" for k, v in recon.existing_ids.items()
        )
        recon_ids_section = (
            "\n\n## Existing Entity IDs (use these exact IDs in FK references)\n\n"
            f"{id_lines}\n"
        )

    human_msg = (
        "Generate INSERT SQL implementing the ingestion plan below.\n\n"
        "## Approved Ingestion Plan\n\n"
        f"{_format_plan_for_sql_prompt(state['sql_plan'])}\n\n"
        "## Extracted Keywords (source values for INSERT literals)\n\n"
        f"{_format_keywords(state['keywords'])}"
        f"{recon_ids_section}"
    )
    raw_result = model.invoke([
        _cacheable_system_msg(_SQL_GEN_SYSTEM_MSG),
        HumanMessage(content=human_msg),
    ])
    duration_ms = int((time.perf_counter() - t0) * 1000)
    result = raw_result["parsed"]
    tokens = _extract_token_usage(raw_result.get("raw"))

    # Post-process: enforce realistic confidence
    if result.confidence_score >= 1.0:
        result.confidence_score = 0.82
    result.confidence_score = round(min(result.confidence_score, 0.95), 2)

    return {
        "sql_result": result,
        "sql_tokens": tokens,
        "sql_duration_ms": duration_ms,
    }


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _route_after_plan(state: FPIState) -> str:
    """Route to SQL generation if model_sql is provided, otherwise end."""
    if state.get("model_sql"):
        return "node_generate_sql"
    return END


def _build_graph() -> StateGraph:
    g = StateGraph(FPIState)
    g.add_node("node_extract", node_extract)
    g.add_node("node_reconcile", node_reconcile)
    g.add_node("node_plan", node_plan)
    g.add_node("node_generate_sql", node_generate_sql)
    g.add_edge(START, "node_extract")
    g.add_edge("node_extract", "node_reconcile")
    g.add_edge("node_reconcile", "node_plan")
    g.add_conditional_edges("node_plan", _route_after_plan)
    g.add_edge("node_generate_sql", END)
    return g.compile()


_graph = _build_graph()


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def _extract_text_from_pdf(content: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _extract_text_from_docx(content: bytes) -> str:
    import docx  # python-docx
    doc = docx.Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_text(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _extract_text_from_pdf(content)
    if ext in (".docx", ".doc"):
        return _extract_text_from_docx(content)
    # TXT and everything else — assume UTF-8 text
    return content.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Helper: format keywords for the plan prompt human message
# ---------------------------------------------------------------------------

_KEYWORD_FIELDS = [
    "policy", "organization", "region", "rule",
    "attendance_log", "point_history", "alert", "other_relevant_terms",
]


def _format_keywords(kw: KeywordExtraction) -> str:
    """Format a KeywordExtraction into a readable string for downstream prompts."""
    lines: list[str] = []
    for field in _KEYWORD_FIELDS:
        values = getattr(kw, field, [])
        if values:
            lines.append(f"[{field}]")
            lines.extend(f"  • {v}" for v in values)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper: plain-text serialiser for SQLQueryPlan (matches notebook output)
# ---------------------------------------------------------------------------

def _synthesize_cte_description(plan: SQLQueryPlan) -> str:
    """Build a legacy cte_description string from structured fields."""
    parts: list[str] = []
    for step in plan.table_steps:
        col_str = "; ".join(f"{c.column}={c.value_source}" for c in step.columns)
        parts.append(
            f"{step.step_number}) {step.table} — {step.strategy}; "
            f"columns: {col_str}; natural key: {step.natural_key}"
        )
    if plan.rule_rows:
        violations = [r for r in plan.rule_rows if r.category == "violation"]
        exemptions = [r for r in plan.rule_rows if r.category == "exemption"]
        reductions = [r for r in plan.rule_rows if r.category == "reduction"]
        for label, group in [
            ("A) Violation rules", violations),
            ("B) Exemption rules", exemptions),
            ("C) Reduction rules", reductions),
        ]:
            if group:
                parts.append(label)
                for i, r in enumerate(group, 1):
                    parts.append(
                        f"  {i}. id: {r.id}\n"
                        f"     name: {r.name}\n"
                        f"     condition: {r.condition}\n"
                        f"     threshold: {r.threshold}\n"
                        f"     points: {r.points}\n"
                        f"     description: {r.description}\n"
                        f"     active: {r.active}"
                    )
    if plan.id_chaining_summary:
        parts.append("ID chaining summary")
        parts.extend(f"  {c}" for c in plan.id_chaining_summary)
    if plan.operational_reminders:
        parts.append("Operational reminders")
        parts.extend(f"  — {r}" for r in plan.operational_reminders)
    return "\n".join(parts)


def _format_plan(plan: SQLQueryPlan) -> str:
    lines: list[str] = []
    lines.append(f"OBJECTIVE\n  {plan.objective}\n")

    if plan.tables_required:
        lines.append("TABLES")
        for t in plan.tables_required:
            lines.append(f"  [{t.alias}] {t.table}")
            lines.append(f"       purpose: {t.purpose}")
        lines.append("")

    if plan.joins:
        lines.append("JOINS")
        for j in plan.joins:
            lines.append(f"  {j.join_type} JOIN {j.right} ON {j.condition}")
        lines.append("")

    if plan.where_filters:
        lines.append("WHERE FILTERS")
        for f in plan.where_filters:
            lines.append(f"  • {f.description}")
            lines.append(f"    expr   : {f.expression}")
            lines.append(f"    keyword: {f.source_keyword}")
        lines.append("")

    if plan.grouping_columns:
        lines.append("GROUP BY")
        lines.append("  " + ", ".join(plan.grouping_columns))
        lines.append("")

    if plan.aggregations:
        lines.append("AGGREGATIONS")
        for a in plan.aggregations:
            lines.append(f"  [{a.column_name}]")
            lines.append(f"    expr   : {a.expression}")
            lines.append(f"    purpose: {a.purpose}")
        lines.append("")

    if plan.having_filters:
        lines.append("HAVING FILTERS")
        for f in plan.having_filters:
            lines.append(f"  • {f.description}")
            lines.append(f"    expr   : {f.expression}")
            lines.append(f"    keyword: {f.source_keyword}")
        lines.append("")

    if plan.output_columns:
        lines.append("OUTPUT COLUMNS")
        lines.append("  " + ", ".join(plan.output_columns))
        lines.append("")

    # ── Structured ingestion plan sections ────────────────────────────
    if plan.table_steps:
        lines.append("INGESTION STEPS")
        for step in plan.table_steps:
            lines.append(f"  {step.step_number}) {step.table} — {step.strategy}")
            for col in step.columns:
                lines.append(f"       {col.column}: {col.value_source}")
            lines.append(f"       natural key: {step.natural_key}")
        lines.append("")

    if plan.rule_rows:
        violations = [r for r in plan.rule_rows if r.category == "violation"]
        exemptions = [r for r in plan.rule_rows if r.category == "exemption"]
        reductions = [r for r in plan.rule_rows if r.category == "reduction"]
        lines.append("RULE ROWS")
        for label, group in [
            ("A) Violation/Occurrence Rules", violations),
            ("B) Approved-Leave Exemption Rules", exemptions),
            ("C) Perfect-Attendance Reduction Rules", reductions),
        ]:
            if group:
                lines.append(f"  {label}")
                for i, r in enumerate(group, 1):
                    lines.append(f"    {i}. id: {r.id}")
                    lines.append(f"       name: {r.name}")
                    lines.append(f"       condition: {r.condition}")
                    lines.append(f"       threshold: {r.threshold}")
                    lines.append(f"       points: {r.points}")
                    if r.description:
                        lines.append(f"       description: {r.description}")
                    lines.append(f"       active: {r.active}")
        lines.append("")

    if plan.id_chaining_summary:
        lines.append("ID CHAINING SUMMARY")
        for chain in plan.id_chaining_summary:
            lines.append(f"  {chain}")
        lines.append("")

    if plan.operational_reminders:
        lines.append("OPERATIONAL REMINDERS")
        for reminder in plan.operational_reminders:
            lines.append(f"  — {reminder}")
        lines.append("")

    # Legacy fallback: if only cte_description is populated (old cached response)
    if plan.uses_cte and not plan.table_steps and plan.cte_description:
        lines.append("CTE")
        lines.append(f"  {plan.cte_description}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper: format plan for the SQL generation prompt
# ---------------------------------------------------------------------------

def _format_plan_for_sql_prompt(plan: SQLQueryPlan) -> str:
    """Structured plan format optimised for the SQL generation model."""
    lines = [f"Objective: {plan.objective}", ""]

    if plan.tables_required:
        lines.append("Tables (in INSERT order):")
        for t in plan.tables_required:
            lines.append(f"  {t.table} AS {t.alias} — {t.purpose}")
        lines.append("")

    if plan.joins:
        lines.append("FK Dependencies:")
        for j in plan.joins:
            lines.append(f"  {j.left} -> {j.right} ON {j.condition}")
        lines.append("")

    if plan.where_filters:
        lines.append("Existence checks:")
        for f in plan.where_filters:
            lines.append(f"  {f.description}")
            lines.append(f"    expr: {f.expression}  (keyword: {f.source_keyword})")
        lines.append("")

    if plan.table_steps:
        lines.append("Ingestion Steps:")
        for step in plan.table_steps:
            col_str = "; ".join(f"{c.column}={c.value_source}" for c in step.columns)
            lines.append(
                f"  {step.step_number}) {step.table} — {step.strategy}; "
                f"columns: {col_str}; natural key: {step.natural_key}"
            )
        lines.append("")

    if plan.rule_rows:
        lines.append(f"Rule Rows ({len(plan.rule_rows)} total):")
        for r in plan.rule_rows:
            lines.append(
                f"  {r.id}: {r.name} | {r.category} | thresh={r.threshold} | "
                f"pts={r.points} | active={r.active}"
            )
        lines.append("")

    if plan.id_chaining_summary:
        lines.append("ID Chaining:")
        for c in plan.id_chaining_summary:
            lines.append(f"  {c}")
        lines.append("")

    if plan.uses_cte and plan.cte_description:
        lines.append("Procedural plan (cte_description):")
        lines.append(plan.cte_description)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SQL Execution (called from endpoint, not from graph)
# ---------------------------------------------------------------------------

# Table name mapping: schema.json (singular) → ORM/DB (plural)
_TABLE_NAME_MAP = {
    "organization": "organizations",
    "region": "regions",
    "policy": "policies",
    "rule": "rules",
    # organization_region stays the same
}

# Config tables to count after execution (actual DB names)
_CONFIG_TABLES = ["organizations", "regions", "organization_region", "policies", "rules"]


def _rewrite_table_names(sql: str) -> str:
    """Rewrite singular table names in LLM-generated SQL to match actual DB schema.

    Uses word-boundary regex. Safe because ``\\b`` treats ``_`` as a word char,
    so ``organization_id`` and ``organization_region`` are NOT matched.
    """
    for singular, plural in _TABLE_NAME_MAP.items():
        sql = re.sub(rf"\b{singular}\b", plural, sql)
    return sql


def _rewrite_sqlite_to_pg(sql: str) -> str:
    """Convert SQLite INSERT syntax to PostgreSQL equivalents.

    Processes each statement individually (via quote-aware splitter) so
    unescaped apostrophes inside LLM-generated string literals don't
    break the rewrite.

    - INSERT OR IGNORE  → append ON CONFLICT DO NOTHING
    - INSERT OR REPLACE → append ON CONFLICT (id) DO UPDATE SET ...
    """
    stmts = _split_sql_statements(sql)
    result: list[str] = []

    for stmt in stmts:
        upper = stmt.upper()

        if "INSERT OR IGNORE" in upper:
            # Remove "OR IGNORE", append ON CONFLICT DO NOTHING
            new = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", stmt, flags=re.IGNORECASE)
            new += " ON CONFLICT DO NOTHING"
            result.append(new)

        elif "INSERT OR REPLACE" in upper:
            # Remove "OR REPLACE", extract column list for ON CONFLICT UPDATE
            new = re.sub(r"INSERT\s+OR\s+REPLACE\s+INTO", "INSERT INTO", stmt, flags=re.IGNORECASE)
            # Extract column names from the first parenthesised group after INTO table
            cols_match = re.search(r"INTO\s+\S+\s*\(([^)]+)\)", new, re.IGNORECASE)
            if cols_match:
                cols = [c.strip() for c in cols_match.group(1).split(",")]
                update_cols = [c for c in cols if c != "id"]
                if update_cols:
                    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
                    new += f" ON CONFLICT (id) DO UPDATE SET {set_clause}"
                else:
                    new += " ON CONFLICT (id) DO NOTHING"
            else:
                new += " ON CONFLICT DO NOTHING"
            result.append(new)

        else:
            result.append(stmt)

    return ";\n".join(result)


def _split_sql_statements(sql: str) -> list[str]:
    """Split SQL text on statement-terminating semicolons, ignoring ``;`` inside single-quoted strings."""
    stmts: list[str] = []
    current: list[str] = []
    in_quote = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'" and not in_quote:
            in_quote = True
            current.append(ch)
        elif ch == "'" and in_quote:
            # Handle escaped quotes ('')
            if i + 1 < len(sql) and sql[i + 1] == "'":
                current.append("''")
                i += 1
            else:
                in_quote = False
                current.append(ch)
        elif ch == "\\" and in_quote and i + 1 < len(sql) and sql[i + 1] == "'":
            # Handle backslash-escaped quotes (\') — treat as escaped, stay in_quote
            current.append("''")
            i += 1
        elif ch == ";" and not in_quote:
            stmt = "".join(current).strip()
            if stmt:
                stmts.append(stmt)
            current = []
        else:
            current.append(ch)
        i += 1
    # Trailing statement without semicolon
    stmt = "".join(current).strip()
    if stmt:
        stmts.append(stmt)
    return stmts


def fetch_existing_records(db) -> dict:
    """Pre-query existing organizations, regions, and policies from the DB.

    Returns serializable dicts (not ORM objects) suitable for passing into
    FPIState.  Called from the endpoint, NOT from the graph.
    """
    from sqlalchemy import text

    organizations: list[dict] = []
    regions: list[dict] = []
    policies: list[dict] = []

    try:
        rows = db.execute(text("SELECT id, name, code, active FROM organizations")).fetchall()
        organizations = [
            {"id": r[0], "name": r[1], "code": r[2], "active": r[3]}
            for r in rows
        ]
    except Exception:
        pass  # table may not exist yet

    try:
        rows = db.execute(text("SELECT id, name, code, timezone FROM regions")).fetchall()
        regions = [
            {"id": r[0], "name": r[1], "code": r[2], "timezone": r[3]}
            for r in rows
        ]
    except Exception:
        pass

    try:
        rows = db.execute(text(
            "SELECT id, name, organization_id, region_id, active, effective_date "
            "FROM policies"
        )).fetchall()
        policies = [
            {
                "id": r[0], "name": r[1], "organization_id": r[2],
                "region_id": r[3], "active": r[4],
                "effective_date": str(r[5]) if r[5] else None,
            }
            for r in rows
        ]
    except Exception:
        pass

    return {
        "existing_organizations": organizations,
        "existing_regions": regions,
        "existing_policies": policies,
    }


def execute_sql_against_db(
    db,
    sql_result: SQLGeneration,
    is_sqlite: bool,
) -> QueryResults:
    """Execute LLM-generated SQL against the database.

    Args:
        db: SQLAlchemy session from FastAPI dependency
        sql_result: The SQLGeneration output from the LLM
        is_sqlite: Whether we're running against SQLite
    """
    import time
    from sqlalchemy import text

    t0 = time.perf_counter()

    raw_sql = sql_result.sql_query.strip()
    if not raw_sql:
        return QueryResults(error="Empty SQL query")

    rewritten_sql = _rewrite_table_names(raw_sql)
    if not is_sqlite:
        rewritten_sql = _rewrite_sqlite_to_pg(rewritten_sql)

    try:
        if is_sqlite:
            raw_conn = db.get_bind().raw_connection()
            raw_conn.executescript(rewritten_sql)
            raw_conn.commit()
        else:
            statements = _split_sql_statements(rewritten_sql)
            for stmt in statements:
                db.execute(text(stmt))
            db.commit()

        counts = {}
        total = 0
        for tbl in _CONFIG_TABLES:
            try:
                row = db.execute(text(f"SELECT COUNT(*) FROM {tbl}")).fetchone()
                count = row[0] if row else 0
                counts[tbl] = count
                total += count
            except Exception:
                counts[tbl] = 0

        duration_ms = int((time.perf_counter() - t0) * 1000)
        return QueryResults(
            row_counts=counts,
            total_rows=total,
            execution_duration_ms=duration_ms,
        )
    except Exception as exc:
        db.rollback()
        duration_ms = int((time.perf_counter() - t0) * 1000)
        return QueryResults(
            error=str(exc),
            execution_duration_ms=duration_ms,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def analyze_policy_document(
    filename: str,
    content: bytes,
    model_extract: str | None = None,
    model_plan: str | None = None,
    model_sql: str | None = None,
    model_reconcile: str | None = None,
    existing_records: dict | None = None,
) -> PolicyAnalysisResponse:
    """
    Extract text from the uploaded file, run the LangGraph pipeline,
    and return keywords + reconciliation + SQL ingestion plan + (optionally) SQL.

    Raises ValueError if the OPENROUTER_API_KEY is not configured.
    """
    api_key = settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY (or OPENAI_API_KEY) is not set. "
            "Policy analysis requires an LLM provider."
        )

    pdf_text = _extract_text(filename, content)
    _er = existing_records or {}

    initial_state: FPIState = {
        "pdf_text": pdf_text,
        "model_extract": model_extract or None,
        "model_plan": model_plan or None,
        "model_sql": model_sql or None,
        "model_reconcile": model_reconcile or None,
        "keywords": None,
        "sql_plan": None,
        "sql_result": None,
        "existing_organizations": _er.get("existing_organizations"),
        "existing_regions": _er.get("existing_regions"),
        "existing_policies": _er.get("existing_policies"),
        "reconciliation": None,
        "extract_tokens": None,
        "reconcile_tokens": None,
        "plan_tokens": None,
        "sql_tokens": None,
        "extract_duration_ms": None,
        "reconcile_duration_ms": None,
        "plan_duration_ms": None,
        "sql_duration_ms": None,
        "error": None,
    }

    # LangGraph invoke is synchronous; run in a thread to stay async-friendly
    import asyncio
    final_state: FPIState = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _graph.invoke(initial_state)
    )

    if final_state.get("error"):
        raise RuntimeError(final_state["error"])

    kw = final_state["keywords"]
    plan = final_state["sql_plan"]
    sql = final_state.get("sql_result")
    et = final_state.get("extract_tokens") or {}
    rt = final_state.get("reconcile_tokens") or {}
    pt = final_state.get("plan_tokens") or {}
    st = final_state.get("sql_tokens") or {}
    token_usage = TokenUsage(
        extract_prompt=et.get("prompt", 0),
        extract_completion=et.get("completion", 0),
        extract_total=et.get("total", 0),
        extract_duration_ms=final_state.get("extract_duration_ms") or 0,
        reconcile_prompt=rt.get("prompt", 0),
        reconcile_completion=rt.get("completion", 0),
        reconcile_total=rt.get("total", 0),
        reconcile_duration_ms=final_state.get("reconcile_duration_ms") or 0,
        plan_prompt=pt.get("prompt", 0),
        plan_completion=pt.get("completion", 0),
        plan_total=pt.get("total", 0),
        plan_duration_ms=final_state.get("plan_duration_ms") or 0,
        sql_prompt=st.get("prompt", 0),
        sql_completion=st.get("completion", 0),
        sql_total=st.get("total", 0),
        sql_duration_ms=final_state.get("sql_duration_ms") or 0,
    )
    return PolicyAnalysisResponse(
        filename=filename,
        keywords=kw,
        reconciliation=final_state.get("reconciliation"),
        sql_plan=plan,
        sql_result=sql,
        formatted_keywords=_format_keywords(kw) if kw else "",
        formatted_plan=_format_plan(plan) if plan else "",
        formatted_sql=sql.sql_query if sql else "",
        token_usage=token_usage,
    )


# ---------------------------------------------------------------------------
# SSE streaming API
# ---------------------------------------------------------------------------

def _sse_event(event_name: str, data: dict) -> str:
    """Format a single Server-Sent Event string."""
    return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"


async def stream_policy_analysis(
    filename: str,
    content: bytes,
    model_extract: str | None = None,
    model_plan: str | None = None,
    model_sql: str | None = None,
    model_reconcile: str | None = None,
    existing_records: dict | None = None,
    db=None,
    analytics_db=None,
    default_model: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Stream analysis results as SSE events, one per graph node completion.

    Uses LangGraph's ``graph.stream()`` in a background thread, pushing
    each node's output through an ``asyncio.Queue`` so the async generator
    can yield SSE events as soon as each step finishes.
    """
    import logging
    log = logging.getLogger(__name__)

    api_key = settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY
    if not api_key:
        yield _sse_event("error", {"step": "init", "message": "OPENROUTER_API_KEY not set"})
        return

    pdf_text = _extract_text(filename, content)
    _er = existing_records or {}

    initial_state: FPIState = {
        "pdf_text": pdf_text,
        "model_extract": model_extract or None,
        "model_plan": model_plan or None,
        "model_sql": model_sql or None,
        "model_reconcile": model_reconcile or None,
        "keywords": None,
        "sql_plan": None,
        "sql_result": None,
        "existing_organizations": _er.get("existing_organizations"),
        "existing_regions": _er.get("existing_regions"),
        "existing_policies": _er.get("existing_policies"),
        "reconciliation": None,
        "extract_tokens": None,
        "reconcile_tokens": None,
        "plan_tokens": None,
        "sql_tokens": None,
        "extract_duration_ms": None,
        "reconcile_duration_ms": None,
        "plan_duration_ms": None,
        "sql_duration_ms": None,
        "error": None,
    }

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def _run_stream_to_queue():
        try:
            for chunk in _graph.stream(initial_state):
                asyncio.run_coroutine_threadsafe(queue.put(chunk), loop)
        except Exception as exc:
            asyncio.run_coroutine_threadsafe(queue.put(exc), loop)
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)  # sentinel

    # Emit initial step_start
    yield _sse_event("step_start", {"step": "extract", "message": "Extracting keywords from policy document..."})

    # Start graph streaming in background thread
    loop.run_in_executor(None, _run_stream_to_queue)

    # Accumulate token data for analysis log saving
    _log_entries = []

    while True:
        item = await queue.get()
        if item is None:
            break  # sentinel — stream finished
        if isinstance(item, Exception):
            yield _sse_event("error", {"step": "graph", "message": str(item)})
            return

        # item is a chunk dict like {"node_extract": {updated_keys}}
        for node_name, state_update in item.items():
            if state_update.get("error"):
                yield _sse_event("error", {"step": node_name, "message": state_update["error"]})
                return

            if node_name == "node_extract":
                kw = state_update["keywords"]
                et = state_update.get("extract_tokens") or {}
                token_data = {
                    "extract_prompt": et.get("prompt", 0),
                    "extract_completion": et.get("completion", 0),
                    "extract_total": et.get("total", 0),
                    "extract_duration_ms": state_update.get("extract_duration_ms", 0),
                    "extract_cache_read": et.get("cache_read", 0),
                    "extract_cache_creation": et.get("cache_creation", 0),
                }
                yield _sse_event("extract", {
                    "keywords": kw.model_dump(),
                    "formatted_keywords": _format_keywords(kw),
                    "token_usage": token_data,
                })
                _log_entries.append(("extract", model_extract, et, state_update.get("extract_duration_ms", 0)))
                # Signal next step: reconciliation
                yield _sse_event("step_start", {"step": "reconcile", "message": "Reconciling entities with existing database..."})

            elif node_name == "node_reconcile":
                recon = state_update.get("reconciliation")
                rt = state_update.get("reconcile_tokens") or {}
                token_data = {
                    "reconcile_prompt": rt.get("prompt", 0),
                    "reconcile_completion": rt.get("completion", 0),
                    "reconcile_total": rt.get("total", 0),
                    "reconcile_duration_ms": state_update.get("reconcile_duration_ms", 0),
                    "reconcile_cache_read": rt.get("cache_read", 0),
                    "reconcile_cache_creation": rt.get("cache_creation", 0),
                }
                yield _sse_event("reconcile", {
                    "reconciliation": recon.model_dump() if recon else None,
                    "token_usage": token_data,
                })
                _log_entries.append(("reconcile", model_reconcile, rt, state_update.get("reconcile_duration_ms", 0)))
                # Signal next step: plan
                yield _sse_event("step_start", {"step": "plan", "message": "Building SQL ingestion plan..."})

            elif node_name == "node_plan":
                plan = state_update["sql_plan"]
                pt = state_update.get("plan_tokens") or {}
                token_data = {
                    "plan_prompt": pt.get("prompt", 0),
                    "plan_completion": pt.get("completion", 0),
                    "plan_total": pt.get("total", 0),
                    "plan_duration_ms": state_update.get("plan_duration_ms", 0),
                    "plan_cache_read": pt.get("cache_read", 0),
                    "plan_cache_creation": pt.get("cache_creation", 0),
                }
                yield _sse_event("plan", {
                    "sql_plan": plan.model_dump(),
                    "formatted_plan": _format_plan(plan),
                    "token_usage": token_data,
                })
                _log_entries.append(("plan", model_plan, pt, state_update.get("plan_duration_ms", 0)))
                if model_sql:
                    yield _sse_event("step_start", {"step": "sql", "message": "Generating SQL statements..."})

            elif node_name == "node_generate_sql":
                sql = state_update["sql_result"]
                st = state_update.get("sql_tokens") or {}
                token_data = {
                    "sql_prompt": st.get("prompt", 0),
                    "sql_completion": st.get("completion", 0),
                    "sql_total": st.get("total", 0),
                    "sql_duration_ms": state_update.get("sql_duration_ms", 0),
                    "sql_cache_read": st.get("cache_read", 0),
                    "sql_cache_creation": st.get("cache_creation", 0),
                }
                yield _sse_event("sql", {
                    "sql_result": sql.model_dump(),
                    "formatted_sql": sql.sql_query if sql else "",
                    "token_usage": token_data,
                })
                _log_entries.append(("sql", model_sql, st, state_update.get("sql_duration_ms", 0)))

    # Save analysis logs to analytics DB (always PG) before done event
    _log_db = analytics_db or db
    if _log_db and _log_entries:
        try:
            from app import models
            _default = default_model or settings.LLM_MODEL or "google/gemini-3-flash-preview"
            for step, model_override, tokens, duration in _log_entries:
                _log_db.add(models.AnalysisLog(
                    filename=filename,
                    step=step,
                    llm_model=model_override or _default,
                    prompt_tokens=tokens.get("prompt", 0),
                    completion_tokens=tokens.get("completion", 0),
                    total_tokens=tokens.get("total", 0),
                    duration_ms=duration,
                    cache_read_tokens=tokens.get("cache_read", 0),
                    cache_creation_tokens=tokens.get("cache_creation", 0),
                ))
            _log_db.commit()
        except Exception:
            log.warning("Failed to save analysis logs", exc_info=True)
            _log_db.rollback()

    yield _sse_event("done", {"filename": filename})
