from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.schemas.base import ORMModel


class ContributionSimulationRequest(ORMModel):
    monthly_contribution: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    annual_rate_percent: Decimal = Field(ge=0, le=100, max_digits=7, decimal_places=4)
    months: int = Field(ge=1, le=1200)


class FixedDepositSimulationRequest(ORMModel):
    principal: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    annual_rate_percent: Decimal = Field(ge=0, le=100, max_digits=7, decimal_places=4)
    months: int = Field(ge=1, le=1200)
    compounds_per_year: Literal[1, 2, 4, 12] = 4


class CompoundGrowthRequest(ORMModel):
    principal: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    annual_rate_percent: Decimal = Field(ge=0, le=100, max_digits=7, decimal_places=4)
    months: int = Field(ge=1, le=1200)


class SimulationResponse(ORMModel):
    invested_amount: Decimal
    estimated_interest: Decimal
    maturity_value: Decimal
    disclaimer: str | None = None