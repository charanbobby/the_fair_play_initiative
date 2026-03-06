"""
app/services/policy_analyzer.py
---------------------------------
LangGraph pipeline: PDF/DOCX/TXT → keyword extraction → SQL ingestion plan.

Nodes (steps 1 and 2 only — no SQL generation or DB writes):
    node_extract  — LLM extracts schema-mapped keywords from policy text
    node_plan     — LLM devises a structured INSERT plan from keywords

Graph:  START → node_extract → node_plan → END
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.schemas import KeywordExtraction, PolicyAnalysisResponse, SQLQueryPlan, TokenUsage

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

# ---------------------------------------------------------------------------
# LLM — ChatOpenAI pointed at OpenRouter
# ---------------------------------------------------------------------------

def _build_model(model_override: str | None = None) -> ChatOpenAI:
    api_key = settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY
    model_name = model_override or settings.LLM_MODEL or "gpt-4o-mini"
    return ChatOpenAI(
        model=model_name,
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        temperature=0,
    )


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------

class FPIState(TypedDict):
    pdf_text: str
    model_extract: str | None
    model_plan: str | None
    keywords: KeywordExtraction | None
    sql_plan: SQLQueryPlan | None
    extract_tokens: dict | None
    plan_tokens: dict | None
    error: str | None


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def _extract_token_usage(raw_msg) -> dict:
    """Pull token counts from an AIMessage's usage_metadata."""
    usage = getattr(raw_msg, "usage_metadata", None) or {}
    return {
        "prompt": usage.get("input_tokens", 0),
        "completion": usage.get("output_tokens", 0),
        "total": usage.get("total_tokens", 0),
    }


def node_extract(state: FPIState) -> dict:
    """Categorise policy keywords into schema-mapped groups."""
    model = _build_model(state.get("model_extract")).with_structured_output(
        KeywordExtraction, include_raw=True
    )
    raw_result = model.invoke([
        SystemMessage(content=_KEYWORD_SYSTEM_MSG),
        HumanMessage(content=state["pdf_text"]),
    ])
    result = raw_result["parsed"]
    tokens = _extract_token_usage(raw_result.get("raw"))
    # Post-process: enforce realistic confidence
    if result.confidence_score >= 1.0:
        result.confidence_score = 0.85
    result.confidence_score = round(min(result.confidence_score, 0.95), 2)
    return {"keywords": result, "extract_tokens": tokens}


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

    model = _build_model(state.get("model_plan")).with_structured_output(
        SQLQueryPlan, include_raw=True
    )
    human_msg = (
        "Devise an ingestion plan for the following keywords extracted from the "
        "attendance policy document. The plan must describe how to INSERT this "
        "policy's data into the FPI configuration tables. Do NOT write SQL.\n\n"
        f"## Extracted Keywords\n\n{_format_keywords(state['keywords'])}\n\n"
        f"## Policy Document (for context)\n\n{state['pdf_text']}"
    )
    raw_result = model.invoke([
        SystemMessage(content=_PLAN_SYSTEM_MSG),
        HumanMessage(content=human_msg),
    ])
    result = raw_result["parsed"]
    tokens = _extract_token_usage(raw_result.get("raw"))
    # Post-process: enforce realistic confidence scores
    has_placeholders = bool(
        result.cte_description and "placeholder" in result.cte_description.lower()
    )
    result.confidence_score = _adjust_confidence(result.confidence_score, has_placeholders)
    return {"sql_plan": result, "plan_tokens": tokens}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_graph() -> StateGraph:
    g = StateGraph(FPIState)
    g.add_node("node_extract", node_extract)
    g.add_node("node_plan", node_plan)
    g.add_edge(START, "node_extract")
    g.add_edge("node_extract", "node_plan")
    g.add_edge("node_plan", END)
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

    if plan.uses_cte:
        lines.append("CTE")
        lines.append(f"  {plan.cte_description or '(no description)'}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def analyze_policy_document(
    filename: str,
    content: bytes,
    model_extract: str | None = None,
    model_plan: str | None = None,
) -> PolicyAnalysisResponse:
    """
    Extract text from the uploaded file, run the LangGraph pipeline,
    and return keywords + SQL ingestion plan.

    Raises ValueError if the OPENROUTER_API_KEY is not configured.
    """
    api_key = settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY (or OPENAI_API_KEY) is not set. "
            "Policy analysis requires an LLM provider."
        )

    pdf_text = _extract_text(filename, content)

    initial_state: FPIState = {
        "pdf_text": pdf_text,
        "model_extract": model_extract or None,
        "model_plan": model_plan or None,
        "keywords": None,
        "sql_plan": None,
        "extract_tokens": None,
        "plan_tokens": None,
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
    et = final_state.get("extract_tokens") or {}
    pt = final_state.get("plan_tokens") or {}
    token_usage = TokenUsage(
        extract_prompt=et.get("prompt", 0),
        extract_completion=et.get("completion", 0),
        extract_total=et.get("total", 0),
        plan_prompt=pt.get("prompt", 0),
        plan_completion=pt.get("completion", 0),
        plan_total=pt.get("total", 0),
    )
    return PolicyAnalysisResponse(
        filename=filename,
        keywords=kw,
        sql_plan=plan,
        formatted_keywords=_format_keywords(kw) if kw else "",
        formatted_plan=_format_plan(plan) if plan else "",
        token_usage=token_usage,
    )
