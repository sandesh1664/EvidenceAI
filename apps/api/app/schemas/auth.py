from datetime import datetime
from uuid import UUID
from email_validator import validate_email, EmailNotValidError
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        try:
            # ASCII identities keep Python normalization identical to the DB index.
            normalized = validate_email(value.strip(), check_deliverability=False,
                                        allow_smtputf8=False).ascii_email
            if not normalized:
                raise ValueError()
            return normalized.lower()
        except (EmailNotValidError, ValueError):
            raise ValueError("Invalid email address") from None


class RegisterRequest(LoginRequest):
    password: SecretStr = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=200)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Display name is required")
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    display_name: str
    is_active: bool
    created_at: datetime


class RegistrationAccepted(BaseModel):
    detail: str = "Registration request accepted. Complete email verification before signing in. If delivery is unavailable, contact the administrator."


class VerifyRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    token: SecretStr = Field(min_length=43, max_length=43)
