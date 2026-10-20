from decimal import Decimal

from app.financial_engine import FinancialProfile as EngineProfile
from app.financial_engine import calculate_financial_health_breakdown
from app.models.enums import GoalType
from app.schemas.planning import FinancialHealthResponse, HealthScoreComponent
from app.services.investment_allocation_service import build_investment_plan
from app.services.planning_context import PlanningContext


def build_financial_health(context: PlanningContext) -> FinancialHealthResponse:
    profile = context.profile
    data = context.cash_flow
    engine_profile = EngineProfile(
        monthly_take_home_income=data["base_income"],
        monthly_other_income=profile.other_income + data["income_transactions"],
        essential_expenses=data["essential_expenses"],
        discretionary_expenses=data["discretionary_expenses"],
        debt_payments=profile.monthly_debt_payment,
        monthly_savings=data["savings"],
        current_emergency_fund=profile.emergency_savings,
        emergency_fund_target_months=profile.emergency_fund_target_months,
        emergency_expense_baseline=max(data["essential_expenses"], profile.typical_essential_expenses),
    )
    breakdown = calculate_financial_health_breakdown(engine_profile)
    savings_rate = context.summary.savings_rate_percent
    coverage = context.summary.emergency_fund_coverage_percent
    expense_ratio = (
        context.summary.monthly_expenses / context.summary.monthly_income * Decimal("100")
        if context.summary.monthly_income > 0
        else Decimal("100")
    )
    debt_ratio = (
        profile.monthly_debt_payment / context.summary.monthly_income * Decimal("100")
        if context.summary.monthly_income > 0
        else Decimal("100")
    )
    components = [
        HealthScoreComponent(
            name="Savings rate", points=breakdown.savings_points, maximum_points=30,
            status="STRONG" if savings_rate >= 20 else "BUILDING",
            reason=f"Recorded savings are {savings_rate:.1f}% of income; the Phase 1 scoring cap is 20%.",
        ),
        HealthScoreComponent(
            name="Emergency fund", points=breakdown.emergency_fund_points, maximum_points=30,
            status="ON_TARGET" if coverage >= 100 else "BUILDING",
            reason=f"Emergency savings cover {coverage:.1f}% of the selected target.",
        ),
        HealthScoreComponent(
            name="Expense discipline", points=breakdown.expense_discipline_points, maximum_points=20,
            status="STRONG" if expense_ratio <= 50 else "REVIEW" if expense_ratio >= 90 else "STEADY",
            reason=f"Recorded monthly expenses are {expense_ratio:.1f}% of income.",
        ),
        HealthScoreComponent(
            name="Debt burden", points=breakdown.debt_points, maximum_points=20,
            status="LOW" if debt_ratio <= 10 else "REVIEW" if debt_ratio >= 40 else "MODERATE",
            reason=f"Monthly debt payments are {debt_ratio:.1f}% of income.",
        ),
    ]
    goals = build_investment_plan(context).goal_analysis
    scored_goals = [goal for goal in goals if goal.goal_type != GoalType.EMERGENCY_FUND.value]
    on_track = sum(goal.funding_status == "ON_TRACK" for goal in scored_goals)
    goal_context = (
        f"{on_track} of {len(scored_goals)} non-emergency goals are on track. Goal progress is shown as context, "
        "not included in the unchanged Phase 1 score formula."
        if scored_goals
        else "No non-emergency goals are configured; goal progress is not included in the Phase 1 score."
    )

    strengths = [component.reason for component in components if component.points >= component.maximum_points * 0.75]
    areas = [component.reason for component in components if component.points < component.maximum_points * 0.5]
    actions: list[str] = []
    if context.summary.emergency_fund_gap > 0:
        actions.append(
            f"Build emergency coverage from {coverage / Decimal('100') * profile.emergency_fund_target_months:.1f} months toward the selected {profile.emergency_fund_target_months}-month target."
        )
    if debt_ratio >= 25:
        actions.append("Review debt repayment capacity before increasing optional long-term allocations.")
    if savings_rate < 20:
        actions.append("Review whether monthly savings can increase without reducing essential spending or required goal funding.")
    if not actions:
        actions.append("Keep reviewing actual monthly transactions against your stated goals and safety buffer.")
    if not strengths:
        strengths.append("Your financial picture is being measured from recorded income, expenses, savings, and debt.")

    return FinancialHealthResponse(
        user_id=context.user_id,
        score=breakdown.score,
        components=components,
        goal_progress_context=goal_context,
        strengths=strengths,
        areas_to_improve=areas,
        deterministic_actions=actions,
    )