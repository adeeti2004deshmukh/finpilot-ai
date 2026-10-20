from dataclasses import replace
from types import SimpleNamespace
from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.schemas.planning import (
    AffordabilityAnalyzeRequest,
    AffordabilityAnalyzeResponse,
    AffordabilityScenario,
    AffordabilityStatus,
)
from app.services.investment_allocation_service import build_investment_plan
from app.services.planning_context import PlanningContext

ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _ratio(value: Decimal, denominator: Decimal) -> Decimal:
    return value / denominator if denominator > ZERO else ZERO


def _date_after_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def analyze_affordability(
    context: PlanningContext,
    request: AffordabilityAnalyzeRequest,
    *, _include_alternatives: bool = True,
) -> AffordabilityAnalyzeResponse:
    profile = context.profile
    plan = build_investment_plan(context)
    income = context.summary.monthly_income
    surplus_before = context.summary.monthly_surplus
    monthly_emi = request.monthly_emi or ZERO
    upfront = request.price if request.payment_method == "CASH" else (request.down_payment or ZERO)
    protected_goal_capital = min(max(ZERO, profile.current_savings - profile.emergency_savings),
                                 sum((g.current_amount for g in context.goals
                                      if g.goal_type.value != "EMERGENCY_FUND"), ZERO))
    liquid_non_emergency = max(ZERO, profile.current_savings - profile.emergency_savings - protected_goal_capital)
    emergency_draw = max(ZERO, upfront - liquid_non_emergency)
    emergency_after = max(ZERO, profile.emergency_savings - emergency_draw)
    funding_shortfall = max(ZERO, upfront - liquid_non_emergency - profile.emergency_savings)
    surplus_after = surplus_before - monthly_emi
    cash_flow_impact = request.price if request.payment_method == "CASH" else monthly_emi
    emergency_target = context.summary.emergency_fund_target
    essential_baseline = max(context.cash_flow["essential_expenses"], profile.typical_essential_expenses)
    coverage_before = _ratio(profile.emergency_savings, essential_baseline)
    coverage_after = _ratio(emergency_after, essential_baseline)
    debt_after = profile.monthly_debt_payment + monthly_emi
    debt_ratio_before = _ratio(profile.monthly_debt_payment, income)
    debt_ratio_after = _ratio(debt_after, income)

    planned_goal_total = sum((goal.monthly_contribution for goal in context.goals), ZERO)
    existing_commitments = max(context.actual_monthly_savings, planned_goal_total)
    safety_target = plan.safety_buffer_target
    free_after_purchase = max(ZERO, surplus_after - existing_commitments)
    funded_goal_topups = sum((item.amount for item in plan.allocations if item.related_goal_id is not None
                              and item.reason_code in {"SHORT_TERM_GOAL", "MEDIUM_TERM_GOAL", "LONG_TERM_GOAL"}), ZERO)
    current_short_goal_need = funded_goal_topups
    protected_monthly = plan.safety_buffer + plan.debt_repayment_reserve + sum(
        (item.amount for item in plan.allocations if item.reason_code == "EMERGENCY_FUND_BELOW_TARGET"), ZERO)
    free_after_purchase = max(ZERO, surplus_after - existing_commitments - protected_monthly)
    available_purchase_saving = sum((item.amount for item in plan.allocations
                                    if item.reason_code == "EXCESS_SURPLUS" or
                                    (item.reason_code == "LONG_TERM_GOAL" and item.related_goal_id is None)), ZERO)

    component_scores = {
        "emergency_fund_impact": int((min(Decimal("1"), _ratio(emergency_after, emergency_target)) * 25).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if emergency_target > 0 else 25,
        "monthly_cash_flow": int((min(Decimal("1"), max(ZERO, _ratio(surplus_after - existing_commitments, max(income * Decimal("0.4"), Decimal("1")))) ) * 25).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        "debt_burden": int((max(ZERO, min(Decimal("1"), (Decimal("0.4") - debt_ratio_after) / Decimal("0.4"))) * 15).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        "goal_impact": int(((Decimal("1") if current_short_goal_need == 0 else min(Decimal("1"), free_after_purchase / current_short_goal_need)) * Decimal("15")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        "purchase_relative_to_income": int((max(ZERO, min(Decimal("1"), Decimal("1") - _ratio(request.price, max(income * 6, Decimal("1"))))) * 10).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        "safety_buffer": int((min(Decimal("1"), free_after_purchase / safety_target) * 10).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if safety_target > 0 else 10,
    }
    # A purchase requiring unavailable cash or an unaffordable installment
    # must not receive a reassuring aggregate score from unrelated factors.
    if funding_shortfall > 0 or surplus_after < 0 or income <= 0 or monthly_emi > available_purchase_saving:
        component_scores = {name: 0 for name in component_scores}
    score = max(0, min(100, sum(component_scores.values())))
    affordability_status: AffordabilityStatus = (
        "COMFORTABLE" if score >= 80 else "MANAGEABLE" if score >= 65 else "CAUTION" if score >= 40 else "HIGH_RISK"
    )

    goal_impact = max(ZERO, current_short_goal_need - free_after_purchase)
    warnings: list[str] = []
    if protected_goal_capital > 0:
        warnings.append(f"?{protected_goal_capital:,.2f} of recorded savings is protected for existing goals and excluded from purchase cash.")
    if monthly_emi > available_purchase_saving:
        warnings.append("The EMI would displace existing savings, safety, debt, emergency or goal funding; it exceeds optional monthly capacity.")
    if funding_shortfall > 0:
        warnings.append(f"Upfront cash exceeds recorded liquid savings by ₹{funding_shortfall:,.2f}; the purchase is not fully funded.")
    if surplus_after < 0:
        warnings.append("Required expenses and debt payments after the purchase exceed monthly income.")
    if emergency_after < profile.emergency_savings:
        warnings.append(
            f"Cash or down payment would reduce emergency coverage from {coverage_before:.1f} to {coverage_after:.1f} months of essential expenses."
        )
    if request.payment_method == "EMI" and surplus_after - existing_commitments < safety_target:
        warnings.append("After the EMI and existing commitments, monthly cash flow falls below the configured safety-buffer target.")
    if debt_ratio_after >= Decimal("0.25"):
        warnings.append("Monthly debt obligations would be at least 25% of income after this EMI.")
    if goal_impact > 0:
        warnings.append(f"Current monthly cash flow would leave about ₹{goal_impact:,.0f} of short-term goal funding unmet.")
    if request.purchase_date > context.today:
        warnings.append("Future savings and investment returns are not projected; alternatives use principal-only saving amounts.")

    alternatives = []
    if _include_alternatives:
        alternatives.append(AffordabilityScenario(
            name="Buy now", purchase_date=context.today,
            required_monthly_saving=ZERO, projected_emergency_fund=_money(emergency_after),
            projected_goal_contribution=_money(plan.goal_contributions), status=affordability_status,
            available_monthly_saving=_money(available_purchase_saving), affordability_score=score,
            warnings=list(warnings),
        ))
        # Alternatives mean save first, then buy outright; an EMI is not assumed.
        future_gap = max(ZERO, request.price - liquid_non_emergency)
        for months in (3, 6, 12):
            required = (future_gap / months).quantize(Decimal("0.01"), rounding="ROUND_CEILING")
            affordable_saving = min(required, available_purchase_saving)
            future_profile = SimpleNamespace(**{name: getattr(profile, name) for name in (
                "current_savings", "emergency_savings", "monthly_debt_payment", "total_debt",
                "emergency_fund_target_months", "risk_tolerance", "monthly_income", "other_income", "typical_essential_expenses")})
            future_profile.current_savings += affordable_saving * months
            future_context = replace(context, profile=future_profile)
            purchase_date = _date_after_months(context.today, months)
            cash_request = AffordabilityAnalyzeRequest(user_id=context.user_id, item_name=request.item_name,
                price=request.price, purchase_date=purchase_date, payment_method="CASH")
            assessment = analyze_affordability(future_context, cash_request, _include_alternatives=False)
            shortfall = max(ZERO, required - available_purchase_saving)
            scenario_warnings = list(assessment.warnings)
            if shortfall > 0:
                scenario_warnings.append("The saving target exceeds optional monthly capacity; existing priorities cannot all be preserved.")
            alternatives.append(AffordabilityScenario(
                name=f"Wait {months} months" if months != 12 else "Save first over 12 months",
                purchase_date=purchase_date, required_monthly_saving=_money(required),
                projected_emergency_fund=assessment.emergency_fund_after,
                projected_goal_contribution=_money(plan.goal_contributions),
                status=assessment.affordability_status if shortfall == 0 else "HIGH_RISK",
                available_monthly_saving=_money(available_purchase_saving),
                monthly_saving_shortfall=_money(shortfall),
                affordability_score=assessment.affordability_score if shortfall == 0 else 0,
                warnings=scenario_warnings,
            ))

    return AffordabilityAnalyzeResponse(
        user_id=context.user_id,
        item_name=request.item_name,
        price=_money(request.price),
        payment_method=request.payment_method,
        affordability_score=score,
        affordability_status=affordability_status,
        cash_flow_impact=_money(cash_flow_impact),
        upfront_funding_shortfall=_money(funding_shortfall),
        emergency_fund_before=_money(profile.emergency_savings),
        emergency_fund_after=_money(emergency_after),
        emergency_coverage_months_before=_money(coverage_before),
        emergency_coverage_months_after=_money(coverage_after),
        goal_impact=_money(goal_impact),
        monthly_surplus_before=_money(surplus_before),
        monthly_surplus_after=_money(surplus_after),
        total_emi_commitment=_money(debt_after),
        debt_burden_before_percent=_money(debt_ratio_before * ONE_HUNDRED),
        debt_burden_after_percent=_money(debt_ratio_after * ONE_HUNDRED),
        score_components=component_scores,
        warnings=warnings,
        alternative_scenarios=alternatives,
        methodology=[
            "Score weights: emergency fund impact 25, monthly cash flow 25, debt burden 15, goal impact 15, purchase-to-income 10, safety buffer 10.",
            "Cash uses savings above emergency reserves and protected goal capital first; the remainder reduces emergency reserves. Current savings include emergency savings.",
            "EMI reduces monthly surplus by the entered installment and increases monthly debt obligations; down payment is treated as upfront cash.",
            "Buy now assesses current balances regardless of the entered date; future dates do not assume automatic accumulation. Wait alternatives explicitly save within optional capacity, then buy for cash at constant price.",
            "Wait alternatives protect existing monthly savings, safety, debt, emergency and goal funding, assume constant recorded cash flow, and include no investment returns or taxes.",
            "Affordability scores are deterministic planning signals, not approval or product recommendations.",
            "Score components are zero when upfront cash is unfunded, monthly cash flow is negative, income is zero, or an EMI displaces protected monthly commitments.",
        ],
    )
