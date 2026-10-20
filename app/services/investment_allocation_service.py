from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.config import settings
from app.models.entities import Goal
from app.models.enums import GoalType, RiskTolerance
from app.schemas.planning import (
    GoalAnalysisResponse,
    InvestmentAllocationResponse,
    InvestmentCategoryGuidance,
    InvestmentPlanResponse,
    MonthlyPlanLine,
)
from app.services.financial_priority_service import evaluate_financial_priorities
from app.services.goal_analysis_service import analyze_goal
from app.services.investment_category_service import (
    category_guidance_by_name,
    list_investment_categories,
    score_category_relevance,
)
from app.services.planning_context import PlanningContext, load_planning_context

CENT = Decimal("0.01")
ZERO = Decimal("0")


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _percent(amount: Decimal, total: Decimal) -> Decimal:
    if total <= ZERO:
        return ZERO.quantize(CENT)
    return (amount / total * Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)


def _alloc(
    purpose: str,
    amount: Decimal,
    total_surplus: Decimal,
    reason_code: str,
    reason: str,
    categories: list[InvestmentCategoryGuidance],
    goal_id: int | None = None,
) -> InvestmentAllocationResponse:
    return InvestmentAllocationResponse(
        purpose=purpose,
        amount=_money(amount),
        percentage=_percent(amount, total_surplus),
        reason_code=reason_code,
        reason=reason,
        categories_to_explore=categories,
        related_goal_id=goal_id,
    )


def _long_term_guidance(risk: RiskTolerance) -> list[InvestmentCategoryGuidance]:
    available = {item.name: item for item in list_investment_categories()}
    if risk == RiskTolerance.LOW:
        names = ["Debt-oriented category", "Fixed Deposit (FD)", "Recurring Deposit (RD)"]
    elif risk == RiskTolerance.HIGH:
        names = ["Index-oriented SIP category", "Mutual Fund SIP", "Debt-oriented category"]
    else:
        names = ["Mutual Fund SIP", "Debt-oriented category", "Index-oriented SIP category"]
    return [available[name] for name in names]


