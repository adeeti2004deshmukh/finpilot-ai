from app.services.auth import get_current_user, ensure_actor
from app.models.entities import User
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.entities import FinancialProfile
from app.schemas.profiles import FinancialProfileCreate, FinancialProfileResponse, FinancialProfileUpdate
from app.services.transactions import require_user

router = APIRouter(prefix="/api/profile", tags=["Profile"])


@router.get("/{user_id}", response_model=FinancialProfileResponse, summary="Get a user's financial profile")
def get_profile(user_id: int, db: Session = Depends(get_db)) -> FinancialProfile:
    profile = db.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Financial profile not found")
    return profile


@router.post("", response_model=FinancialProfileResponse, status_code=201, summary="Create a financial profile")
def create_profile(payload: FinancialProfileCreate, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> FinancialProfile:
    payload = payload.model_copy(update={"user_id": ensure_actor(actor, payload.user_id)})
    require_user(db, payload.user_id)
    existing = db.scalar(select(FinancialProfile).where(FinancialProfile.user_id == payload.user_id))
    if existing:
        raise HTTPException(status_code=409, detail="A financial profile already exists for this user")
    profile = FinancialProfile(**payload.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/{user_id}", response_model=FinancialProfileResponse, summary="Update a financial profile")
def update_profile(
    user_id: int,
    payload: FinancialProfileUpdate,
    db: Session = Depends(get_db),
) -> FinancialProfile:
    profile = db.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Financial profile not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile