from decimal import Decimal

from app.financial_engine import FinancialProfile

DEMO_PROFILE_NAME = "Aarav Mehta"
DEMO_CITY = "Pune"
DEMO_AGE = 27
DEMO_CURRENCY = "INR"

DEMO_PROFILE = FinancialProfile(
    monthly_take_home_income=Decimal("95000"),
    monthly_other_income=Decimal("5000"),
    essential_expenses=Decimal("30000"),
    discretionary_expenses=Decimal("15000"),
    debt_payments=Decimal("8000"),
    monthly_savings=Decimal("12000"),
    current_emergency_fund=Decimal("180000"),
    emergency_fund_target_months=6,
)