from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.financial_engine import FinancialProfile as EngineProfile
from app.financial_engine import FinancialSummary, calculate_financial_summary
from app.models.entities import Budget, Category, FinancialProfile, Goal, Transaction
from app.models.enums import GoalType, TransactionType
from app.schemas.dashboard import (
    CategoryAmount,
    DashboardResponse,
    EmergencyFundSummary,
    InvestableSurplusResponse,
    MonthlyAmount,
    MonthlySavingsAmount,
)
from app.services.goals import goal_response
from app.services.transactions import require_user

CENT = Decimal("0.01")


def month_start(value: date) -> date:
    return value.replace(day=1)


def next_month(value: date) -> date:
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1, day=1)
    return value.replace(month=value.month + 1, day=1)


def get_profile(db: Session, user_id: int) -> FinancialProfile:
    require_user(db, user_id)
    profile = db.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user_id))
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Financial profile not found")
    return profile


def period_cash_flow(db: Session, profile: FinancialProfile, period: date, *, through_day: int | None = None) -> dict:
    period = month_start(period)
    end = next_month(period)
    rows = db.execute(
        select(Transaction, Category)
        .outerjoin(Category, Transaction.category_id == Category.id)
        .where(
            Transaction.user_id == profile.user_id,
            Transaction.date >= period,
            Transaction.date < end,
        )
    ).all()
    if through_day is not None:
        rows = [(transaction, category) for transaction, category in rows if transaction.date.day <= through_day]

    salary_recorded = any(transaction.transaction_type == TransactionType.INCOME and category is not None
                          and category.name.casefold() == "salary" for transaction, category in rows)
    base_income = Decimal("0") if salary_recorded else profile.monthly_income
    essential_expenses = Decimal("0")
    discretionary_expenses = Decimal("0")
    other_income = profile.other_income
    savings = Decimal("0")
    category_totals: dict[tuple[int | None, str], Decimal] = {}
    category_essential: dict[int | None, bool] = {}
    for transaction, category in rows:
        if transaction.transaction_type == TransactionType.INCOME:
            other_income += transaction.amount
        elif transaction.transaction_type == TransactionType.SAVINGS:
            savings += transaction.amount
        elif transaction.transaction_type == TransactionType.EXPENSE:
            if category is not None and category.is_essential:
                essential_expenses += transaction.amount
            else:
                discretionary_expenses += transaction.amount
            key = (category.id if category else None, category.name if category else "Uncategorized")
            category_totals[key] = category_totals.get(key, Decimal("0")) + transaction.amount
            category_essential[key[0]] = category is not None and category.is_essential

    engine_profile = EngineProfile(
        monthly_take_home_income=base_income,
        monthly_other_income=other_income,
        essential_expenses=essential_expenses,
        discretionary_expenses=discretionary_expenses,
        debt_payments=profile.monthly_debt_payment,
        monthly_savings=savings,
        current_emergency_fund=profile.emergency_savings,
        emergency_fund_target_months=profile.emergency_fund_target_months,
        emergency_expense_baseline=max(essential_expenses, profile.typical_essential_expenses),
    )
    summary = calculate_financial_summary(engine_profile)
    return {
        "period": period,
        "summary": summary,
        "savings": savings,
        "income_transactions": other_income - profile.other_income,
        "base_income": base_income,
        "category_totals": category_totals,
        "transaction_count": len(rows),
        "category_essential": category_essential,
        "essential_expenses": essential_expenses,
        "discretionary_expenses": discretionary_expenses,
    }


