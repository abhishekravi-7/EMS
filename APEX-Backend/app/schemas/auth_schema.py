"""Request/response schemas for authentication endpoints (``/api/auth/*``).

Field names are camelCase over the wire (matching the frontend), same as
every other schema module in this package. These are the HTTP boundary
contracts — validation happens here, before any code touches the database.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, computed_field, field_validator, model_validator

# One regex per password rule reads far more clearly than a single giant
# pattern, and each gives its own error message when it fails.
_HAS_UPPERCASE = re.compile(r"[A-Z]")
_HAS_LOWERCASE = re.compile(r"[a-z]")
_HAS_DIGIT = re.compile(r"\d")
_HAS_SPECIAL_CHARACTER = re.compile(r"[^A-Za-z0-9]")


class SignupRequest(BaseModel):
    """Body for ``POST /api/auth/signup``."""

    full_name: Optional[str] = Field(default=None, alias="fullName", max_length=200)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., alias="confirmPassword", min_length=8, max_length=128)

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "email": "javaapex@example.com",
                "password": "StrongPassword@123",  # nosec B105
                "confirmPassword": "StrongPassword@123",  # nosec B105
            }
        },
    }

    @field_validator("full_name")
    @classmethod
    def _trim_full_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        # EmailStr already validated the format; this just trims/lowercases
        # it so "Pavithra@Example.com " and "pavithra@example.com" are the
        # same account.
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def _validate_password_strength(cls, value: str) -> str:
        if not _HAS_UPPERCASE.search(value):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not _HAS_LOWERCASE.search(value):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not _HAS_DIGIT.search(value):
            raise ValueError("Password must contain at least one number.")
        if not _HAS_SPECIAL_CHARACTER.search(value):
            raise ValueError("Password must contain at least one special character.")
        return value

    @model_validator(mode="after")
    def _passwords_must_match(self) -> "SignupRequest":
        # `model_validator(mode="after")` runs once all individual fields
        # have already passed their own validation — the right place for a
        # check that spans two fields, like a Bean Validation `@AssertTrue`
        # method in Java.
        if self.password != self.confirm_password:
            raise ValueError("Password and confirm password must match.")
        return self


class SignupResponse(BaseModel):
    """Response returned upon successful signup initiation (pending verification)."""

    email: str
    message: str

    model_config = {"populate_by_name": True}


class LoginRequest(BaseModel):
    """Body for ``POST /api/auth/login``."""

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {"email": "javaapex@example.com", "password": "StrongPassword@123"}  # nosec B105
        },
    }

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserResponse(BaseModel):
    """Safe, public view of a user. NEVER includes password_hash."""

    id: int | str
    full_name: str = Field(..., alias="fullName")
    email: str
    role: str
    is_active: bool = Field(..., alias="isActive")
    is_email_verified: bool = Field(..., alias="isEmailVerified")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")
    last_login_at: Optional[datetime] = Field(default=None, alias="lastLoginAt")

    @computed_field
    @property
    def userId(self) -> int | str:
        return self.id

    # `from_attributes=True` lets this schema read straight off object attributes
    # (`UserResponse.model_validate(user)`) or dictionaries.
    model_config = {"populate_by_name": True, "from_attributes": True}


class AuthResponse(BaseModel):
    """Success body for ``POST /api/auth/login``."""

    user: UserResponse
    message: str

    model_config = {"populate_by_name": True}


class MessageResponse(BaseModel):
    """Generic ``{ "message": "..." }`` body for refresh/logout."""

    message: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., alias="newPassword", min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _validate_password_strength(cls, value: str) -> str:
        if not _HAS_UPPERCASE.search(value):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not _HAS_LOWERCASE.search(value):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not _HAS_DIGIT.search(value):
            raise ValueError("Password must contain at least one number.")
        if not _HAS_SPECIAL_CHARACTER.search(value):
            raise ValueError("Password must contain at least one special character.")
        return value


class VerifyEmailCodeRequest(BaseModel):
    """Body for ``POST /api/auth/verify-email-code`` and ``POST /api/auth/verify-email``."""

    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.isdigit() or len(cleaned) != 6:
            raise ValueError("Verification code must be exactly 6 digits.")
        return cleaned


class VerifyEmailRequest(BaseModel):
    """Legacy or alternate body for email verification."""

    email: Optional[EmailStr] = None
    code: Optional[str] = None
    token: Optional[str] = None

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: Optional[str]) -> Optional[str]:
        return value.strip().lower() if value else None


class ResendVerificationRequest(BaseModel):
    """Body for ``POST /api/auth/resend-verification-code`` and ``POST /api/auth/resend-verification``."""

    email: EmailStr

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class GoogleAuthRequest(BaseModel):
    """Body for ``POST /api/auth/google``."""

    credential: str = Field(..., min_length=1, alias="credential")

    model_config = {"populate_by_name": True}
