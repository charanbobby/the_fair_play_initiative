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
import json
from pathlib import Path
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.schemas import KeywordExtraction, PolicyAnalysisResponse, SQLQueryPlan

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

def _build_model() -> ChatOpenAI:
    api_key = settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY
    model_name = settings.LLM_MODEL or "gpt-4o-mini"
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
    keywords: KeywordExtraction | None
    sql_plan: SQLQueryPlan | None
    error: str | None


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def node_extract(state: FPIState) -> dict:
    """Categorise policy keywords into schema-mapped groups."""
    model = _build_model().with_structured_output(KeywordExtraction)
    result = model.invoke([
        SystemMessage(content=_KEYWORD_SYSTEM_MSG),
        HumanMessage(content=state["pdf_text"][:4000]),
    ])
    return {"keywords": result}


def node_plan(state: FPIState) -> dict:
    """Devise a structured INSERT/UPSERT plan from extracted keywords."""
    if not state.get("keywords"):
        return {"error": "node_plan: no keywords in state"}

    model = _build_model().with_structured_output(SQLQueryPlan)
    human_msg = (
        "Devise an ingestion plan for the following keywords extracted from the "
        "attendance policy document. The plan must describe how to INSERT this "
        "policy's data into the FPI configuration tables. Do NOT write SQL.\n\n"
        f"## Extracted Keywords\n\n{_format_keywords(state['keywords'])}\n\n"
        f"## Policy Document (for context)\n\n{state['pdf_text'][:2000]}"
    )
    result = model.invoke([
        SystemMessage(content=_PLAN_SYSTEM_MSG),
        HumanMessage(content=human_msg),
    ])
    return {"sql_plan": result}


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

def _format_keywords(kw: KeywordExtraction) -> str:
    lines: list[str] = []
    fields = [
        ("policy", kw.policy),
        ("organization", kw.organization),
        ("region", kw.region),
        ("rule", kw.rule),
        ("attendance_log", kw.attendance_log),
        ("point_history", kw.point_history),
        ("alert", kw.alert),
        ("other_relevant_terms", kw.other_relevant_terms),
    ]
    for label, terms in fields:
        if terms:
            lines.append(f"{label}: {', '.join(terms)}")
    lines.append(f"confidence_score: {kw.confidence_score}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def analyze_policy_document(filename: str, content: bytes) -> PolicyAnalysisResponse:
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
        "keywords": None,
        "sql_plan": None,
        "error": None,
    }

    # LangGraph invoke is synchronous; run in a thread to stay async-friendly
    import asyncio
    final_state: FPIState = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _graph.invoke(initial_state)
    )

    if final_state.get("error"):
        raise RuntimeError(final_state["error"])

    return PolicyAnalysisResponse(
        filename=filename,
        keywords=final_state["keywords"],
        sql_plan=final_state["sql_plan"],
    )
