"""
app/config.py
-------------
Central configuration: reads environment variables and provides
safe defaults so the application starts with no LLM credentials.
"""

import os
from dotenv import load_dotenv

# Load .env file if present (dev convenience; in Docker, vars are injected)
load_dotenv()


class Settings:
    # LLM provider selection — default to mock so no keys are required
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")

    # OpenAI / Anthropic keys (optional; only used when provider is set)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./fpi.db")

    # Analytics DB — always PostgreSQL so feedback/logs persist across sessions.
    # Falls back to DATABASE_URL if not set (works when DATABASE_URL is already PG).
    ANALYTICS_DATABASE_URL: str = os.getenv("ANALYTICS_DATABASE_URL", "")

    # Playground mode — set PLAYGROUND_MODE=true to enable the playground UI.
    # When not set, auto-detects from DATABASE_URL (sqlite = playground).
    _PLAYGROUND_MODE_RAW: str = os.getenv("PLAYGROUND_MODE", "auto")

    @property
    def IS_PLAYGROUND(self) -> bool:
        """Explicit PLAYGROUND_MODE env var wins; 'auto' falls back to SQLite detection."""
        val = self._PLAYGROUND_MODE_RAW.lower().strip()
        if val in ("true", "1", "yes"):
            return True
        if val in ("false", "0", "no"):
            return False
        # "auto" or any other value — derive from DB type
        return self.DATABASE_URL.startswith("sqlite")

    # Server
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "7860"))

    # Observability (Arize Phoenix) — optional; no-op if absent
    ARIZE_API_KEY: str = os.getenv("ARIZE_API_KEY", "")
    ARIZE_SPACE_ID: str = os.getenv("ARIZE_SPACE_ID", "")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")


settings = Settings()
