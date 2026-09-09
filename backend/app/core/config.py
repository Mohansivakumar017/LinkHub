from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LinkHub"
    environment: Literal["local", "development", "staging", "production"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    public_base_url: str = "http://localhost:8000"

    postgres_dsn: str = Field(
        default="postgresql+asyncpg://linkhub:linkhub@db:5432/linkhub"
    )
    redis_dsn: str = Field(default="redis://redis:6379/0")
    redis_cache_enabled: bool = True
    redis_cache_ttl_seconds: int = 300
    celery_enabled: bool = False
    celery_email_enabled: bool = False
    celery_result_backend_enabled: bool = False
    rate_limit_enabled: bool = False
    rate_limit_capacity: int = Field(default=20, ge=1)
    rate_limit_refill_per_second: float = Field(default=1.0, gt=0)
    rate_limit_paths: str = (
        "/api/v1/auth/login,/api/v1/auth/refresh,/api/v1/auth/register,"
        "/api/v1/auth/forgot-password,/api/v1/auth/resend-verification,"
        "/api/v1/auth/reset-password,/api/v1/auth/verify-email"
    )
    cleanup_click_retention_days: int = 90
    cleanup_schedule_cron: str = "0 2 * * *"
    expiration_notification_days: int = Field(default=3, ge=1, le=30)
    weekly_report_schedule_cron: str = "0 8 * * 1"
    platform_admin_emails: str = ""
    readiness_timeout_seconds: float = 2.0
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "no-reply@localhost"
    smtp_use_tls: bool = True
    media_dir: str = "/app/media"
    media_base_url: str = "/media"

    jwt_secret_key: str = Field(
        default="dev-only-change-this-jwt-secret-key-32chars-min",
        min_length=32,
    )
    jwt_algorithm: str = "HS256"
    access_token_exp_minutes: int = 15
    refresh_token_exp_days: int = 30
    verify_email_token_exp_minutes: int = 60 * 24
    reset_password_token_exp_minutes: int = 30

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.environment != "production":
            return self
        if self.debug:
            raise ValueError("DEBUG must be false in production")
        if self.jwt_secret_key.startswith("dev-only-"):
            raise ValueError("JWT_SECRET_KEY must be replaced in production")
        if self.postgres_dsn.startswith("postgresql+asyncpg://linkhub:linkhub@"):
            raise ValueError("POSTGRES_DSN must be explicitly configured in production")
        if not self.public_base_url.startswith("https://"):
            raise ValueError("PUBLIC_BASE_URL must use HTTPS in production")
        if "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS cannot contain '*' in production")
        if any("localhost" in origin or "127.0.0.1" in origin for origin in self.cors_origins):
            raise ValueError("CORS_ORIGINS cannot target localhost in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
