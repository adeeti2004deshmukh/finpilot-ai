from datetime import date
from calendar import monthrange
from decimal import Decimal

from sqlalchemy.orm import Session

from app.schemas.planning import FinancialInsight, FinancialInsightsResponse
from app.services.finance import period_cash_flow
from app.services.investment_allocation_service import build_investment_plan
from app.services.planning_context import PlanningContext


def _previous_month(value: date) -> date:
    if value.month == 1:
        return date(value.year - 1, 12, 1)
    return date(value.year, value.month - 1, 1)


def build_financial_insights(db: Session, context: PlanningContext) -> FinancialInsightsResponse:
    previous_month = _previous_month(context.today)
    comparison_day = min(context.today.day, monthrange(previous_month.year, previous_month.month)[1])
    previous = period_cash_flow(db, context.profile, previous_month, through_day=comparison_day)
    current = period_cash_flow(db, context.profile, context.today, through_day=comparison_day)
    coverage_note = (
        f"Spending and savings trends compare days 1–{comparison_day} of {context.today:%Y-%m} and {previous_month:%Y-%m}; "
        "later-dated transactions are excluded from trends. Recorded data may be incomplete. Historical income uses the current profile's recurring income."
    )
    current_savings = current["savings"]
    previous_savings = previous["savings"]
    current_income = current["summary"].monthly_income
    previous_income = previous["summary"].monthly_income
    current_rate = current_savings / current_income * 100 if current_income > 0 else Decimal("0")
    previous_rate = previous_savings / previous_income * 100 if previous_income > 0 else Decimal("0")
    insights: list[FinancialInsight] = []

    for (category_id, category_name), amount in sorted(current["category_totals"].items(), key=lambda item: (item[0][1], item[0][0] or 0)):
        old_amount = previous["category_totals"].get((category_id, category_name), Decimal("0"))
        if old_amount > 0 and amount > old_amount * Decimal("1.10"):
            change = (amount - old_amount) / old_amount * 100
            insights.append(FinancialInsight(
                type="SPENDING_TREND", severity="WARNING", title=f"{category_name} spending increased",
                metric=f"{category_name} spending", current_value=amount, comparison_value=old_amount,
                reason_code="CATEGORY_SPENDING_INCREASED",
                message=f"{category_name} spending increased {change:.0f}% for the same first {comparison_day} days compared with last month.",
            ))
    if previous["transaction_count"] > 0 and previous_income > 0 and current_rate + Decimal("1") < previous_rate:
        insights.append(FinancialInsight(
            type="SAVINGS", severity="INFO", title="Savings rate decreased", metric="Savings rate",
            current_value=current_rate, comparison_value=previous_rate,
            reason_code="SAVINGS_RATE_DECREASED",
            message=f"Your recorded savings rate decreased from {previous_rate:.1f}% to {current_rate:.1f}%.",
        ))
    essential = max(context.cash_flow["essential_expenses"], context.profile.typical_essential_expenses)
    emergency_months = context.profile.emergency_savings / essential if essential > 0 else Decimal(context.profile.emergency_fund_target_months)
    insights.append(FinancialInsight(
        type="EMERGENCY_FUND", severity="WARNING" if emergency_months < context.profile.emergency_fund_target_months else "INFO",
        title="Emergency fund coverage", metric="Months covered", current_value=emergency_months.quantize(Decimal("0.1")),
        comparison_value=Decimal(context.profile.emergency_fund_target_months), reason_code="EMERGENCY_FUND_COVERAGE",
        message=f"Your emergency fund currently covers {emergency_months:.1f} months of essential expenses.",
    ))
    for analysis in build_investment_plan(context).goal_analysis:
        if analysis.funding_status in ("AT_RISK", "NOT_FEASIBLE_WITH_CURRENT_SURPLUS"):
            insights.append(FinancialInsight(
                type="GOAL", severity="WARNING", title=f"{analysis.name} needs attention",
                metric="Required monthly contribution", current_value=analysis.required_monthly_contribution,
                comparison_value=analysis.planned_monthly_contribution, reason_code="GOAL_BEHIND_SCHEDULE",
                message=f"{analysis.name} requires about ₹{analysis.required_monthly_contribution:,.0f}/month to meet its current target date.",
            ))
    plan = build_investment_plan(context)
    insights.append(FinancialInsight(
        type="INVESTABLE_SURPLUS", severity="INFO", title="Monthly allocation capacity",
        metric="Investable surplus", current_value=plan.investable_surplus, comparison_value=None,
        reason_code="POST_PRIORITY_INVESTABLE_SURPLUS",
        message=f"After current savings, safety buffer, debt, emergency-fund, and near-term goal priorities, ₹{plan.investable_surplus:,.0f} remains for longer-term allocation.",
    ))
    return FinancialInsightsResponse(user_id=context.user_id, insights=insights, coverage_note=coverage_note)
