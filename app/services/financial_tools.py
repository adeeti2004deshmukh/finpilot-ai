"""User-scoped deterministic service interfaces; no AI dependency or invocation.

The caller injects a database session. Pydantic results support model_dump(mode="json").
Reads and scenarios never mutate persisted financial records.
"""
from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.planning import AffordabilityAnalyzeRequest, WhatIfRequest
from app.services.affordability_service import analyze_affordability as assess_purchase
from app.services.finance import create_dashboard
from app.services.financial_health_service import build_financial_health
from app.services.goal_comparison_service import compare_categories_for_goal
from app.services.insights_service import build_financial_insights
from app.services.investment_allocation_service import get_investment_plan
from app.services.monthly_action_plan_service import build_monthly_action_plan
from app.services.planning_context import load_planning_context
from app.services.what_if_service import run_what_if


def get_financial_summary(db: Session, user_id: int, today: date | None = None):
    return create_dashboard(db, user_id, today)


def get_financial_health(db: Session, user_id: int, today: date | None = None):
    return build_financial_health(load_planning_context(db, user_id, today))


def get_financial_priorities(db: Session, user_id: int, today: date | None = None):
    return get_investment_plan(db, user_id, today).financial_priorities


def get_monthly_plan(db: Session, user_id: int, today: date | None = None):
    return build_monthly_action_plan(load_planning_context(db, user_id, today))


def analyze_goal(db: Session, user_id: int, goal_id: int, today: date | None = None):
    goal = next((item for item in get_investment_plan(db, user_id, today).goal_analysis
                 if item.goal_id == goal_id), None)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


def compare_investment_categories(db: Session, user_id: int, goal_id: int):
    return compare_categories_for_goal(db, user_id, goal_id)


def analyze_affordability(db: Session, user_id: int, purchase: AffordabilityAnalyzeRequest,
                          today: date | None = None):
    if purchase.user_id != user_id:
        raise HTTPException(status_code=422, detail="Purchase user does not match requested user")
    return assess_purchase(load_planning_context(db, user_id, today), purchase)


def run_what_if_scenario(db: Session, user_id: int, scenario: WhatIfRequest, today: date | None = None):
    return run_what_if(db, user_id, scenario, today)


def get_financial_insights(db: Session, user_id: int, today: date | None = None):
    return build_financial_insights(db, load_planning_context(db, user_id, today))
