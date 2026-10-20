"""Personal application APIs: the session establishes the user, never the browser."""
from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import User, Budget, Transaction, Goal, Alert, Subscription, InvestmentPreference
from app.services.auth import get_current_user
from app.services import financial_tools
from app.services.finance import get_profile, budget_status
from app.services.finance import calculate_available_surplus
from app.services.goals import goal_response
from app.api.routes.users import update_user
from app.api.routes.profiles import update_profile
from app.schemas.users import UserResponse, UserUpdate
from app.schemas.profiles import FinancialProfileResponse, FinancialProfileUpdate
from app.schemas.planning import WhatIfRequest
from app.schemas.budgets import BudgetResponse, BudgetStatusResponse
from app.schemas.goals import GoalResponse

router = APIRouter(prefix="/api/me", tags=["Personal finances"])


@router.get("/user", response_model=UserResponse)
def user_details(actor: User = Depends(get_current_user)):
    return actor


@router.put("/user", response_model=UserResponse)
def save_user(payload: UserUpdate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return update_user(actor.id, payload, db)


@router.get("/profile", response_model=FinancialProfileResponse)
def profile(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_profile(db, actor.id)


@router.put("/profile", response_model=FinancialProfileResponse)
def save_profile(payload: FinancialProfileUpdate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = update_profile(actor.id, payload, db)
    if actor.investment_preferences:
        actor.investment_preferences.risk_tolerance = profile.risk_tolerance
        db.commit()
    return profile


def personal_calculation(name, function):
    def endpoint(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
        return function(db, actor.id)
    endpoint.__name__ = name.replace("-", "_")
    router.add_api_route("/" + name, endpoint, methods=["GET"])


for name, function in (
    ("dashboard", financial_tools.get_financial_summary), ("investment-plan", financial_tools.get_investment_plan),
    ("financial-health", financial_tools.get_financial_health), ("monthly-plan", financial_tools.get_monthly_plan),
    ("insights", financial_tools.get_financial_insights), ("priorities", financial_tools.get_financial_priorities),
    ("available-surplus", calculate_available_surplus),
):
    personal_calculation(name, function)


@router.get("/investment-compare")
def comparison(goal_id: int = Query(gt=0), actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return financial_tools.compare_investment_categories(db, actor.id, goal_id)


@router.get("/goals", response_model=list[GoalResponse])
def goals(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [goal_response(goal) for goal in db.scalars(select(Goal).where(Goal.user_id == actor.id).order_by(Goal.priority, Goal.id)).all()]


@router.get("/budgets", response_model=list[BudgetResponse])
def budgets(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Budget).where(Budget.user_id == actor.id)).all()


@router.get("/budget-status", response_model=list[BudgetStatusResponse])
def statuses(month: int = Query(ge=1, le=12), year: int = Query(ge=2000, le=2200),
             actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [budget_status(db, budget) for budget in db.scalars(select(Budget).where(
        Budget.user_id == actor.id, Budget.month == month, Budget.year == year)).all()]


@router.get("/transactions")
def transactions(month: int | None = Query(default=None, ge=1, le=12),
                 year: int | None = Query(default=None, ge=2000, le=2200), category: int | None = None,
                 merchant: str | None = None, transaction_type: str | None = None,
                 page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=200),
                 actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.api.routes.transactions import list_transactions
    from app.models.enums import TransactionType
    try:
        kind = TransactionType(transaction_type) if transaction_type else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid transaction type")
    return list_transactions(month, year, category, merchant, kind, actor.id, page, page_size, db)


@router.post("/what-if")
def what_if(payload: WhatIfRequest, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return financial_tools.run_what_if_scenario(db, actor.id, payload)


@router.get("/category-suggestion")
def category_suggestion(merchant: str = Query(min_length=1, max_length=160), transaction_type: str = "EXPENSE",
                         actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.transactions import matching_category_id
    return {"category_id": matching_category_id(db, merchant, actor.id) if transaction_type == "EXPENSE" else None,
            "source": "DETERMINISTIC_MERCHANT_RULE"}


@router.get("/preferences")
def preferences(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    preference = db.scalar(select(InvestmentPreference).where(InvestmentPreference.user_id == actor.id))
    return {"risk_tolerance": preference.risk_tolerance if preference else get_profile(db, actor.id).risk_tolerance,
            "liquidity_requirement": preference.liquidity_requirement if preference else "MEDIUM",
            "preferred_time_horizon": preference.preferred_time_horizon if preference else 10}


@router.get("/alerts")
def alerts(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [{"id": item.id, "title": item.title, "message": item.message, "severity": item.severity,
             "is_read": item.is_read, "created_at": item.created_at}
            for item in db.scalars(select(Alert).where(Alert.user_id == actor.id).order_by(Alert.created_at.desc())).all()]


@router.get("/subscriptions")
def subscriptions(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [{"id": item.id, "merchant": item.merchant, "monthly_amount": str(item.monthly_amount), "estimated_annual_amount": str(item.estimated_annual_amount),
             "is_active": item.is_active} for item in db.scalars(select(Subscription).where(Subscription.user_id == actor.id)).all()]
