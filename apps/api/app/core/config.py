from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore", hide_input_in_errors=True)

    app_name: str = Field(default="EvidenceAI API", min_length=1)
    app_env: Literal["development", "test", "staging", "production"] = "development"
    database_url: SecretStr

    session_ttl_seconds: int = Field(default=86400, ge=60, le=2592000)
    auth_allow_insecure_http: bool = False
    trusted_frontend_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    auth_rate_limit: int = Field(default=20, ge=1, le=10000)
    auth_rate_window_seconds: int = Field(default=300, ge=1, le=86400)

    @property
    def secure_cookies(self) -> bool:
        return not self.auth_allow_insecure_http

    @property
    def session_cookie_name(self) -> str:
        return "__Host-evidenceai_session" if self.secure_cookies else "evidenceai_session"

    @model_validator(mode="after")
    def validate_browser_security(self):
        from urllib.parse import urlsplit
        if self.auth_allow_insecure_http and self.app_env not in {"development", "test"}:
            raise ValueError("Insecure HTTP is only permitted in development/test")
        if not self.trusted_frontend_origins:
            raise ValueError("At least one explicit frontend origin is required")
        for origin in self.trusted_frontend_origins:
            url = urlsplit(origin)
            # Accessing port also validates malformed/out-of-range ports.
            _ = url.port
            if (url.scheme not in {"http", "https"} or not url.hostname or url.username
                    or url.password or url.path or url.query or url.fragment or "*" in origin
                    or "\\" in origin or any(char.isspace() for char in origin)):
                raise ValueError("Frontend origins must be explicit HTTP(S) origins without paths")
            if self.app_env in {"production", "staging"} and url.scheme != "https":
                raise ValueError("Production/staging origins require HTTPS")
        return self

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            if url.drivername not in {"postgresql", "postgresql+psycopg"} or not url.database or not url.host:
                raise ValueError()
        except Exception:
            raise ValueError("DATABASE_URL must be a PostgreSQL URL with host and database") from None
        return SecretStr(str(url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)))


@lru_cache
def get_settings() -> Settings:
    return Settings()
