from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class FinancialProfileRequest(BaseModel):
    monthly_take_home_income: Decimal = Field(ge=0)
    monthly_other_income: Decimal = Field(default=Decimal("0"), ge=0)
    essential_expenses: Decimal = Field(ge=0)
    discretionary_expenses: Decimal = Field(ge=0)
    debt_payments: Decimal = Field(default=Decimal("0"), ge=0)
    monthly_savings: Decimal = Field(default=Decimal("0"), ge=0)
    current_emergency_fund: Decimal = Field(default=Decimal("0"), ge=0)
    emergency_fund_target_months: int = Field(default=6, ge=1, le=1200)


class FinancialSummaryResponse(BaseModel):
    monthly_income: Decimal
    monthly_expenses: Decimal
    monthly_savings: Decimal
    savings_rate_percent: Decimal
    monthly_surplus: Decimal
    emergency_fund_target: Decimal
    emergency_fund_gap: Decimal
    emergency_fund_coverage_percent: Decimal
    financial_health_score: int
    investable_surplus: Decimal


class DemoResponse(BaseModel):
    profile_name: str
    city: str
    age: int
    currency: str
    profile: FinancialProfileRequest
    summary: FinancialSummaryResponse


class ContributionSimulationRequest(BaseModel):
    monthly_contribution: Decimal = Field(ge=0)
    annual_rate_percent: Decimal = Field(ge=0)
    months: int = Field(ge=1, le=1200)


class FixedDepositSimulationRequest(BaseModel):
    principal: Decimal = Field(ge=0)
    annual_rate_percent: Decimal = Field(ge=0)
    months: int = Field(ge=1, le=1200)
    compounds_per_year: Literal[1, 2, 4, 12] = 4


class SimulationResponse(BaseModel):
    invested_amount: Decimal
    estimated_interest: Decimal
    maturity_value: Decimal