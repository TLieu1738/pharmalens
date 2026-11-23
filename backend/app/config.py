"""Application configuration loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PharmaLens"
    environment: Literal["development", "test", "production"] = "development"

    anthropic_api_key: SecretStr | None = None
    # Model ID is configuration-only (ANTHROPIC_MODEL); there is deliberately no hardcoded default.
    anthropic_model: str | None = None

    supabase_url: str | None = None
    supabase_anon_key: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None

    frontend_url: str = "http://localhost:5173"
    # Extra comma-separated origins (e.g. Vercel preview URLs). Never "*" in production.
    additional_cors_origins: str = ""

    ncbi_api_key: SecretStr | None = None
    # Optional free key from openalex.org/settings/api; without one OpenAlex shares a small daily budget per IP.
    openalex_api_key: SecretStr | None = None
    # Allow signed-out users to run research (sessions are unlisted, reachable only by their UUID).
    demo_mode: bool = True
    anon_sessions_per_hour: int = Field(default=6, ge=0)
    max_concurrent_research: int = Field(default=3, ge=1)
    # Durable job queue (research sessions double as job records; see services/research_service.py)
    run_worker_in_api: bool = True  # false when a separate `python -m app.worker` process runs jobs
    job_lease_seconds: int = Field(default=90, ge=10, le=600)
    job_max_attempts: int = Field(default=2, ge=1, le=5)
    job_poll_seconds: float = Field(default=2.0, gt=0, le=60)
    # Second LLM pass that checks each cited record supports its claim (adds roughly 15-30 s per run).
    semantic_claim_verification: bool = True

    http_timeout_seconds: float = Field(default=20.0, gt=0, le=120)

    @field_validator("anthropic_model", mode="before")
    @classmethod
    def _blank_model_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "anthropic_api_key",
        "supabase_anon_key",
        "supabase_service_role_key",
        "ncbi_api_key",
        "openalex_api_key",
        mode="before",
    )
    @classmethod
    def _blank_secret_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def cors_origins(self) -> list[str]:
        origins = [self.frontend_url.strip().rstrip("/")]
        origins += [o.strip().rstrip("/") for o in self.additional_cors_origins.split(",") if o.strip()]
        return [o for o in dict.fromkeys(origins) if o != "*"]

    @property
    def anthropic_configured(self) -> bool:
        return self.anthropic_api_key is not None and self.anthropic_model is not None

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url) and self.supabase_service_role_key is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
