from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, model_validator, field_validator
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    app_name: str = "Personal Finance API"
    app_env: Literal["development", "test", "production"] = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    database_url: str = Field(default="sqlite:///./finpilot_dev.db", repr=False)
    frontend_url: str = "http://localhost:3000"
    backend_url: str = ""
    session_cookie_name: str = "finpilot_session"
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    max_request_bytes: int = Field(default=65536, ge=4096, le=1048576)
    session_ttl_seconds: int = Field(default=86400, ge=300, le=604800)
    safety_buffer_rate: Decimal = Field(default=Decimal("0.08"), ge=0, le=1)
    safety_buffer_minimum: Decimal = Field(default=Decimal("5000"), ge=0)
    openai_api_key: SecretStr = SecretStr("")
    ai_provider: Literal["demo", "openai"] = "demo"
    openai_model: str = "gpt-6-sol"
    ai_timeout_seconds: float = Field(default=30, ge=1, le=60)
    ai_max_output_tokens: int = Field(default=1800, ge=256, le=4000)
    ai_max_tool_rounds: int = Field(default=4, ge=1, le=6)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True)

    @field_validator("database_url")
    @classmethod
    def normalize_database(cls, value):
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                value = "postgresql+psycopg://" + value[len(prefix):]
        try:
            url = make_url(value)
            if url.drivername not in {"sqlite", "postgresql+psycopg"}:
                raise ValueError()
        except Exception:
            raise ValueError("DATABASE_URL must use SQLite or PostgreSQL with psycopg") from None
        return value

    @field_validator("frontend_url", "backend_url")
    @classmethod
    def validate_origin(cls, value):
        if not value:
            return value
        value = value.rstrip("/")
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or "*" in value or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError("Use a single HTTP(S) origin without paths, credentials or wildcards")
        return value

    @model_validator(mode="after")
    def validate_production_cors(self) -> "Settings":
        if not self.frontend_url:
            raise ValueError("FRONTEND_URL is required")
        if self.app_env.lower() == "production":
            url = make_url(self.database_url)
            if url.drivername != "postgresql+psycopg" or not url.host or not url.database:
                raise ValueError("Production requires a managed PostgreSQL DATABASE_URL")
            if not self.frontend_url.startswith("https://") or (self.backend_url and not self.backend_url.startswith("https://")):
                raise ValueError("Production frontend/backend origins must use HTTPS")
        elif self.session_cookie_samesite == "none":
            raise ValueError("SameSite=None requires production HTTPS; use lax for local HTTP")
        return self


settings = Settings()
