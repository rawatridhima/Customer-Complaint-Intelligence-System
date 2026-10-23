from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://cis:cis_password@db:5432/cis"
    REDIS_URL: str = "redis://redis:6379/0"

    JWT_SECRET: SecretStr = SecretStr("dev-only-change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 480

    MODEL_DIR: Path = Path("/models")
    CONFIDENCE_THRESHOLD: float = 0.95

    # LLM (FR-19 to FR-25). Leave LLM_PROVIDER empty to run without an LLM:
    # every complaint then gets the template response and is flagged for
    # manual handling (FR-25). Providers:
    #   anthropic - Claude API
    #   openai    - any OpenAI-compatible API: OpenAI, Gemini, Groq, Ollama...
    #               (set LLM_BASE_URL for anything other than OpenAI itself)
    LLM_PROVIDER: str = ""
    LLM_API_KEY: SecretStr = SecretStr("")
    LLM_MODEL: str = ""
    LLM_BASE_URL: str = ""
    LLM_TIMEOUT_SECONDS: int = 20
    LLM_MAX_TOKENS: int = 700
    PROMPT_VERSION: str = "v2"
    # How many complaints the worker sends to the LLM per minute. Each one is
    # two requests, so "5/m" is 10 requests a minute, inside free-tier limits.
    # A batch of complaints then queues up instead of tripping HTTP 429.
    LLM_RATE_LIMIT: str = "5/m"

    PRIORITY_W_SENTIMENT: float = 0.40
    PRIORITY_W_CATEGORY: float = 0.25
    PRIORITY_W_URGENCY: float = 0.20
    PRIORITY_W_REPEAT: float = 0.15

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()