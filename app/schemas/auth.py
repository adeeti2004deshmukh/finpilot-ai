from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator, model_validator

from app.schemas.profiles import FinancialProfileCreate
from app.schemas.goals import GoalCreate


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class RegisterRequest(LoginRequest):
    name: str = Field(min_length=1, max_length=120)
    confirm_password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Enter your full name")
        return value.strip()

    @model_validator(mode="after")
    def validate_password(self):
        password = self.password.get_secret_value()
        if len(password) < 12 or not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
            raise ValueError("Use at least 12 characters including letters and numbers")
        if password != self.confirm_password.get_secret_value():
            raise ValueError("Passwords do not match")
        return self


class AuthUserResponse(BaseModel):
    id: int
    name: str
    email: str
    age: int | None
    is_demo: bool
    onboarding_completed: bool

    model_config = {"from_attributes": True}


class OnboardingRequest(FinancialProfileCreate):
    name: str = Field(min_length=1, max_length=120)
    age: int | None = Field(default=None, ge=18, le=100)
    typical_essential_expenses: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    first_goal: GoalCreate | None = None

    @model_validator(mode="after")
    def valid_balances(self):
        if self.emergency_savings > self.current_savings:
            raise ValueError("Emergency savings must be included in current savings")
        if not self.name.strip():
            raise ValueError("Enter your name")
        return self
