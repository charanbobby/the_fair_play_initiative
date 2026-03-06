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

    @property
    def IS_PLAYGROUND(self) -> bool:
        """Playground mode when using SQLite (default). Production uses PostgreSQL."""
        return self.DATABASE_URL.startswith("sqlite")

    # Server
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "7860"))

    # Observability (Arize Phoenix) — optional; no-op if absent
    ARIZE_API_KEY: str = os.getenv("ARIZE_API_KEY", "")
    ARIZE_SPACE_ID: str = os.getenv("ARIZE_SPACE_ID", "")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")


settings = Settings()
