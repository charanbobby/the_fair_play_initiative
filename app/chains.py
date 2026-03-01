"""
app/chains.py
-------------
LangChain chain construction for the chatbot.

Current implementation: minimal chain = system prompt + history + user message.

TODO – Planned evolution:
    [ ] LangGraph orchestration: replace linear chain with stateful graph agent
    [ ] Tool calling: bind tools (search, calculator) to the LLM node
    [ ] Retrieval Augmented Generation (RAG): add a retriever node before the LLM
    [ ] Attendance policy parsing: ingest policy PDF via langchain-community loaders
    [ ] Point scoring engine: compute point totals and flag thresholds
    [ ] Multi-agent: separate scoring agent + chat agent orchestrated by LangGraph
"""

from __future__ import annotations
from typing import Any

from app import logging as app_logging

logger = app_logging.logger

# System prompt for the Fair Play Initiative chatbot
SYSTEM_PROMPT = (
    "You are a helpful assistant for the Fair Play Initiative, "
    "a student-athlete attendance tracking and advocacy program. "
    "Answer questions clearly and concisely. "
    "If you don't know the answer, say so honestly."
)


def build_messages(
    history: list[dict[str, str]],
    user_message: str,
) -> list[dict[str, str]]:
    """
    Assemble the message list for the LLM.

    Format:
        [system] → [human/ai history messages] → [current human message]
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    for entry in history:
        role = entry.get("role", "human")
        content = entry.get("content", "")
        # LangChain uses "human" / "ai"; some providers want "user" / "assistant"
        messages.append({"role": role, "content": content})

    messages.append({"role": "human", "content": user_message})
    return messages


def run_chain(
    llm: Any,
    history: list[dict[str, str]],
    user_message: str,
    trace_id: str,
) -> str:
    """
    Execute the chain and return the assistant reply string.

    For the MockLLM this is synchronous.  Real LangChain LLMs with .invoke()
    are also called synchronously here; async support is a future TODO.

    TODO: wire LangGraph graph.stream() here for streaming replies.
    TODO: add retriever.get_relevant_documents() call before invoke() for RAG.
    """
    messages = build_messages(history, user_message)
    logger.info(f"chain=invoke trace_id={trace_id} history_len={len(history)}")

    result = llm.invoke(messages)

    # LangChain real LLMs return an AIMessage object; MockLLM returns a string
    if isinstance(result, str):
        return result
    # AIMessage or BaseMessage
    if hasattr(result, "content"):
        return str(result.content)
    return str(result)
