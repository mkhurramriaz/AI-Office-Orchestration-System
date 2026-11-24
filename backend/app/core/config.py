import json
from functools import lru_cache
from typing import Annotated, Any
from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors_origins(v: Any) -> list[str]:
    """Parse CORS origins whether supplied as list, JSON string, or comma-separated string."""
    if isinstance(v, str):
        v = v.strip()
        if not v:
            return []
        if v.startswith("[") and v.endswith("]"):
            try:
                return json.loads(v)
            except Exception:
                pass
        return [origin.strip() for origin in v.split(",") if origin.strip()]
    elif isinstance(v, list):
        return [str(item).strip() for item in v]
    return []


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # General App Settings
    PROJECT_NAME: str = "TaskFlow AI"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Security & JWT
    SECRET_KEY: str = Field(
        default="taskflow-insecure-secret-key-change-in-production-for-jwt-tokens-0987654321",
        description="Secret key for JWT token generation and validation",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database Configuration (PostgreSQL by default; supports SQLite async fallback for tests)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/taskflow_ai"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/taskflow_ai"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 1800  # 30 minutes
    DB_ECHO: bool = False

    # CORS
    BACKEND_CORS_ORIGINS: Annotated[list[str], BeforeValidator(parse_cors_origins)] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    # ChromaDB & Document Storage
    CHROMA_PERSIST_DIRECTORY: str = "./Data/chroma_db"
    DOCUMENTS_DIRECTORY: str = "./Data/documents"

    # AI Model Providers
    DEFAULT_LLM_PROVIDER: str = "groq"
    DEFAULT_LLM_MODEL: str = "openai/gpt-oss-20b"
    GROQ_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return cached instance of application settings."""
    return Settings()


settings = get_settings()
