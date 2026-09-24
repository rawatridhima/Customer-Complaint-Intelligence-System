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
    CONFIDENCE_THRESHOLD: float = 0.75

    LLM_API_KEY: SecretStr = SecretStr("")
    LLM_MODEL: str = ""
    LLM_TIMEOUT_SECONDS: int = 30
    PROMPT_VERSION: str = "v1"

    PRIORITY_W_SENTIMENT: float = 0.40
    PRIORITY_W_CATEGORY: float = 0.25
    PRIORITY_W_URGENCY: float = 0.20
    PRIORITY_W_REPEAT: float = 0.15

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
