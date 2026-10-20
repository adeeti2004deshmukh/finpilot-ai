from datetime import date
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from app.models.entities import Goal
from app.schemas.planning import FundingStatus, GoalAnalysisResponse, GoalHorizon


def months_until(target_date: date, today: date) -> int:
    months = (target_date.year - today.year) * 12 + target_date.month - today.month
    if target_date.day > today.day:
        months += 1
    return max(0, months)


def classify_horizon(months_remaining: int | None) -> GoalHorizon:
    if months_remaining is None:
        return "UNSPECIFIED"
    if months_remaining <= 12:
        return "VERY_SHORT_TERM"
    if months_remaining <= 36:
        return "SHORT_TERM"
    if months_remaining <= 60:
        return "MEDIUM_TERM"
    return "LONG_TERM"


def analyze_goal(
    goal: Goal,
    today: date,
    available_monthly_surplus: Decimal,
    planned_contribution: Decimal | None = None,
) -> GoalAnalysisResponse:
    remaining_months = months_until(goal.target_date, today) if goal.target_date else None
    gap = max(Decimal("0"), goal.target_amount - goal.current_amount)
    if remaining_months is None:
        required = Decimal("0")
    elif remaining_months > 0:
        required = gap / remaining_months
    else:
        required = gap
    contribution = goal.monthly_contribution if planned_contribution is None else planned_contribution
    funded = min(max(Decimal("0"), available_monthly_surplus), contribution)
    required = required.quantize(Decimal("0.01"), rounding=ROUND_CEILING)

    if gap == 0:
        status: FundingStatus = "ON_TRACK"
    elif remaining_months is None:
        status = "NEEDS_TARGET_DATE"
    elif remaining_months == 0:
        status = "NOT_FEASIBLE_WITH_CURRENT_SURPLUS"
    elif required > 0 and funded >= required:
        status = "ON_TRACK"
    elif available_monthly_surplus <= 0 or required > available_monthly_surplus:
        status = "NOT_FEASIBLE_WITH_CURRENT_SURPLUS"
    elif required > 0 and funded >= required * Decimal("0.8"):
        status = "SLIGHTLY_BEHIND"
    else:
        status = "AT_RISK"

    return GoalAnalysisResponse(
        goal_id=goal.id,
        name=goal.name,
        goal_type=goal.goal_type.value,
        goal_horizon=classify_horizon(remaining_months),
        remaining_months=remaining_months,
        target_amount=goal.target_amount,
        current_amount=goal.current_amount,
        funding_gap=gap.quantize(Decimal("0.01")),
        required_monthly_contribution=required.quantize(Decimal("0.01")),
        planned_monthly_contribution=contribution.quantize(Decimal("0.01")),
        funded_monthly_contribution=funded.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        funding_status=status,
    )
