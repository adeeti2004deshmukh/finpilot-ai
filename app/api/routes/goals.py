from app.services.auth import get_current_user, ensure_actor
from app.models.entities import User
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.entities import Goal
from app.schemas.goals import GoalCreate, GoalResponse, GoalUpdate
from app.services.goals import goal_response
from app.services.transactions import require_user

router = APIRouter(prefix="/api/goals", tags=["Goals"])


@router.get("", response_model=list[GoalResponse], summary="List a user's goals")
def list_goals(user_id: int = Query(gt=0), db: Session = Depends(get_db)) -> list[GoalResponse]:
    goals = db.scalars(select(Goal).where(Goal.user_id == user_id).order_by(Goal.priority, Goal.id)).all()
    return [goal_response(goal) for goal in goals]


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED, summary="Create a goal")
def create_goal(payload: GoalCreate, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> GoalResponse:
    payload = payload.model_copy(update={"user_id": ensure_actor(actor, payload.user_id)})
    require_user(db, payload.user_id)
    goal = Goal(**payload.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal_response(goal)


@router.get("/{goal_id}", response_model=GoalResponse, summary="Get a goal")
def get_goal(goal_id: int, db: Session = Depends(get_db)) -> GoalResponse:
    goal = db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal_response(goal)


@router.put("/{goal_id}", response_model=GoalResponse, summary="Update a goal")
def update_goal(goal_id: int, payload: GoalUpdate, db: Session = Depends(get_db)) -> GoalResponse:
    goal = db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
        setattr(goal, field, value)
    db.commit()
    db.refresh(goal)
    return goal_response(goal)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a goal")
def delete_goal(goal_id: int, db: Session = Depends(get_db)) -> Response:
    goal = db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(goal)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)