from decimal import Decimal

from app.models.enums import GoalType
from app.schemas.planning import FinancialPriorityResponse, GoalAnalysisResponse, PriorityLevel
from app.services.goal_analysis_service import analyze_goal
from app.services.planning_context import PlanningContext


def evaluate_financial_priorities(
    context: PlanningContext,
    goal_analyses: list[GoalAnalysisResponse] | None = None,
) -> list[FinancialPriorityResponse]:
    summary = context.summary
    profile = context.profile
    income = summary.monthly_income
    debt_ratio = profile.monthly_debt_payment / income if income > 0 else Decimal("1")
    priorities: list[FinancialPriorityResponse] = []

    if summary.monthly_surplus <= 0:
        priorities.append(FinancialPriorityResponse(
            priority_level="CRITICAL",
            purpose="Stabilize monthly cash flow",
            action="Review spending and required obligations before adding new commitments",
            reason_code="NO_MONTHLY_SURPLUS",
            reason="Recorded monthly income does not exceed expenses and debt obligations.",
        ))

    scheduled = sum((goal.monthly_contribution for goal in context.goals), Decimal("0"))
    if max(context.actual_monthly_savings, scheduled) > max(Decimal("0"), summary.monthly_surplus):
        priorities.append(FinancialPriorityResponse(
            priority_level="CRITICAL", purpose="Reconcile existing commitments",
            action="Reduce commitments or revise goal timelines before adding allocations",
            reason_code="COMMITMENTS_EXCEED_SURPLUS",
            reason="Recorded savings or scheduled goal contributions exceed positive monthly cash flow.",
        ))

    if debt_ratio >= Decimal("0.25") or (income > 0 and profile.total_debt >= income * 12):
        priorities.append(FinancialPriorityResponse(
            priority_level="HIGH",
            purpose="Debt repayment capacity",
            action="Review debt repayment capacity before increasing long-term allocations",
            reason_code="HIGH_DEBT_BURDEN",
            reason=f"Monthly debt payments are {debt_ratio * 100:.1f}% of monthly income.",
        ))

    emergency_target = summary.emergency_fund_target
    current_emergency = profile.emergency_savings
    emergency_coverage = current_emergency / emergency_target if emergency_target > 0 else Decimal("1")
    if summary.emergency_fund_gap > 0:
        level: PriorityLevel = "HIGH"
        priorities.append(FinancialPriorityResponse(
            priority_level=level,
            purpose="Emergency Fund",
            action="Build accessible emergency reserves toward the selected target",
            reason_code="LOW_EMERGENCY_RESERVE" if emergency_coverage < Decimal("0.5") else "EMERGENCY_FUND_BELOW_TARGET",
            reason=(
                f"Emergency savings cover {emergency_coverage * 100:.1f}% of the target "
                f"({profile.emergency_fund_target_months} months of essential expenses)."
            ),
            related_goal_id=next((goal.id for goal in context.goals if goal.goal_type == GoalType.EMERGENCY_FUND), None),
        ))

    analyses = goal_analyses if goal_analyses is not None else [
        analyze_goal(goal, context.today, max(Decimal("0"), summary.monthly_surplus))
        for goal in context.goals
    ]
    goal_map = {goal.id: goal for goal in context.goals}
    for analysis in sorted(analyses, key=lambda item: (
        item.remaining_months is None, item.remaining_months or 0, goal_map[item.goal_id].priority, item.goal_id,
    )):
        goal = goal_map[analysis.goal_id]
        if analysis.funding_status == "NEEDS_TARGET_DATE":
            priorities.append(FinancialPriorityResponse(
                priority_level="MEDIUM", purpose=analysis.name, action="Set a target date to assess goal feasibility",
                reason_code="GOAL_TARGET_DATE_REQUIRED", reason="A monthly saving amount alone does not establish a dated funding requirement.",
                related_goal_id=analysis.goal_id,
            ))
            continue
        if goal.goal_type == GoalType.EMERGENCY_FUND or analysis.goal_horizon not in ("VERY_SHORT_TERM", "SHORT_TERM", "MEDIUM_TERM"):
            continue
        if analysis.funding_status in ("AT_RISK", "NOT_FEASIBLE_WITH_CURRENT_SURPLUS", "SLIGHTLY_BEHIND"):
            level = "HIGH" if analysis.remaining_months is not None and analysis.remaining_months <= 12 else "MEDIUM"
            priorities.append(FinancialPriorityResponse(
                priority_level=level,
                purpose=analysis.name,
                action="Review the goal timeline or monthly contribution",
                reason_code="GOAL_BEHIND_SCHEDULE",
                reason=f"The goal needs about ₹{analysis.required_monthly_contribution:,.0f}/month; planned contribution is ₹{analysis.planned_monthly_contribution:,.0f}/month.",
                related_goal_id=analysis.goal_id,
            ))

    if not priorities:
        long_goal = next((item for item in analyses if item.goal_horizon == "LONG_TERM"), None)
        priorities.append(FinancialPriorityResponse(
            priority_level="LOW" if long_goal else "MEDIUM",
            purpose=long_goal.name if long_goal else "Maintain financial resilience",
            action="Long-term educational allocations can be explored after current commitments",
            reason_code="LONG_TERM_GOAL" if long_goal else "PRIORITIES_ON_TRACK",
            reason="Emergency reserves and near-term commitments do not currently indicate a higher priority.",
            related_goal_id=long_goal.goal_id if long_goal else None,
        ))

    rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    return sorted(priorities, key=lambda item: rank[item.priority_level])
