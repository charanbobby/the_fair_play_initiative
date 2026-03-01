"""
app/quotes.py
-------------
Quote drafting placeholder for the /quotes/draft endpoint.

Current implementation: deterministic stub — returns empty lists so the
endpoint is callable and the API contract is validated without real logic.

TODO – Planned evolution:
    [ ] LLM-based extraction: prompt the LLM to pull pull-quotes from input_text
    [ ] Style variants: formal / neutral / informal re-wording via separate prompts
    [ ] Citation tagging: attach source paragraph indices to each quote
    [ ] Batch mode: accept multiple passages in a single request
    [ ] Human review flag: add a confidence score and flag low-confidence items
"""

from __future__ import annotations
from typing import Any


def draft_quotes(input_text: str, style: str) -> dict[str, Any]:
    """
    Stub implementation of the quote drafting logic.

    Returns empty draft_quotes and a note explaining mock mode.
    Replace the body of this function when real LLM drafting is implemented.
    """
    # TODO: replace with LLM-based quote extraction
    # Example future call:
    #   llm = get_llm()
    #   quotes = extract_quotes_chain(llm, input_text, style)

    notes = [
        f"Quote drafting is a stub (style={style!r}). "
        "LLM extraction not yet implemented.",
    ]

    return {
        "draft_quotes": [],   # TODO: populate from LLM
        "notes": notes,
    }
