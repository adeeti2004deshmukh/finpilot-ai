from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import ORMModel


class BudgetCreate(ORMModel):
    user_id: int | None = Field(default=None, gt=0)
    category_id: int = Field(gt=0)
    monthly_limit: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2200)


class BudgetUpdate(ORMModel):
    category_id: int | None = Field(default=None, gt=0)
    monthly_limit: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=2000, le=2200)


class BudgetResponse(ORMModel):
    id: int
    user_id: int
    category_id: int
    monthly_limit: Decimal
    month: int
    year: int
    created_at: datetime
    updated_at: datetime


class BudgetStatusResponse(ORMModel):
    budget_id: int
    category_id: int
    category: str
    monthly_limit: Decimal
    amount_spent: Decimal
    remaining_budget: Decimal
    percentage_used: Decimal
    status: str