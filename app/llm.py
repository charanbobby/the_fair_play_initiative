"""
app/llm.py
----------
LLM provider abstraction.

All provider initialisation is gated behind get_llm() so missing
API keys cause a graceful failure only when an LLM endpoint is actually
invoked, not at server startup.

Supported LLM_PROVIDER values:
    mock        – deterministic stub, no credentials required (default)
    openai      – LangChain ChatOpenAI (requires OPENAI_API_KEY or LLM_API_KEY)
    anthropic   – LangChain ChatAnthropic (requires ANTHROPIC_API_KEY or LLM_API_KEY)
"""

from __future__ import annotations
from typing import Any

from app.config import settings
from app import logging as app_logging

logger = app_logging.logger


# ---------------------------------------------------------------------------
# Mock provider (always available, no credentials required)
# ---------------------------------------------------------------------------

class MockLLM:
    """Deterministic echo LLM for testing and development."""

    def invoke(self, messages: list[dict[str, str]]) -> str:
        # Extract the last human message and echo it
        for msg in reversed(messages):
            if msg.get("role") == "human":
                return f"MOCK_REPLY: {msg['content']}"
        return "MOCK_REPLY: (no message)"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_llm() -> Any:
    """
    Return an LLM instance based on the LLM_PROVIDER setting.

    Returns a MockLLM when provider == 'mock' or when required credentials
    are missing.  Real providers are wrapped so errors surface only on call.
    """
    provider = settings.LLM_PROVIDER.lower()

    if provider == "mock":
        logger.info("llm=mock")
        return MockLLM()

    if provider == "openai":
        api_key = settings.LLM_API_KEY or settings.OPENAI_API_KEY
        if not api_key:
            logger.warning("llm=openai api_key=missing falling_back=mock")
            return MockLLM()
        try:
            from langchain_openai import ChatOpenAI  # type: ignore
            model = settings.LLM_MODEL or "gpt-4o-mini"
            logger.info(f"llm=openai model={model}")
            return ChatOpenAI(model=model, api_key=api_key)
        except ImportError:
            logger.warning("llm=openai langchain_openai=not_installed falling_back=mock")
            return MockLLM()

    if provider == "anthropic":
        api_key = settings.LLM_API_KEY or settings.ANTHROPIC_API_KEY
        if not api_key:
            logger.warning("llm=anthropic api_key=missing falling_back=mock")
            return MockLLM()
        try:
            from langchain_anthropic import ChatAnthropic  # type: ignore
            model = settings.LLM_MODEL or "claude-3-haiku-20240307"
            logger.info(f"llm=anthropic model={model}")
            return ChatAnthropic(model=model, api_key=api_key)
        except ImportError:
            logger.warning("llm=anthropic langchain_anthropic=not_installed falling_back=mock")
            return MockLLM()

    logger.warning(f"llm=unknown provider={provider!r} falling_back=mock")
    return MockLLM()
