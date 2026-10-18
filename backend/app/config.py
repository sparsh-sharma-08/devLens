"""
DevLens AI — Backend Configuration
Loads and validates all environment variables using Pydantic Settings.
"""
from functools import lru_cache
from typing import Literal

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Environment ──────────────────────────────────────────────────────────
    environment: Literal["development", "production"] = "development"

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://devlens:devlens_secret@localhost:5432/devlens"

    # ── Redis / Celery ───────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── Auth ─────────────────────────────────────────────────────────────────
    github_client_id: str = ""
    github_client_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    jwt_secret_key: str = "change_me_to_a_long_random_string"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_provider: Literal["groq", "claude", "openai", "ollama"] = "groq"
    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.8-27b"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # ── Embeddings ───────────────────────────────────────────────────────────
    embedding_provider: Literal["local", "groq", "voyage"] = "local"
    embedding_model: str = "all-MiniLM-L6-v2"

    # ── Repository Processing ────────────────────────────────────────────────
    max_repo_size_mb: int = 500
    max_repo_loc: int = 500_000
    clone_workspace_dir: str = "/tmp/devlens_repos"

    # ── API ───────────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    # ── Observability ────────────────────────────────────────────────────────
    sentry_dsn: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