def build_investment_plan(
    context: PlanningContext,
    safety_buffer_rate: Decimal | None = None,
    safety_buffer_minimum: Decimal | None = None,
) -> InvestmentPlanResponse:
    profile = context.profile
    summary = context.summary
    income = summary.monthly_income
    monthly_surplus = summary.monthly_surplus
    actual_savings = context.actual_monthly_savings
    positive_surplus = max(ZERO, monthly_surplus)
    savings_committed = min(actual_savings, positive_surplus)
    cash_after_actual_savings = max(ZERO, positive_surplus - savings_committed)

    goal_planned_total = sum((goal.monthly_contribution for goal in context.goals), ZERO)
    existing_goal_commitments = max(ZERO, min(goal_planned_total, positive_surplus) - savings_committed)
    cash_after_existing_commitments = max(ZERO, cash_after_actual_savings - existing_goal_commitments)

    buffer_rate = safety_buffer_rate if safety_buffer_rate is not None else settings.safety_buffer_rate
    buffer_minimum = safety_buffer_minimum if safety_buffer_minimum is not None else settings.safety_buffer_minimum
    if not buffer_rate.is_finite() or not ZERO <= buffer_rate <= 1 or not buffer_minimum.is_finite() or buffer_minimum < ZERO:
        raise ValueError("Safety buffer requires a rate between 0 and 1 and a nonnegative minimum")
    safety_buffer_target = _money(max(income * buffer_rate, buffer_minimum))
    safety_buffer = min(cash_after_existing_commitments, safety_buffer_target)
    remaining = max(ZERO, cash_after_existing_commitments - safety_buffer)

    emergency_target = summary.emergency_fund_target
    emergency_gap = summary.emergency_fund_gap
    emergency_monthly_need = emergency_gap / profile.emergency_fund_target_months if emergency_gap > 0 else ZERO
    emergency_goal = next((goal for goal in context.goals if goal.goal_type == GoalType.EMERGENCY_FUND), None)
    # Scheduled contributions share one household budget. Recorded savings
    # overlap them by policy because the existing schema has no goal linkage.
    base_budget = min(goal_planned_total, positive_surplus)
    base_funded = {}
    ordered_goals = sorted(context.goals, key=lambda goal: (
        goal.goal_type != GoalType.EMERGENCY_FUND,
        goal.target_date is None, goal.target_date or date.max, goal.priority, goal.id,
    ))
    for goal in ordered_goals:
        funded = min(base_budget, goal.monthly_contribution)
        if goal.current_amount >= goal.target_amount:
            funded = ZERO
        base_funded[goal.id] = funded
        base_budget -= funded
    emergency_planned = sum((base_funded[g.id] for g in context.goals
                             if g.goal_type == GoalType.EMERGENCY_FUND), ZERO)
    emergency_incremental_need = max(ZERO, emergency_monthly_need - emergency_planned)

    preliminary_goals = [
        analyze_goal(goal, context.today, base_funded[goal.id], base_funded[goal.id])
        for goal in context.goals
    ]
    priorities = evaluate_financial_priorities(context, preliminary_goals)
    high_debt = any(item.reason_code == "HIGH_DEBT_BURDEN" for item in priorities)
    debt_target = ZERO
    if high_debt and profile.total_debt > 0:
        debt_target = min(profile.total_debt / Decimal("24"), income * Decimal("0.10"))
    debt_reserve = min(remaining, _money(debt_target))
    remaining -= debt_reserve

    emergency_reserve = min(remaining, _money(emergency_incremental_need))
    remaining -= emergency_reserve

    goal_allocations: list[tuple[Goal, GoalAnalysisResponse, Decimal]] = []
    for goal, analysis in sorted(
        zip(context.goals, preliminary_goals),
        key=lambda pair: (pair[1].remaining_months is None, pair[1].remaining_months or 0, pair[0].priority, pair[0].id),
    ):
        if goal.goal_type == GoalType.EMERGENCY_FUND:
            continue
        if analysis.goal_horizon not in ("VERY_SHORT_TERM", "SHORT_TERM", "MEDIUM_TERM"):
            continue
        incremental_need = max(ZERO, analysis.required_monthly_contribution - base_funded[goal.id])
        allocation = min(remaining, incremental_need) if analysis.remaining_months else ZERO
        if allocation > 0:
            goal_allocations.append((goal, analysis, allocation))
            remaining -= allocation

    secondary_buffer = _money(remaining * Decimal("0.10"))
    long_term_allocation = remaining - secondary_buffer
    long_term_total = long_term_allocation
    for goal, analysis in sorted(zip(context.goals, preliminary_goals),
                                  key=lambda pair: (pair[0].priority, pair[0].id)):
        if goal.goal_type == GoalType.EMERGENCY_FUND or analysis.goal_horizon != "LONG_TERM":
            continue
        amount = min(long_term_allocation, max(ZERO, analysis.required_monthly_contribution - base_funded[goal.id]))
        if amount > 0:
            goal_allocations.append((goal, analysis, amount))
            long_term_allocation -= amount
    allocations: list[InvestmentAllocationResponse] = []
    if safety_buffer > 0:
        allocations.append(_alloc(
            "Monthly safety buffer", safety_buffer, positive_surplus, "SAFETY_BUFFER",
            f"Reserves {buffer_rate * 100:.1f}% of income, subject to the configured minimum and available cash.",
            [category_guidance_by_name("Savings Account")],
        ))
    if debt_reserve > 0:
        allocations.append(_alloc(
            "Additional debt repayment capacity", debt_reserve, positive_surplus, "HIGH_DEBT_BURDEN",
            "A portion of remaining cash is held for debt reduction because debt burden is above the priority threshold.",
            [],
        ))
    if emergency_reserve > 0:
        allocations.append(_alloc(
            "Emergency Fund", emergency_reserve, positive_surplus, "EMERGENCY_FUND_BELOW_TARGET",
            f"Emergency savings cover {summary.emergency_fund_coverage_percent:.1f}% of the selected target; accessible reserves are prioritized.",
            [category_guidance_by_name("Savings Account"), category_guidance_by_name("Recurring Deposit (RD)")],
            emergency_goal.id if emergency_goal else None,
        ))

    goal_analysis_results: list[GoalAnalysisResponse] = []
    for goal, analysis, amount in goal_allocations:
        relevance = score_category_relevance(
            analysis,
            profile.risk_tolerance,
            summary.emergency_fund_coverage_percent,
        )
        allocations.append(_alloc(
            goal.name, amount, positive_surplus,
            "LONG_TERM_GOAL" if analysis.goal_horizon == "LONG_TERM" else "MEDIUM_TERM_GOAL" if analysis.goal_horizon == "MEDIUM_TERM" else "SHORT_TERM_GOAL",
            f"This dated goal has a {analysis.goal_horizon.lower().replace('_', ' ')} horizon and a calculated funding gap.",
            relevance[:3], goal.id,
        ))

    goal_analysis_results = []
    for goal, analysis in zip(context.goals, preliminary_goals):
        allocated = next((amount for item_goal, _, amount in goal_allocations if item_goal.id == goal.id), ZERO)
        emergency_topup = emergency_reserve if emergency_goal and goal.id == emergency_goal.id else ZERO
        effective_funded = base_funded[goal.id] + allocated + emergency_topup
        goal_analysis_results.append(analyze_goal(goal, context.today, effective_funded,
                                                 max(goal.monthly_contribution, effective_funded)))

    if long_term_allocation > 0:
        allocations.append(_alloc(
            "Long-term allocation to explore", long_term_allocation, positive_surplus, "LONG_TERM_GOAL",
            "This is the residual after recorded savings, existing goal commitments, safety reserve, emergency priority, debt reserve, and near-term goal needs.",
            _long_term_guidance(profile.risk_tolerance),
            None,
        ))
    if secondary_buffer > 0:
        allocations.append(_alloc(
            "Additional unallocated reserve", secondary_buffer, positive_surplus, "EXCESS_SURPLUS",
            "Ten percent of cash remaining after priority allocations stays unassigned; not every rupee is allocated.",
            [category_guidance_by_name("Savings Account")],
        ))

    goal_contribution_sum = sum((goal.monthly_contribution for goal in context.goals), ZERO)
    warnings: list[str] = []
    if monthly_surplus <= 0:
        warnings.append("Monthly expenses and debt obligations meet or exceed income; no new allocation is suggested.")
    if actual_savings > positive_surplus:
        warnings.append("Recorded savings exceed the current month's surplus; the plan does not suggest additional allocation.")
    if goal_planned_total > 0 and actual_savings > 0:
        warnings.append("Savings transactions are not linked to individual goals; existing savings and goal commitments are treated as overlapping up to the larger total to avoid double-counting.")
    if safety_buffer < safety_buffer_target:
        warnings.append("Available cash does not fully fund the configured monthly safety buffer.")
    if emergency_gap > 0 and emergency_reserve < emergency_incremental_need:
        warnings.append("The emergency-fund reserve target exceeds cash remaining after higher-priority commitments.")
    if long_term_total == 0:
        warnings.append("No surplus remains for a new long-term allocation after current commitments and priorities.")
    if goal_contribution_sum > positive_surplus:
        warnings.append("Stored monthly goal contributions exceed the positive monthly surplus.")

    existing_reserved = positive_surplus - cash_after_existing_commitments
    existing_goal_funded = sum(base_funded.values(), ZERO)
    ledger = [MonthlyPlanLine(purpose="Existing savings and scheduled goal reserve",
                              amount=_money(existing_reserved), reason_code="EXISTING_COMMITMENTS")]
    ledger.extend(MonthlyPlanLine(purpose=item.purpose, amount=item.amount, reason_code=item.reason_code)
                  for item in allocations)
    allocation_total = sum((line.amount for line in ledger), ZERO)
    if allocation_total > positive_surplus:
        raise ValueError("Monthly allocations exceed positive cash flow")
    return InvestmentPlanResponse(
        user_id=context.user_id,
        currency="INR",
        monthly_income=_money(income),
        monthly_expenses=_money(context.cash_flow["essential_expenses"] + context.cash_flow["discretionary_expenses"]),
        monthly_debt_payment=_money(profile.monthly_debt_payment),
        actual_monthly_savings=_money(actual_savings),
        monthly_surplus=_money(monthly_surplus),
        cash_after_actual_savings=_money(cash_after_actual_savings),
        existing_goal_commitments=_money(existing_goal_commitments),
        cash_after_existing_commitments=_money(cash_after_existing_commitments),
        safety_buffer_target=_money(safety_buffer_target),
        safety_buffer=_money(safety_buffer),
        emergency_fund_current=_money(profile.emergency_savings),
        emergency_fund_target=_money(emergency_target),
        emergency_fund_gap=_money(emergency_gap),
        debt_repayment_reserve=_money(debt_reserve),
        short_term_goal_reserve=_money(sum((amount for _, analysis, amount in goal_allocations if analysis.goal_horizon in ("VERY_SHORT_TERM", "SHORT_TERM")), ZERO)),
        goal_contributions=_money(sum((base_funded[g.id] for g in context.goals if g.goal_type != GoalType.EMERGENCY_FUND), ZERO) + sum((amount for _, _, amount in goal_allocations), ZERO)),
        scheduled_goal_contributions=_money(goal_planned_total),
        funded_existing_goal_contributions=_money(existing_goal_funded),
        savings_goal_overlap=_money(min(savings_committed, existing_goal_funded)),
        allocation_total=_money(allocation_total),
        funding_ledger=ledger,
        emergency_fund_contribution=_money(emergency_planned + emergency_reserve),
        investable_surplus=_money(long_term_total),
        unallocated_buffer=_money(secondary_buffer),
        financial_priorities=evaluate_financial_priorities(context, goal_analysis_results),
        allocations=allocations,
        goal_analysis=goal_analysis_results,
        warnings=warnings,
        methodology=[
            "Monthly surplus = monthly income - essential expenses - discretionary expenses - debt payments.",
            "Actual monthly savings are recorded SAVINGS transactions; they are not inferred from leftover cash.",
            "Existing goal contributions and actual savings overlap up to the larger total because transactions are not linked to goals.",
            f"Safety buffer target = max({buffer_rate * 100:.1f}% of income, ₹{buffer_minimum:,.0f}); reserve is capped at cash available.",
            "Existing commitments and safety are reserved first; marginal funding order is high debt, emergency reserves, dated goals by earliest deadline (including medium term), then long-term capacity.",
            "Goal contributions are funded non-emergency goals; emergency funding is separate. Recorded savings overlap funded existing goals by the reported savings_goal_overlap and must not be added twice.",
            "Investable surplus includes funded long-term top-ups plus generic long-term capacity. The funding_ledger is the additive cash reconciliation; contribution totals are its descriptive subsets.",
            "Ten percent of the remaining post-priority cash is held as additional unallocated reserve; remaining long-term amount is the investable surplus.",
            "All proposed allocations are capped by positive surplus after existing savings and goal commitments.",
        ],
    )


def get_investment_plan(db: Session, user_id: int, today: date | None = None) -> InvestmentPlanResponse:
    return build_investment_plan(load_planning_context(db, user_id, today))
