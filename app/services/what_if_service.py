from dataclasses import replace
from calendar import monthrange
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.financial_engine import FinancialProfile as EngineProfile
from app.financial_engine import calculate_financial_summary
from app.schemas.planning import WhatIfRequest, WhatIfResponse, WhatIfSnapshot
from app.services.investment_allocation_service import build_investment_plan
from app.services.planning_context import PlanningContext, load_planning_context

ZERO = Decimal("0")


def _date_after_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def _snapshot(context: PlanningContext) -> WhatIfSnapshot:
    plan = build_investment_plan(context)
    essential = max(context.cash_flow["essential_expenses"], context.profile.typical_essential_expenses)
    months = context.profile.emergency_fund_target_months
    emergency_months = context.profile.emergency_savings / essential if essential > 0 else Decimal(months)
    analyses = plan.goal_analysis
    return WhatIfSnapshot(
        monthly_income=context.summary.monthly_income,
        monthly_expenses=context.summary.monthly_expenses,
        actual_monthly_savings=context.actual_monthly_savings,
        savings_rate=context.summary.savings_rate_percent,
        monthly_surplus=context.summary.monthly_surplus,
        investable_surplus=plan.investable_surplus,
        emergency_fund_months=emergency_months.quantize(Decimal("0.01")),
        goal_feasibility=analyses,
    )


def _recalculate(context: PlanningContext, *, income_delta: Decimal = ZERO, essential_delta: Decimal = ZERO,
                 discretionary_delta: Decimal = ZERO, savings_delta: Decimal = ZERO,
                 goals: list | None = None) -> PlanningContext:
    profile = context.profile
    data = dict(context.cash_flow)
    data["essential_expenses"] = max(ZERO, data["essential_expenses"] + essential_delta)
    data["discretionary_expenses"] = max(ZERO, data["discretionary_expenses"] + discretionary_delta)
    data["savings"] = max(ZERO, data["savings"] + savings_delta)
    engine_profile = EngineProfile(
        monthly_take_home_income=data["base_income"] + income_delta,
        monthly_other_income=profile.other_income + data["income_transactions"],
        essential_expenses=data["essential_expenses"],
        discretionary_expenses=data["discretionary_expenses"],
        debt_payments=profile.monthly_debt_payment,
        monthly_savings=data["savings"],
        current_emergency_fund=profile.emergency_savings,
        emergency_fund_target_months=profile.emergency_fund_target_months,
        emergency_expense_baseline=max(data["essential_expenses"], profile.typical_essential_expenses),
    )
    data["summary"] = calculate_financial_summary(engine_profile)
    data["base_income"] += income_delta
    return replace(context, cash_flow=data, goals=goals if goals is not None else context.goals)


def run_what_if(db: Session, user_id: int, request: WhatIfRequest, today: date | None = None) -> WhatIfResponse:
    context = load_planning_context(db, user_id, today)
    current = _snapshot(context)
    projected_context = context
    changes: dict[str, Decimal | int | str] = {}
    warnings = ["What-if values are deterministic estimates using current recorded data; they do not forecast returns or future behavior."]

    if request.scenario_type == "INCOME_INCREASE":
        projected_context = _recalculate(context, income_delta=request.amount)
        changes = {"monthly_income_change": request.amount}
    elif request.scenario_type == "RENT_INCREASE":
        projected_context = _recalculate(context, essential_delta=request.amount)
        changes = {"essential_expense_change": request.amount}
    elif request.scenario_type == "FOOD_SPENDING_REDUCTION":
        food_totals = {True: ZERO, False: ZERO}
        known_ids = {category_id for category_id, _ in context.cash_flow["category_totals"]}
        if any(category_id not in known_ids for category_id in request.category_ids):
            raise HTTPException(status_code=422, detail="Select categories with recorded expense spending for this user and month")
        for (category_id, category_name), value in context.cash_flow["category_totals"].items():
            selected = category_id in request.category_ids if request.category_ids else "food" in category_name.casefold()
            if selected:
                food_totals[context.cash_flow["category_essential"].get(category_id, False)] += value
        if sum(food_totals.values(), ZERO) == 0:
            warnings.append("No matching food spending was recorded; select expense category IDs explicitly to model your food categories.")
        elif request.amount > sum(food_totals.values(), ZERO):
            warnings.append("The reduction was capped at recorded spending in the selected categories.")
        discretionary_reduction = min(request.amount, food_totals[False])
        essential_reduction = min(request.amount - discretionary_reduction, food_totals[True])
        projected_context = _recalculate(
            context, essential_delta=-essential_reduction, discretionary_delta=-discretionary_reduction,
        )
        changes = {"discretionary_expense_reduction": discretionary_reduction,
                   "essential_expense_reduction": essential_reduction}
    elif request.scenario_type == "SAVINGS_INCREASE":
        projected_context = _recalculate(context, savings_delta=request.amount)
        changes = {"additional_monthly_savings": request.amount}
    else:
        goal = next((item for item in context.goals if item.id == request.goal_id), None)
        if goal is None:
            raise HTTPException(status_code=404, detail="Goal not found")
        if goal.target_date is None:
            raise HTTPException(status_code=400, detail="A target date is required to model a goal delay")
        delayed_goal = SimpleNamespace(
            id=goal.id,
            user_id=goal.user_id,
            name=goal.name,
            goal_type=goal.goal_type,
            target_amount=goal.target_amount,
            current_amount=goal.current_amount,
            target_date=_date_after_months(goal.target_date, request.delay_months or 1),
            monthly_contribution=goal.monthly_contribution,
            priority=goal.priority,
        )
        projected_goals = [delayed_goal if item.id == goal.id else item for item in context.goals]
        projected_context = replace(context, goals=projected_goals)
        changes = {"goal_id": goal.id, "delay_months": request.delay_months or 1}

    return WhatIfResponse(
        user_id=user_id,
        scenario_type=request.scenario_type,
        current=current,
        projected=_snapshot(projected_context),
        changes=changes,
        warnings=warnings + build_investment_plan(projected_context).warnings,
    )
