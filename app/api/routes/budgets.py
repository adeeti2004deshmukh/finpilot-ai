from app.services.auth import get_current_user, ensure_actor
from app.models.entities import User
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.entities import Budget, Category
from app.models.enums import CategoryType
from app.schemas.budgets import BudgetCreate, BudgetResponse, BudgetStatusResponse, BudgetUpdate
from app.services.finance import budget_status
from app.services.transactions import require_user

router = APIRouter(prefix="/api/budgets", tags=["Budgets"])


def require_expense_category(db: Session, category_id: int) -> None:
    category = db.get(Category, category_id)
    if category is None or category.type != CategoryType.EXPENSE:
        raise HTTPException(status_code=400, detail="Budget category must be an existing expense category")


@router.get("", response_model=list[BudgetResponse], summary="List a user's budgets")
def list_budgets(user_id: int = Query(gt=0), db: Session = Depends(get_db)) -> list[Budget]:
    return db.scalars(select(Budget).where(Budget.user_id == user_id).order_by(Budget.year, Budget.month)).all()


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED, summary="Create a budget")
def create_budget(payload: BudgetCreate, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> Budget:
    payload = payload.model_copy(update={"user_id": ensure_actor(actor, payload.user_id)})
    require_user(db, payload.user_id)
    require_expense_category(db, payload.category_id)
    budget = Budget(**payload.model_dump())
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


@router.get("/status", response_model=list[BudgetStatusResponse], summary="Get spending status for a month")
def get_budget_status(
    user_id: int = Query(gt=0),
    month: int = Query(default_factory=lambda: date.today().month, ge=1, le=12),
    year: int = Query(default_factory=lambda: date.today().year, ge=2000, le=2200),
    db: Session = Depends(get_db),
) -> list[dict]:
    budgets = db.scalars(
        select(Budget).where(Budget.user_id == user_id, Budget.month == month, Budget.year == year)
    ).all()
    return [budget_status(db, budget) for budget in budgets]


@router.put("/{budget_id}", response_model=BudgetResponse, summary="Update a budget")
def update_budget(budget_id: int, payload: BudgetUpdate, db: Session = Depends(get_db)) -> Budget:
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    changes = payload.model_dump(exclude_unset=True)
    if "category_id" in changes:
        require_expense_category(db, changes["category_id"])
    for field, value in changes.items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
        setattr(budget, field, value)
    db.commit()
    db.refresh(budget)
    return budget


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a budget")
def delete_budget(budget_id: int, db: Session = Depends(get_db)) -> Response:
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    db.delete(budget)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)