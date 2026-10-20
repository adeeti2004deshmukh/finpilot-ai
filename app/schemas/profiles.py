from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.models.enums import RiskTolerance
from app.schemas.base import ORMModel

EmergencyMonths = int


class FinancialProfileCreate(ORMModel):
    user_id: int | None = Field(default=None, gt=0)
    monthly_income: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    other_income: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    current_savings: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    typical_essential_expenses: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    emergency_savings: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    monthly_debt_payment: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    total_debt: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    dependents: int = Field(default=0, ge=0, le=30)
    risk_tolerance: RiskTolerance
    emergency_fund_target_months: EmergencyMonths = Field(default=6, ge=1, le=24)


class FinancialProfileUpdate(ORMModel):
    monthly_income: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    other_income: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    current_savings: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    typical_essential_expenses: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    emergency_savings: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    monthly_debt_payment: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    total_debt: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    dependents: int | None = Field(default=None, ge=0, le=30)
    risk_tolerance: RiskTolerance | None = None
    emergency_fund_target_months: EmergencyMonths | None = Field(default=None, ge=1, le=24)


class FinancialProfileResponse(FinancialProfileCreate):
    id: int
    created_at: datetime
    updated_at: datetime
