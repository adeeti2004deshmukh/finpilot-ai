from decimal import Decimal

from app.schemas.planning import MonthlyActionPlanResponse
from app.services.investment_allocation_service import build_investment_plan
from app.services.planning_context import PlanningContext


def build_monthly_action_plan(context: PlanningContext) -> MonthlyActionPlanResponse:
    plan = build_investment_plan(context)
    positive_surplus = max(Decimal("0"), context.summary.monthly_surplus)
    existing_commitment = min(
        positive_surplus,
        max(context.actual_monthly_savings, sum((goal.monthly_contribution for goal in context.goals), Decimal("0"))),
    )
    lines = plan.funding_ledger
    allocation_total = sum((line.amount for line in lines), Decimal("0")).quantize(Decimal("0.01"))
    available_for_suggestions = max(Decimal("0"), positive_surplus - existing_commitment)
    if allocation_total - existing_commitment > available_for_suggestions:
        raise ValueError("Suggested monthly allocations exceed cash available after existing commitments")

    expenses = context.summary.monthly_expenses
    total_commitment = expenses + allocation_total
    warnings = list(plan.warnings)
    if total_commitment > context.summary.monthly_income:
        warnings.append("Recorded expenses and current commitments exceed income; no additional allocation is suggested beyond available cash.")
    return MonthlyActionPlanResponse(
        user_id=context.user_id,
        month=context.cash_flow["period"],
        monthly_income=context.summary.monthly_income,
        essential_expenses=context.cash_flow["essential_expenses"],
        discretionary_expenses=context.cash_flow["discretionary_expenses"],
        debt_obligations=context.profile.monthly_debt_payment,
        monthly_savings=context.actual_monthly_savings,
        monthly_surplus=context.summary.monthly_surplus,
        safety_buffer=plan.safety_buffer,
        allocations=lines,
        allocation_total=allocation_total,
        remaining_unallocated=max(Decimal("0"), context.summary.monthly_income - total_commitment).quantize(Decimal("0.01")),
        total_income_commitment=total_commitment.quantize(Decimal("0.01")),
        income_limit=context.summary.monthly_income,
        warnings=warnings,
    )
