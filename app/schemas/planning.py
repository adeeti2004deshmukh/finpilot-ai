from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.models.enums import RiskTolerance
from app.schemas.base import ORMModel

GoalHorizon = Literal["VERY_SHORT_TERM", "SHORT_TERM", "MEDIUM_TERM", "LONG_TERM", "UNSPECIFIED"]
FundingStatus = Literal["ON_TRACK", "SLIGHTLY_BEHIND", "AT_RISK", "NOT_FEASIBLE_WITH_CURRENT_SURPLUS", "NEEDS_TARGET_DATE"]
PriorityLevel = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
AffordabilityStatus = Literal["COMFORTABLE", "MANAGEABLE", "CAUTION", "HIGH_RISK"]
PaymentMethod = Literal["CASH", "EMI"]


class GoalAnalysisResponse(ORMModel):
    goal_id: int
    name: str
    goal_type: str
    goal_horizon: GoalHorizon
    remaining_months: int | None
    target_amount: Decimal
    current_amount: Decimal
    funding_gap: Decimal
    required_monthly_contribution: Decimal
    planned_monthly_contribution: Decimal
    funded_monthly_contribution: Decimal = Decimal("0")
    funding_status: FundingStatus


class FinancialPriorityResponse(ORMModel):
    priority_level: PriorityLevel
    purpose: str
    action: str
    reason_code: str
    reason: str
    related_goal_id: int | None = None


class InvestmentCategoryGuidance(ORMModel):
    name: str
    description: str
    risk_level: str
    liquidity: str
    typical_time_horizon: str
    return_type: str
    market_linked: bool
    capital_guarantee_explanation: str
    best_used_for: str
    advantages: list[str]
    limitations: list[str]
    relevance_score: int | None = None
    relevance_level: str | None = None
    relevance_reason: str | None = None


class InvestmentAllocationResponse(ORMModel):
    purpose: str
    amount: Decimal
    percentage: Decimal
    reason_code: str
    reason: str
    categories_to_explore: list[InvestmentCategoryGuidance]
    related_goal_id: int | None = None


class InvestmentPlanResponse(ORMModel):
    user_id: int
    currency: str
    monthly_income: Decimal
    monthly_expenses: Decimal
    monthly_debt_payment: Decimal
    actual_monthly_savings: Decimal
    monthly_surplus: Decimal
    cash_after_actual_savings: Decimal
    existing_goal_commitments: Decimal
    cash_after_existing_commitments: Decimal
    safety_buffer_target: Decimal
    safety_buffer: Decimal
    emergency_fund_current: Decimal
    emergency_fund_target: Decimal
    emergency_fund_gap: Decimal
    debt_repayment_reserve: Decimal
    short_term_goal_reserve: Decimal
    goal_contributions: Decimal
    emergency_fund_contribution: Decimal
    scheduled_goal_contributions: Decimal
    funded_existing_goal_contributions: Decimal
    savings_goal_overlap: Decimal
    allocation_total: Decimal
    funding_ledger: list["MonthlyPlanLine"]
    investable_surplus: Decimal
    unallocated_buffer: Decimal
    financial_priorities: list[FinancialPriorityResponse]
    allocations: list[InvestmentAllocationResponse]
    goal_analysis: list[GoalAnalysisResponse]
    warnings: list[str]
    methodology: list[str]


class MonthlyPlanLine(ORMModel):
    purpose: str
    amount: Decimal
    reason_code: str


class MonthlyActionPlanResponse(ORMModel):
    user_id: int
    month: date
    monthly_income: Decimal
    essential_expenses: Decimal
    discretionary_expenses: Decimal
    debt_obligations: Decimal
    monthly_savings: Decimal
    monthly_surplus: Decimal
    safety_buffer: Decimal
    allocations: list[MonthlyPlanLine]
    allocation_total: Decimal
    remaining_unallocated: Decimal
    total_income_commitment: Decimal
    income_limit: Decimal
    warnings: list[str]


