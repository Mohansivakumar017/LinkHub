import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_development_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(environment="production")


def test_production_accepts_explicit_security_configuration() -> None:
    settings = Settings(
        environment="production",
        jwt_secret_key="a" * 64,
        postgres_dsn="postgresql+asyncpg://app:secret@db:5432/linkhub",
        cors_origins=["https://app.example.com"],
        public_base_url="https://app.example.com",
    )

    assert settings.environment == "production"


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(
            environment="production",
            jwt_secret_key="a" * 64,
            postgres_dsn="postgresql+asyncpg://app:secret@db:5432/linkhub",
            cors_origins=["*"],
            public_base_url="https://app.example.com",
        )


def test_production_rejects_localhost_cors() -> None:
    with pytest.raises(ValidationError, match="localhost"):
        Settings(
            environment="production",
            jwt_secret_key="a" * 64,
            postgres_dsn="postgresql+asyncpg://app:secret@db:5432/linkhub",
            cors_origins=["http://localhost:8080"],
            public_base_url="https://app.example.com",
        )
