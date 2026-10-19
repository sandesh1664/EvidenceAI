from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore", hide_input_in_errors=True)

    app_name: str = Field(default="EvidenceAI API", min_length=1)
    app_env: Literal["development", "test", "staging", "production"] = "development"
    database_url: SecretStr

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
