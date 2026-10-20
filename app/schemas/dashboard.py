from datetime import date
from decimal import Decimal

from app.schemas.base import ORMModel
from app.schemas.goals import GoalResponse


class EmergencyFundSummary(ORMModel):
    current_amount: Decimal
    target_amount: Decimal
    remaining_amount: Decimal
    coverage_percentage: Decimal


class CategoryAmount(ORMModel):
    category_id: int | None
    category: str
    amount: Decimal


class MonthlyAmount(ORMModel):
    month: date
    income: Decimal
    expenses: Decimal


class MonthlySavingsAmount(ORMModel):
    month: date
    savings: Decimal


class DashboardResponse(ORMModel):
    user_id: int
    month: date
    monthly_income: Decimal
    monthly_expenses: Decimal
    monthly_expenses_excluding_debt: Decimal
    monthly_debt_payment: Decimal
    monthly_savings: Decimal
    savings_rate: Decimal
    monthly_surplus: Decimal
    investable_surplus: Decimal
    financial_health_score: int
    emergency_fund: EmergencyFundSummary
    expense_by_category: list[CategoryAmount]
    income_vs_expenses: list[MonthlyAmount]
    monthly_savings_trend: list[MonthlySavingsAmount]
    top_spending_categories: list[CategoryAmount]
    goals: list[GoalResponse]


class InvestableSurplusResponse(ORMModel):
    user_id: int
    monthly_income: Decimal
    monthly_expenses: Decimal
    monthly_savings: Decimal
    monthly_surplus: Decimal
    monthly_debt_payment: Decimal
    safety_buffer: Decimal
    emergency_fund_gap: Decimal
    emergency_fund_monthly_reserve: Decimal
    monthly_goal_contributions: Decimal
    calculated_investable_surplus: Decimal
    available_investable_surplus: Decimal
    explanation: list[str]