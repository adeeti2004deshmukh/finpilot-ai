from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.dashboard import DashboardResponse, InvestableSurplusResponse
from app.services.finance import calculate_available_surplus, create_dashboard

router = APIRouter(tags=["Dashboard", "Investments"])


@router.get("/api/dashboard/{user_id}", response_model=DashboardResponse, summary="Get a user's financial dashboard")
def dashboard(user_id: int, db: Session = Depends(get_db)) -> DashboardResponse:
    return create_dashboard(db, user_id)


@router.get(
    "/api/investment/available/{user_id}",
    response_model=InvestableSurplusResponse,
    summary="Calculate available monthly investable surplus",
)
def available_investable_surplus(user_id: int, db: Session = Depends(get_db)) -> InvestableSurplusResponse:
    return calculate_available_surplus(db, user_id)