class AffordabilityAnalyzeRequest(ORMModel):
    user_id: int | None = Field(default=None, gt=0)
    item_name: str = Field(min_length=1, max_length=120)
    price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    purchase_date: date
    payment_method: PaymentMethod
    down_payment: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    monthly_emi: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    tenure_months: int | None = Field(default=None, ge=1, le=600)

    @field_validator("purchase_date")
    @classmethod
    def purchase_date_not_in_past(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("purchase_date cannot be in the past")
        return value

    @model_validator(mode="after")
    def validate_payment(self):
        if self.payment_method == "EMI":
            if self.down_payment is None or self.monthly_emi is None or self.tenure_months is None:
                raise ValueError("EMI requires down_payment, monthly_emi, and tenure_months")
            if self.down_payment > self.price:
                raise ValueError("down_payment cannot exceed price")
            if self.down_payment == self.price:
                raise ValueError("down_payment must be less than price for EMI")
            if self.down_payment + self.monthly_emi * self.tenure_months < self.price:
                raise ValueError("EMI payments and down_payment must cover the price")
        elif any(value is not None for value in (self.down_payment, self.monthly_emi, self.tenure_months)):
            raise ValueError("CASH purchases cannot include EMI fields")
        return self


class AffordabilityScenario(ORMModel):
    name: str
    purchase_date: date
    required_monthly_saving: Decimal
    projected_emergency_fund: Decimal
    projected_goal_contribution: Decimal
    status: str
    available_monthly_saving: Decimal = Decimal("0")
    monthly_saving_shortfall: Decimal = Decimal("0")
    affordability_score: int = 0
    warnings: list[str] = Field(default_factory=list)


class AffordabilityAnalyzeResponse(ORMModel):
    user_id: int
    item_name: str
    price: Decimal
    payment_method: PaymentMethod
    affordability_score: int
    affordability_status: AffordabilityStatus
    cash_flow_impact: Decimal
    upfront_funding_shortfall: Decimal
    emergency_fund_before: Decimal
    emergency_fund_after: Decimal
    emergency_coverage_months_before: Decimal
    emergency_coverage_months_after: Decimal
    goal_impact: Decimal
    monthly_surplus_before: Decimal
    monthly_surplus_after: Decimal
    total_emi_commitment: Decimal
    debt_burden_before_percent: Decimal
    debt_burden_after_percent: Decimal
    score_components: dict[str, int]
    warnings: list[str]
    alternative_scenarios: list[AffordabilityScenario]
    methodology: list[str]


class CategoryRelevanceResponse(ORMModel):
    category: InvestmentCategoryGuidance


class GoalComparisonResponse(ORMModel):
    goal: GoalAnalysisResponse
    risk_tolerance: RiskTolerance
    liquidity_requirement: str
    categories_to_explore: list[InvestmentCategoryGuidance]
    methodology: str


WhatIfKind = Literal["INCOME_INCREASE", "RENT_INCREASE", "FOOD_SPENDING_REDUCTION", "SAVINGS_INCREASE", "GOAL_DELAY"]


class WhatIfRequest(ORMModel):
    scenario_type: WhatIfKind
    amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    goal_id: int | None = Field(default=None, gt=0)
    delay_months: int | None = Field(default=None, ge=1, le=120)
    category_ids: list[int] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_scenario(self):
        if any(category_id <= 0 for category_id in self.category_ids):
            raise ValueError("category_ids must contain positive IDs")
        if self.category_ids and self.scenario_type != "FOOD_SPENDING_REDUCTION":
            raise ValueError("category_ids applies only to spending reduction")
        if self.scenario_type == "GOAL_DELAY" and (self.goal_id is None or self.delay_months is None):
            raise ValueError("GOAL_DELAY requires goal_id and delay_months")
        if self.scenario_type != "GOAL_DELAY" and self.amount <= 0:
            raise ValueError("amount must be greater than zero for this scenario")
        return self


class WhatIfSnapshot(ORMModel):
    monthly_income: Decimal
    monthly_expenses: Decimal
    actual_monthly_savings: Decimal
    savings_rate: Decimal
    monthly_surplus: Decimal
    investable_surplus: Decimal
    emergency_fund_months: Decimal
    goal_feasibility: list[GoalAnalysisResponse]


class WhatIfResponse(ORMModel):
    user_id: int
    scenario_type: WhatIfKind
    current: WhatIfSnapshot
    projected: WhatIfSnapshot
    changes: dict[str, Decimal | int | str]
    warnings: list[str]


class HealthScoreComponent(ORMModel):
    name: str
    points: int
    maximum_points: int
    status: str
    reason: str


class FinancialHealthResponse(ORMModel):
    user_id: int
    score: int
    maximum_score: int = 100
    components: list[HealthScoreComponent]
    goal_progress_context: str
    strengths: list[str]
    areas_to_improve: list[str]
    deterministic_actions: list[str]


class FinancialInsight(ORMModel):
    type: str
    severity: str
    title: str
    metric: str
    current_value: Decimal | None
    comparison_value: Decimal | None
    reason_code: str
    message: str


class FinancialInsightsResponse(ORMModel):
    user_id: int
    insights: list[FinancialInsight]
    coverage_note: str = ""
