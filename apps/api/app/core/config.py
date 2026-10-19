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

    document_storage_root: Path = BACKEND_ROOT.parents[1] / "storage" / "documents"
    document_upload_max_bytes: int = Field(default=20 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
    document_chunk_size: int = Field(default=1600, ge=64, le=10000)
    document_chunk_overlap: int = Field(default=200, ge=0)
    document_max_chunks: int = Field(default=10000, ge=1, le=50000)
    document_max_pages: int = Field(default=500, ge=1, le=5000)
    document_max_text_chars: int = Field(default=2000000, ge=1, le=10000000)
    document_validation_timeout: int = Field(default=5, ge=1, le=30)
    document_processing_timeout: int = Field(default=30, ge=1, le=300)
    document_parser_memory_mb: int = Field(default=512, ge=128, le=2048)
    document_max_attempts: int = Field(default=3, ge=1, le=10)
    document_job_lease_seconds: int = Field(default=120, ge=30, le=3600)

    @model_validator(mode="after")
    def validate_document_limits(self):
        if self.document_chunk_overlap >= self.document_chunk_size:
            raise ValueError("Document overlap must be smaller than chunk size")
        if self.document_job_lease_seconds < self.document_processing_timeout + 15:
            raise ValueError("Document job lease must exceed processing timeout by at least 15 seconds")
        if not self.document_storage_root.is_absolute():
            raise ValueError("Document storage root must be absolute")
        root = self.document_storage_root.resolve()
        web = BACKEND_ROOT.parent / "web"
        if root == web or web in root.parents or root == Path("/"):
            raise ValueError("Document storage must be private and outside the frontend")
        return self

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
