from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.models.entities import Goal
from app.schemas.goals import GoalResponse
from app.services.goal_analysis_service import analyze_goal


def goal_response(goal: Goal, today: date | None = None) -> GoalResponse:
    today = today or date.today()
    remaining = max(Decimal("0"), goal.target_amount - goal.current_amount)
    progress = min(Decimal("100"), goal.current_amount / goal.target_amount * Decimal("100"))
    analysis = analyze_goal(goal, today, max(Decimal("0"), goal.monthly_contribution))
    months_remaining = analysis.remaining_months
    required_contribution = analysis.required_monthly_contribution

    return GoalResponse(
        id=goal.id,
        user_id=goal.user_id,
        name=goal.name,
        goal_type=goal.goal_type,
        target_amount=goal.target_amount,
        current_amount=goal.current_amount,
        target_date=goal.target_date,
        monthly_contribution=goal.monthly_contribution,
        priority=goal.priority,
        remaining_amount=remaining.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        progress_percentage=progress.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        months_remaining=months_remaining,
        required_monthly_contribution=required_contribution.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )