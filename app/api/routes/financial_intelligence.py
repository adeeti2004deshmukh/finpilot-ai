from app.services.auth import get_current_user, ensure_actor
from app.models.entities import User
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.planning import (
    AffordabilityAnalyzeRequest,
    AffordabilityAnalyzeResponse,
    FinancialHealthResponse,
    FinancialInsightsResponse,
    GoalComparisonResponse,
    InvestmentCategoryGuidance,
    InvestmentPlanResponse,
    MonthlyActionPlanResponse,
    WhatIfRequest,
    WhatIfResponse,
    GoalAnalysisResponse,
    FinancialPriorityResponse,
)
from app.services.goal_comparison_service import compare_categories_for_goal
from app.services.investment_allocation_service import get_investment_plan
from app.services.investment_category_service import list_investment_categories
from app.services import financial_tools

router = APIRouter()


@router.get(
    "/api/investment/plan/{user_id}",
    response_model=InvestmentPlanResponse,
    tags=["Investments"],
    summary="Build a deterministic purpose-first monthly allocation plan",
)
def investment_plan(user_id: int, db: Session = Depends(get_db)) -> InvestmentPlanResponse:
    return get_investment_plan(db, user_id)


@router.get(
    "/api/investment/categories",
    response_model=list[InvestmentCategoryGuidance],
    tags=["Investments"],
    summary="List educational investment and savings category metadata",
)
def investment_categories() -> list[InvestmentCategoryGuidance]:
    return list_investment_categories()


@router.get(
    "/api/investment/compare/{user_id}",
    response_model=GoalComparisonResponse,
    tags=["Investments"],
    summary="Compare category relevance for a saved financial goal",
)
def compare_goal_categories(
    user_id: int,
    goal_id: int = Query(gt=0),
    db: Session = Depends(get_db),
) -> GoalComparisonResponse:
    return compare_categories_for_goal(db, user_id, goal_id)


@router.post(
    "/api/affordability/analyze",
    response_model=AffordabilityAnalyzeResponse,
    tags=["Affordability"],
    summary="Analyze a cash or EMI purchase against current priorities",
)
def affordability_analysis(
    payload: AffordabilityAnalyzeRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> AffordabilityAnalyzeResponse:
    payload = payload.model_copy(update={"user_id": ensure_actor(actor, payload.user_id)})
    return financial_tools.analyze_affordability(db, actor.id, payload)


@router.get(
    "/api/financial-health/{user_id}",
    response_model=FinancialHealthResponse,
    tags=["Dashboard"],
    summary="Get the existing financial score and its deterministic components",
)
def financial_health(user_id: int, db: Session = Depends(get_db)) -> FinancialHealthResponse:
    return financial_tools.get_financial_health(db, user_id)


@router.get(
    "/api/financial-plan/monthly/{user_id}",
    response_model=MonthlyActionPlanResponse,
    tags=["Dashboard"],
    summary="Build a monthly plan constrained by recorded income and commitments",
)
def monthly_action_plan(user_id: int, db: Session = Depends(get_db)) -> MonthlyActionPlanResponse:
    return financial_tools.get_monthly_plan(db, user_id)


@router.post(
    "/api/financial-plan/what-if/{user_id}",
    response_model=WhatIfResponse,
    tags=["Dashboard"],
    summary="Compare the current financial picture with a deterministic scenario",
)
def what_if_scenario(user_id: int, payload: WhatIfRequest, db: Session = Depends(get_db)) -> WhatIfResponse:
    return financial_tools.run_what_if_scenario(db, user_id, payload)


@router.get(
    "/api/financial-insights/{user_id}",
    response_model=FinancialInsightsResponse,
    tags=["Dashboard"],
    summary="Return deterministic month-over-month financial insights",
)
def financial_insights(user_id: int, db: Session = Depends(get_db)) -> FinancialInsightsResponse:
    return financial_tools.get_financial_insights(db, user_id)


@router.get("/api/financial-priorities/{user_id}", response_model=list[FinancialPriorityResponse], tags=["Dashboard"])
def financial_priorities(user_id: int, db: Session = Depends(get_db)):
    return financial_tools.get_financial_priorities(db, user_id)


@router.get("/api/goals/{goal_id}/analysis", response_model=GoalAnalysisResponse, tags=["Goals"])
def goal_analysis(goal_id: int, user_id: int = Query(gt=0), db: Session = Depends(get_db)):
    return financial_tools.analyze_goal(db, user_id, goal_id)
