from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, field_validator

from app.models.enums import GoalType
from app.schemas.base import ORMModel


class GoalCreate(ORMModel):
    user_id: int | None = Field(default=None, gt=0)
    name: str = Field(min_length=1, max_length=120)
    goal_type: GoalType
    target_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    current_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    target_date: date | None = None
    monthly_contribution: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    priority: int = Field(default=3, ge=1, le=5)

    @field_validator("target_date")
    @classmethod
    def validate_target_date(cls, value: date | None) -> date | None:
        if value is not None and value < date.today():
            raise ValueError("target_date cannot be in the past")
        return value


class GoalUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    goal_type: GoalType | None = None
    target_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    current_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    target_date: date | None = None
    monthly_contribution: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    priority: int | None = Field(default=None, ge=1, le=5)

    @field_validator("target_date")
    @classmethod
    def validate_target_date(cls, value: date | None) -> date | None:
        if value is not None and value < date.today():
            raise ValueError("target_date cannot be in the past")
        return value


class GoalResponse(ORMModel):
    id: int
    user_id: int
    name: str
    goal_type: GoalType
    target_amount: Decimal
    current_amount: Decimal
    target_date: date | None
    monthly_contribution: Decimal
    priority: int
    remaining_amount: Decimal
    progress_percentage: Decimal
    months_remaining: int | None
    required_monthly_contribution: Decimal
    created_at: datetime
    updated_at: datetime