def create_dashboard(db: Session, user_id: int, today: date | None = None) -> DashboardResponse:
    today = today or date.today()
    profile = get_profile(db, user_id)
    current_data = period_cash_flow(db, profile, today)
    current_summary: FinancialSummary = current_data["summary"]
    from app.services.investment_allocation_service import get_investment_plan

    investment_plan = get_investment_plan(db, user_id, today)
    category_amounts = [
        CategoryAmount(category_id=category_id, category=name, amount=amount.quantize(CENT))
        for (category_id, name), amount in sorted(
            current_data["category_totals"].items(), key=lambda entry: entry[1], reverse=True
        )
    ]

    income_expenses: list[MonthlyAmount] = []
    savings_trend: list[MonthlySavingsAmount] = []
    period = month_start(today)
    for offset in range(5, -1, -1):
        year = period.year
        month = period.month - offset
        while month <= 0:
            month += 12
            year -= 1
        month_date = date(year, month, 1)
        data = period_cash_flow(db, profile, month_date)
        summary: FinancialSummary = data["summary"]
        income_expenses.append(
            MonthlyAmount(
                month=month_date,
                income=summary.monthly_income,
                expenses=max(Decimal("0"), summary.monthly_expenses - profile.monthly_debt_payment),
            )
        )
        savings_trend.append(MonthlySavingsAmount(month=month_date, savings=data["savings"].quantize(CENT)))

    goals = db.scalars(select(Goal).where(Goal.user_id == user_id).order_by(Goal.priority, Goal.id)).all()
    return DashboardResponse(
        user_id=user_id,
        month=month_start(today),
        monthly_income=current_summary.monthly_income,
        monthly_expenses=current_summary.monthly_expenses,
        monthly_expenses_excluding_debt=(
            current_data["essential_expenses"] + current_data["discretionary_expenses"]
        ).quantize(CENT, rounding=ROUND_HALF_UP),
        monthly_debt_payment=profile.monthly_debt_payment.quantize(CENT),
        monthly_savings=current_summary.monthly_savings,
        savings_rate=current_summary.savings_rate_percent,
        monthly_surplus=current_summary.monthly_surplus,
        investable_surplus=investment_plan.investable_surplus,
        financial_health_score=current_summary.financial_health_score,
        emergency_fund=EmergencyFundSummary(
            current_amount=profile.emergency_savings.quantize(CENT),
            target_amount=current_summary.emergency_fund_target,
            remaining_amount=current_summary.emergency_fund_gap,
            coverage_percentage=current_summary.emergency_fund_coverage_percent,
        ),
        expense_by_category=category_amounts,
        income_vs_expenses=income_expenses,
        monthly_savings_trend=savings_trend,
        top_spending_categories=category_amounts[:5],
        goals=[goal_response(goal, today) for goal in goals],
    )


def calculate_available_surplus(db: Session, user_id: int, today: date | None = None) -> InvestableSurplusResponse:
    from app.services.investment_allocation_service import get_investment_plan

    plan = get_investment_plan(db, user_id, today)
    profile = get_profile(db, user_id)
    emergency_reserve = (
        plan.emergency_fund_gap / profile.emergency_fund_target_months
        if plan.emergency_fund_gap > 0
        else Decimal("0")
    ).quantize(CENT, rounding=ROUND_HALF_UP)
    planned_goal_contributions = sum(
        (goal.planned_monthly_contribution for goal in plan.goal_analysis),
        Decimal("0"),
    )
    return InvestableSurplusResponse(
        user_id=user_id,
        monthly_income=plan.monthly_income,
        monthly_expenses=plan.monthly_expenses,
        monthly_savings=plan.actual_monthly_savings,
        monthly_surplus=plan.monthly_surplus,
        monthly_debt_payment=profile.monthly_debt_payment.quantize(CENT),
        safety_buffer=plan.safety_buffer,
        emergency_fund_gap=plan.emergency_fund_gap,
        emergency_fund_monthly_reserve=emergency_reserve,
        monthly_goal_contributions=planned_goal_contributions,
        calculated_investable_surplus=plan.cash_after_actual_savings,
        available_investable_surplus=plan.investable_surplus,
        explanation=plan.methodology,
    )


def budget_status(db: Session, budget: Budget) -> dict:
    start = date(budget.year, budget.month, 1)
    end = next_month(start)
    spent = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.user_id == budget.user_id,
            Transaction.category_id == budget.category_id,
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.date >= start,
            Transaction.date < end,
        )
    )
    spent = Decimal(spent)
    percentage = spent / budget.monthly_limit * Decimal("100") if budget.monthly_limit else Decimal("0")
    if spent > budget.monthly_limit:
        status_text = "OVER_BUDGET"
    elif percentage >= Decimal("80"):
        status_text = "WARNING"
    else:
        status_text = "ON_TRACK"
    return {
        "budget_id": budget.id,
        "category_id": budget.category_id,
        "category": budget.category.name,
        "monthly_limit": budget.monthly_limit,
        "amount_spent": spent.quantize(CENT),
        "remaining_budget": (budget.monthly_limit - spent).quantize(CENT),
        "percentage_used": percentage.quantize(CENT, rounding=ROUND_HALF_UP),
        "status": status_text,
    }
