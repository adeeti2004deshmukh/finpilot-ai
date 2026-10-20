from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.entities import Goal
from app.schemas.planning import GoalComparisonResponse
from app.services.investment_allocation_service import build_investment_plan
from app.services.investment_category_service import score_category_relevance
from app.services.planning_context import load_planning_context


def compare_categories_for_goal(db: Session, user_id: int, goal_id: int) -> GoalComparisonResponse:
    context = load_planning_context(db, user_id)
    goal = db.get(Goal, goal_id)
    if goal is None or goal.user_id != user_id:
        raise HTTPException(status_code=404, detail="Goal not found")
    analysis = next(item for item in build_investment_plan(context).goal_analysis if item.goal_id == goal_id)
    categories = score_category_relevance(
        analysis,
        context.profile.risk_tolerance,
        context.summary.emergency_fund_coverage_percent,
    )
    return GoalComparisonResponse(
        goal=analysis,
        risk_tolerance=context.profile.risk_tolerance,
        liquidity_requirement="HIGH" if analysis.goal_horizon in ("VERY_SHORT_TERM", "SHORT_TERM") else "MEDIUM",
        categories_to_explore=categories,
        methodology="Scores combine goal horizon fit, risk-tolerance alignment, liquidity horizon, goal type, and emergency-fund coverage. They describe relevance only; they do not predict returns or guarantee suitability.",
    )
